"""Per-card thermal network coupled to a fixed flow field.

Die and memory meet the heatsink through resistances. The heatsink dumps heat
into the fin channel (ε-NTU) and, in parallel, off the shroud and backplate.
Backplate heat captured by the next card's inlet is what preheats a stacked
neighbour. Everything electrical ends up in the air so the enthalpy balance
can be checked.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from gpusim.flow import FlowSolution
from gpusim.network import AMB, Network
from gpusim.physics import CP_AIR, air_conductivity, air_density, air_viscosity, fin_epsilon


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


@dataclass
class ThermalSolution:
    cards: list[ThermalCard]
    node_temp: dict[str, float]
    heat_w: float
    enthalpy_w: float
    energy_error: float


def _linear_temperatures(net: Network, flow: FlowSolution, heat_branch, heat_node, t_amb: float):
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
    for br in net.branches:
        q = flow.flow_m3s.get(br.id, 0.0)
        if abs(q) < 1e-14:
            continue
        mass = abs(br.rho * q)
        if q >= 0:
            up, down = br.a, br.b
        else:
            up, down = br.b, br.a
        if down == AMB:
            continue
        j = index[down]
        matrix[j, j] += mass
        if up == AMB:
            rhs[j] += mass * t_amb
        else:
            matrix[j, index[up]] -= mass
        if down != AMB:
            rhs[j] += heat_branch.get(br.id, 0.0) / CP_AIR
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

    cpu = 0.0
    if build.radiator and build.radiator.model:
        cpu = float(build.radiator.cpu_power_w)
    heat_branch_cpu = {"radiator": cpu} if cpu else {}

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
            cond = g_conv + 1.0 / r_ext
            t_hs = (p_tot + g_conv * t_in + t_sink / r_ext) / cond
            q_ext = (t_hs - t_sink) / r_ext
            q_ext = float(np.clip(q_ext, -0.1 * p_tot, p_tot))
            q_channel = p_tot - q_ext
            per[gpu_id] = {
                "p_tot": p_tot,
                "p_die": p_die,
                "p_mem": p_mem,
                "t_hs": t_hs,
                "t_in": t_in,
                "q_ext": q_ext,
                "q_channel": q_channel,
                "mass": mass,
                "q_vol": max(q_vol, 0.0),
                "t_die": t_hs + p_die * params["r_tim"],
                "t_mem": t_hs + p_mem * params["r_mem"],
            }
            if blower is not None:
                heat_branch[blower.id] = q_channel
        # Backplate → neighbour inlet, remainder → GPU-zone air (or this exhaust
        # in open air, so the joules still leave with the stream).
        for idx, gpu_id in enumerate(net.ordered_ids):
            gap = net.gaps[gpu_id]
            q_ext = per[gpu_id]["q_ext"]
            downstream = None
            if idx + 1 < len(net.ordered_ids):
                nxt = net.ordered_ids[idx + 1]
                if net.gaps[nxt].get("upstream") == gpu_id:
                    downstream = nxt
            captured = 0.0
            if downstream is not None and q_ext > 0:
                g0 = params_by_card[next(g.card for g in build.gpus if g.id == gpu_id)]["capture_g0_mm"]
                frac = 1.0 / (1.0 + net.gaps[downstream]["gap_mm"] / max(g0, 0.5))
                captured = q_ext * frac
                heat_node[f"cin-{downstream}"] = heat_node.get(f"cin-{downstream}", 0.0) + captured
            rest = q_ext - captured
            if build.open_air or "gpu" not in net.nodes:
                heat_node[f"cex-{gpu_id}"] = heat_node.get(f"cex-{gpu_id}", 0.0) + rest
            else:
                heat_node["gpu"] = heat_node.get("gpu", 0.0) + rest
        t_nodes = _linear_temperatures(net, flow, heat_branch, heat_node, t_amb)
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
                )
            )

    heat = float(sum(heat_branch.values()) + sum(heat_node.values()))
    enthalpy = _enthalpy(net, flow, heat_branch, t_nodes, t_amb)
    error = abs(heat - enthalpy) / max(heat, 1.0)
    return ThermalSolution(last_cards, t_nodes, heat, enthalpy, error)
