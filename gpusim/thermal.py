"""Per-card thermal network coupled to a fixed flow field.

Die and memory meet the heatsink through resistances. The heatsink dumps heat
into the fin channel (ε-NTU) and, in parallel, off the shroud and backplate.
Backplate heat captured by the next card's inlet is what preheats a stacked
neighbour. Everything electrical ends up in the air so the enthalpy balance
can be checked.

Air temperatures come from an upwind advection balance on the solved flow
field: every node mixes the streams that flow into it. Rev 4 adds a plume
ingestion overlay. When a flow-through card's exhaust jet points at the fan
face of the card above, a fraction φ(gap) of that card's fan-side intake is
taken straight from the jet instead of from the GPU zone. The same mass is
removed from the jet's stream into the upper case volume and from the zone's
stream into the upper inlet, and the displaced zone air is sent where the jet
share would have gone, so every node still balances and no energy is created.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from gpusim.flow import FlowSolution
from gpusim.network import AMB, Network
from gpusim.physics import (
    CP_AIR,
    air_conductivity,
    air_density,
    air_viscosity,
    fin_epsilon,
    gap_channel_h,
    m3s_to_cfm,
    skin_couple_ua,
)


@dataclass
class ThermalCard:
    gpu_id: str
    power_w: float
    power_die_w: float
    power_mem_w: float
    t_die_c: float
    t_mem_c: float
    t_hs_c: float
    t_in_c: float
    t_exh_c: float
    flow_m3s: float
    mass_kg_s: float
    duty: float
    gap_mm: float
    gap_state: str
    detail: dict | None = None


@dataclass
class ThermalSolution:
    cards: list[ThermalCard]
    node_temp: dict[str, float]
    heat_w: float
    enthalpy_w: float
    energy_error: float
    transfers: list[dict] | None = None
    advection_residual: dict[str, float] | None = None


def zone_sweep(net: Network, flow: FlowSolution) -> tuple[float, float]:
    """Fresh air entering the GPU zone (m³/s) and the crossflow speed through
    the card region (m/s): that flow over `net.sweep_area_m2`."""
    q_in = 0.0
    for br in net.branches:
        if br.kind == "bleed":
            continue
        q = flow.flow_m3s.get(br.id, 0.0)
        if br.b == "gpu" and q > 0 and not br.a.startswith(("cin-", "cex-")):
            q_in += q
        elif br.a == "gpu" and q < 0 and not br.b.startswith(("cin-", "cex-")):
            q_in += -q
    area = max(float(getattr(net, "sweep_area_m2", 0.05) or 0.05), 1e-3)
    return q_in, q_in / area


def plume_transfers(net: Network, flow: FlowSolution, sample: dict) -> list[dict]:
    """Mass the upper card draws straight out of the lower card's exhaust jet.

    Derived from the solved flows, not a fixed function of the gap:

      V_j   = Q_jet / A_cutout                 jet speed leaving the backplate
      U_c   = Q_zone_in / A_sweep              crossflow through the card region
      s     = min(1, U_c · g / (V_j · L_f))    share of the jet the crossflow
                                               carries past the fan region (L_f
                                               long) while it crosses the gap g
      e     = α · P · g / A_cutout             zone air the jet entrains on the
                                               way (α ≈ 0.08, P = jet perimeter)
      ṁ_arr = ṁ_jet · (1 − s)                  hot air that reaches the fans above
      ṁ_ing = min(ṁ_in, ṁ_arr · (1 + e)) / (1 + e)

    The upper fans take the arriving mixture first (the jet points at them) and
    make up any shortfall with zone air. φ = ṁ_ing / ṁ_in is reported.
    """
    alpha = float(sample.get("plume_entrainment", 0.08))
    sweep_scale = float(sample.get("plume_sweep_scale", 1.0))
    q_zone, u_c = zone_sweep(net, flow)
    u_c *= sweep_scale
    geom = getattr(net, "plume_geom", {}) or {}
    out = []
    for lower, upper, gap_mm in getattr(net, "plume_pairs", []) or []:
        up = net.by_id(f"upexit-{lower}")
        inlet = net.by_id(f"gap-{upper}-fan")
        if up is None or inlet is None:
            continue
        m_up = up.rho * flow.flow_m3s.get(up.id, 0.0)
        m_in = inlet.rho * flow.flow_m3s.get(inlet.id, 0.0)
        cutout, width = geom.get(lower, (0.012, 0.22))
        g = max(float(gap_mm), 0.0) / 1000.0
        v_jet = (m_up / up.rho) / max(cutout, 1e-6) if m_up > 0 else 0.0
        swept = min(1.0, u_c * g / max(v_jet * width, 1e-9)) if v_jet > 0 else 1.0
        perimeter = 2.0 * (width + cutout / max(width, 1e-6))
        entrained = alpha * perimeter * g / max(cutout, 1e-6)
        arriving = max(m_up, 0.0) * (1.0 - swept)
        if m_up <= 0 or m_in <= 0:
            m_ing = 0.0
        else:
            m_ing = min(m_in, arriving * (1.0 + entrained)) / (1.0 + entrained)
            m_ing = min(m_ing, 0.98 * m_up)
        phi = (m_ing / m_in) if m_in > 0 else 0.0
        out.append(
            {
                "id": f"plume-{lower}-{upper}",
                "lower": lower,
                "upper": upper,
                "gap_mm": gap_mm,
                "phi": phi,
                "jet_velocity_m_s": v_jet,
                "crossflow_m_s": u_c,
                "swept_fraction": swept,
                "entrained_ratio": entrained,
                "from_node": f"cex-{lower}",
                "to_node": f"cin-{upper}",
                "out_branch": up.id,
                "in_branch": inlet.id,
                # Zone air the upper card no longer takes goes where the jet
                # share would have gone, so both nodes still balance.
                "displaced_from": inlet.a,
                "displaced_to": up.b,
                "mass_kg_s": m_ing,
                "share_of_upper_intake": phi,
                "share_of_lower_jet": (m_ing / m_up) if m_up > 0 else 0.0,
                "rho": up.rho,
            }
        )
    return out


def _streams(net: Network, flow: FlowSolution, transfers) -> list[tuple[str, str, float, str | None]]:
    """(upstream, downstream, mass kg/s, branch id) with the plume overlay applied."""
    cut: dict[str, float] = {}
    for t in transfers or []:
        cut[t["out_branch"]] = cut.get(t["out_branch"], 0.0) + t["mass_kg_s"]
        cut[t["in_branch"]] = cut.get(t["in_branch"], 0.0) + t["mass_kg_s"]
    out = []
    for br in net.branches:
        q = flow.flow_m3s.get(br.id, 0.0)
        if abs(q) < 1e-14:
            continue
        mass = abs(br.rho * q)
        if br.id in cut and q > 0:
            mass = max(mass - cut[br.id], 0.0)
        up, down = (br.a, br.b) if q >= 0 else (br.b, br.a)
        out.append((up, down, mass, br.id))
    for t in transfers or []:
        if t["mass_kg_s"] > 0:
            out.append((t["from_node"], t["to_node"], t["mass_kg_s"], None))
            if t["displaced_from"] != t["displaced_to"]:
                out.append((t["displaced_from"], t["displaced_to"], t["mass_kg_s"], None))
    return out


def advection_residual(net: Network, flow: FlowSolution, transfers) -> dict[str, float]:
    """Mass in minus mass out at every internal node, overlay included."""
    res = {n: 0.0 for n in net.nodes if n != AMB}
    for up, down, mass, _ in _streams(net, flow, transfers):
        if down in res:
            res[down] += mass
        if up in res:
            res[up] -= mass
    return res


def _linear_temperatures(net: Network, flow: FlowSolution, heat_branch, heat_node, t_amb: float, transfers=None):
    unknowns = [n for n in net.nodes if n != AMB]
    index = {n: i for i, n in enumerate(unknowns)}
    n = len(unknowns)
    if n == 0:
        return {AMB: t_amb}
    matrix = np.zeros((n, n))
    rhs = np.zeros(n)
    for i in range(n):
        matrix[i, i] += 1e-8
        rhs[i] += 1e-8 * t_amb
    for up, down, mass, bid in _streams(net, flow, transfers):
        if down == AMB:
            continue
        j = index[down]
        matrix[j, j] += mass
        if up == AMB:
            rhs[j] += mass * t_amb
        else:
            matrix[j, index[up]] -= mass
        if bid is not None:
            rhs[j] += heat_branch.get(bid, 0.0) / CP_AIR
    for node, watts in heat_node.items():
        if node in index:
            rhs[index[node]] += watts / CP_AIR
    try:
        solved = np.linalg.solve(matrix, rhs)
    except np.linalg.LinAlgError:
        solved = np.linalg.lstsq(matrix, rhs, rcond=None)[0]
    temps = {AMB: t_amb}
    temps.update({name: float(solved[index[name]]) for name in unknowns})
    return temps


def _enthalpy(net, flow, heat_branch, t_nodes, t_amb) -> float:
    net_w = 0.0
    for br in net.branches:
        q = flow.flow_m3s.get(br.id, 0.0)
        if abs(q) < 1e-14:
            continue
        mass = abs(br.rho * q)
        if q >= 0:
            up, down = br.a, br.b
        else:
            up, down = br.b, br.a
        if down == AMB and up != AMB:
            t_up = t_nodes.get(up, t_amb)
            net_w += mass * CP_AIR * (t_up - t_amb) + heat_branch.get(br.id, 0.0)
    return net_w


def _wash(net: Network, gpu_id: str) -> list[dict]:
    return [g for g in (getattr(net, "shroud_gaps", None) or []) if gpu_id in (g["upper"], g["lower"])]


def _washes_for(net: Network, gpu_id: str) -> list[dict]:
    """Gap walls this card gives heat to.

    Inter-card mouths are the card's own shroud branches. A card with no
    mouth (the vertical card) still has one face in the plenum stream when
    the shroud is pulling an open gap, so it borrows that stream. A taped
    crack does not lend its stream: the crack resistance is unchanged.
    """
    own = _wash(net, gpu_id)
    if own:
        return own
    pulls = [g for g in (getattr(net, "shroud_gaps", None) or []) if g.get("kind") == "shroud-pull"]
    if not pulls:
        return []
    donor = max(pulls, key=lambda g: float(g.get("area_m2") or 0.0))
    guest = dict(donor)
    guest["upper"] = gpu_id
    guest["guest"] = True
    return [guest]


def _wall_conductance(ua: float, mass_kg_s: float) -> float:
    """W/K this wall can put into its half of the bypass stream (ε-NTU)."""
    cap = 0.5 * max(float(mass_kg_s), 0.0) * CP_AIR
    if cap < 1e-8 or ua <= 0.0:
        return 0.0
    return float((1.0 - math.exp(-min(ua / cap, 40.0))) * cap)


def solve_thermal(
    build,
    net: Network,
    flow: FlowSolution,
    powers: dict[str, tuple[float, float, float]],
    duties: dict[str, float],
    sample: dict,
    t_amb: float,
) -> ThermalSolution:
    nu_c = float(sample.get("nu_C", 0.064))
    nu_m = float(sample.get("nu_m", 0.60))
    params_by_card = sample["cards"]
    t_nodes = {n: t_amb for n in net.nodes}
    t_nodes[AMB] = t_amb
    last_cards: list[ThermalCard] = []
    heat_branch: dict[str, float] = {}
    heat_node: dict[str, float] = {}

    heat_branch_cpu: dict[str, float] = {}
    cpu_w = float(build.cpu.power_w) if not build.open_air else 0.0
    if cpu_w > 0:
        if build.cpu.cooling == "air" and net.by_id("cpu-cooler") is not None:
            heat_branch_cpu["cpu-cooler"] = cpu_w
        elif net.by_id("radiator") is not None:
            heat_branch_cpu["radiator"] = cpu_w
    transfers = [] if build.open_air else plume_transfers(net, flow, sample)
    # Previous-pass heatsink temperatures, for the skin-to-skin gap.
    hs_prev: dict[str, float] = {}

    for _ in range(4):
        heat_branch = dict(heat_branch_cpu)
        heat_node = {}
        per: dict[str, dict] = {}
        for gpu_id in net.ordered_ids:
            gpu = next(g for g in build.gpus if g.id == gpu_id)
            params = params_by_card[gpu.card]
            p_tot, p_die, p_mem = powers[gpu_id]
            blower = net.by_id(f"blower-{gpu_id}")
            q_vol = flow.flow_m3s.get(blower.id, 0.0) if blower else 0.0
            rho = blower.rho if blower else air_density(t_amb, build.altitude_m)
            mass = max(rho * q_vol, 0.0) if q_vol > 0 else 0.0
            t_film = max(t_nodes.get(f"cin-{gpu_id}", t_amb), t_amb)
            eps = fin_epsilon(
                mass,
                rho,
                air_viscosity(t_film),
                air_conductivity(t_film),
                nu_c,
                nu_m,
                params["dh_m"],
                params["fin_area_m2"],
                params["channel_area_m2"],
            )
            g_conv = eps * mass * CP_AIR
            t_in = t_nodes.get(f"cin-{gpu_id}", t_amb)
            if build.open_air:
                t_sink = t_amb
            else:
                t_sink = t_nodes.get("gpu", t_amb)
            r_ext = max(params["r_ext"], 0.05)
            t_sink_used = t_sink
            washed = _washes_for(net, gpu_id)
            skin_rows: list[dict] = []
            q_couple = 0.0
            h_report = 0.0
            if not washed:
                # No shroud stream on this card: the calibrated stagnant shell
                # path. Shroud-off builds, including both anchors, stay here.
                cond = g_conv + 1.0 / r_ext
                t_hs = (p_tot + g_conv * t_in + t_sink / r_ext) / cond
                q_ext = (t_hs - t_sink) / r_ext
                q_ext = float(np.clip(q_ext, -0.1 * p_tot, p_tot))
                q_channel = p_tot - q_ext
                q_skin = 0.0
            else:
                # Washed faces convect into the bypass (or crack) stream.
                # Unwashed faces keep their share of r_ext. A taped crack also
                # couples the two skins by conduction and radiation.
                n_wash = min(len(washed), 2)
                g_stag = (1.0 / r_ext) * (2 - n_wash) / 2.0
                k_air = air_conductivity(t_film)
                mu = air_viscosity(t_film)
                nu_skin_m = float(sample.get("skin_nu_m", 0.50))
                full_mm = float(sample.get("skin_gap_full_h_mm", 12.0))
                emiss = float(sample.get("skin_emissivity", 0.80))
                t_zone = t_nodes.get("gpu", t_amb)
                numer = p_tot + g_conv * t_in + g_stag * t_zone
                denom = g_conv + g_stag
                for rec in washed:
                    br = net.by_id(rec["id"])
                    q_gap = flow.flow_m3s.get(rec["id"], 0.0) if br else 0.0
                    rho_b = br.rho if br else rho
                    mass_gap = abs(rho_b * q_gap)
                    # Open-gap C is the 2026-09-30 soak fit. The tape crack
                    # keeps the old skin_nu_C so its resistance does not move.
                    if rec["kind"] == "shroud-pull":
                        nu_skin_c = float(sample.get("open_gap_nu_C", sample.get("skin_nu_C", 0.10)))
                    else:
                        nu_skin_c = float(sample.get("skin_nu_C", 0.10))
                    gap_m = max(float(rec["gap_mm"]), 0.3) / 1000.0
                    h = gap_channel_h(
                        mass_gap, rho_b, mu, k_air, gap_m, rec["span_m"], nu_skin_c, nu_skin_m
                    )
                    degrade = min(1.0, max(float(rec["gap_mm"]), 0.0) / max(full_mm, 0.5))
                    h *= degrade
                    g_i = _wall_conductance(h * float(rec["skin_m2"]), mass_gap)
                    neighbor = rec["lower"] if rec["upper"] == gpu_id else rec["upper"]
                    ua_c = 0.0
                    if rec["kind"] == "shroud-crack":
                        t_self = hs_prev.get(gpu_id, t_zone)
                        t_other = hs_prev.get(neighbor, t_zone)
                        ua_c = skin_couple_ua(gap_m, rec["skin_m2"], t_self, t_other, emiss, k_air)
                        numer += ua_c * t_other
                        denom += ua_c
                    numer += g_i * t_zone
                    denom += g_i
                    skin_rows.append(
                        {
                            "id": rec["id"],
                            "g": g_i,
                            "h": h,
                            "mass": mass_gap,
                            "neighbor": neighbor,
                            "ua": ua_c,
                            "cfm": m3s_to_cfm(abs(q_gap)),
                        }
                    )
                t_hs = numer / max(denom, 1e-6)
                q_skin = 0.0
                q_stag = g_stag * (t_hs - t_zone)
                q_couple = 0.0
                h_report = 0.0
                for row_s in skin_rows:
                    q_i = row_s["g"] * (t_hs - t_zone)
                    h_report += row_s["h"]
                    if row_s["mass"] < 1e-7:
                        q_i = 0.0
                    else:
                        heat_branch[row_s["id"]] = heat_branch.get(row_s["id"], 0.0) + q_i
                    q_skin += q_i
                    if row_s["ua"] > 0.0:
                        q_couple += row_s["ua"] * (t_hs - hs_prev.get(row_s["neighbor"], t_hs))
                # Couple is metal-to-metal. Recompute it off this pass's own
                # heatsinks once both cards exist; until then the previous
                # pass is the other wall. The two directions cancel globally
                # once the temperatures settle.
                q_ext = q_stag
                q_channel = p_tot - q_skin - q_stag - q_couple
                if skin_rows:
                    h_report /= len(skin_rows)
            per[gpu_id] = {
                "p_tot": p_tot,
                "p_die": p_die,
                "p_mem": p_mem,
                "t_hs": t_hs,
                "t_in": t_in,
                "q_ext": q_ext,
                "q_channel": q_channel,
                "q_skin": q_skin,
                "q_couple": q_couple,
                "skin_h": h_report,
                "bypass_cfm": sum(s["cfm"] for s in skin_rows),
                "skins": skin_rows,
                "mass": mass,
                "q_vol": max(q_vol, 0.0),
                "t_die": t_hs + p_die * params["r_tim"],
                "t_mem": t_hs + p_mem * params["r_mem"],
                "eps": eps,
                "g_conv": g_conv,
                "r_ext": r_ext,
                "r_tim": params["r_tim"],
                "r_mem": params["r_mem"],
                "t_sink": t_sink_used,
                "washed": bool(washed),
            }
            if blower is not None:
                heat_branch[blower.id] = q_channel
        # Skin-to-skin heat uses this pass's heatsinks, so what leaves one
        # card arrives at the other and the air still sees the whole load.
        for gpu_id, row in per.items():
            skins = row.get("skins") or []
            if not skins or not any(s["ua"] > 0 for s in skins):
                continue
            t_hs = row["t_hs"]
            q_couple = 0.0
            for skin in skins:
                if skin["ua"] <= 0.0:
                    continue
                other = per[skin["neighbor"]]["t_hs"]
                q_couple += skin["ua"] * (t_hs - other)
            row["q_channel"] -= q_couple - row["q_couple"]
            row["q_couple"] = q_couple
            blower = net.by_id(f"blower-{gpu_id}")
            if blower is not None:
                heat_branch[blower.id] = row["q_channel"]
        hs_prev = {gid: row["t_hs"] for gid, row in per.items()}
        # External heat leaves through the fan face (down) and the backplate (up).
        # A tight gap returns a share of that heat into the inlet that breathes it.
        # The rest warms the GPU zone. Nothing here is reserved for the lowest card.
        for gpu_id in net.ordered_ids:
            gap = net.gaps[gpu_id]
            q_ext = per[gpu_id]["q_ext"]
            gpu = next(g for g in build.gpus if g.id == gpu_id)
            g0 = params_by_card[gpu.card]["capture_g0_mm"]
            if build.open_air or "gpu" not in net.nodes or q_ext == 0:
                dest = f"cex-{gpu_id}"
                heat_node[dest] = heat_node.get(dest, 0.0) + q_ext
                continue
            captured = 0.0
            for side in gap.get("sides") or []:
                share = max(q_ext, 0.0) * float(side["fraction"])
                frac = 1.0 / (1.0 + float(side["gap_mm"]) / max(g0, 0.5))
                portion = share * frac
                if portion <= 0:
                    continue
                if side["name"] == "fan":
                    # The fan inhales this gap, including heat off its own shroud.
                    target = f"cin-{gpu_id}"
                elif side.get("neighbor"):
                    # Backplate faces the card above; that card's fan draws the same gap.
                    target = f"cin-{side['neighbor']}"
                else:
                    continue
                heat_node[target] = heat_node.get(target, 0.0) + portion
                captured += portion
            rest = q_ext - captured
            heat_node["gpu"] = heat_node.get("gpu", 0.0) + rest
        t_nodes = _linear_temperatures(net, flow, heat_branch, heat_node, t_amb, transfers)
        last_cards = []
        for gpu_id in net.ordered_ids:
            row = per[gpu_id]
            gap = net.gaps[gpu_id]
            t_in = t_nodes.get(f"cin-{gpu_id}", t_amb)
            t_ex = t_nodes.get(f"cex-{gpu_id}", t_in)
            # Recompute metal temperatures off the updated inlet so the reported
            # die matches the air the blower actually swallowed.
            gpu = next(g for g in build.gpus if g.id == gpu_id)
            params = params_by_card[gpu.card]
            # Keep the heatsink solved above; shift die with the inlet movement
            # already included in t_hs from this iteration's t_in (previous pass).
            plume = next((t for t in transfers if t["upper"] == gpu_id), None)
            detail = {
                "cooler": getattr(net, "cooler", {}).get(gpu_id, "blower"),
                "t_zone_c": t_nodes.get("gpu", t_amb),
                "t_inlet_c": t_in,
                # The inlet temperature the heatsink balance below actually used
                # (previous pass). T_die = this + q_channel·R_conv + P_die·R_tim.
                "t_inlet_used_c": row["t_in"],
                "inlet_heat_captured_w": heat_node.get(f"cin-{gpu_id}", 0.0),
                "plume_from": plume["lower"] if plume else None,
                "plume_phi": plume["phi"] if plume else 0.0,
                "plume_share_of_intake": plume["share_of_upper_intake"] if plume else 0.0,
                "plume_source_temp_c": t_nodes.get(plume["from_node"], t_amb) if plume else None,
                "mass_kg_s": row["mass"],
                "epsilon": row["eps"],
                "g_conv_w_per_k": row["g_conv"],
                "r_conv_k_per_w": (1.0 / row["g_conv"]) if row["g_conv"] > 1e-9 else None,
                "r_ext_k_per_w": row["r_ext"],
                "t_ext_sink_c": row["t_sink"],
                "q_channel_w": row["q_channel"],
                "q_ext_w": row["q_ext"],
                "q_skin_w": row.get("q_skin", 0.0),
                "q_couple_w": row.get("q_couple", 0.0),
                "skin_h_w_m2k": row.get("skin_h", 0.0),
                "bypass_cfm": row.get("bypass_cfm", 0.0),
                "t_heatsink_c": row["t_hs"],
                "r_tim_k_per_w": row["r_tim"],
                "p_die_w": row["p_die"],
                "p_mem_w": row["p_mem"],
                "r_mem_k_per_w": row["r_mem"],
                "t_die_c": row["t_die"],
                "t_exhaust_c": t_ex,
            }
            last_cards.append(
                ThermalCard(
                    gpu_id=gpu_id,
                    power_w=row["p_tot"],
                    power_die_w=row["p_die"],
                    power_mem_w=row["p_mem"],
                    t_die_c=row["t_die"],
                    t_mem_c=row["t_mem"],
                    t_hs_c=row["t_hs"],
                    t_in_c=t_in,
                    t_exh_c=t_ex,
                    flow_m3s=row["q_vol"],
                    mass_kg_s=row["mass"],
                    duty=duties.get(gpu_id, 0.0),
                    gap_mm=gap["gap_mm"],
                    gap_state=gap["state"],
                    detail=detail,
                )
            )

    heat = float(sum(heat_branch.values()) + sum(heat_node.values()))
    enthalpy = _enthalpy(net, flow, heat_branch, t_nodes, t_amb)
    error = abs(heat - enthalpy) / max(heat, 1.0)
    residual = advection_residual(net, flow, transfers)
    return ThermalSolution(last_cards, t_nodes, heat, enthalpy, error, transfers, residual)
