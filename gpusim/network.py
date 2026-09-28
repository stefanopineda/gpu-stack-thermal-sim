"""Build the flow network for one configuration.

Nodes (gauge pressure, ambient = 0): case volume, GPU zone, optional PSU
chamber, each card inlet, each card exhaust, a rear plume (shroud off), and
a shroud plenum (shroud on or passive).

Front intake on a direct-to-GPU case dumps into the GPU zone. The radiator and
the rear case fan sit on the main case volume, downstream of that zone on
Meshify-style layouts.
"""

from __future__ import annotations

import numpy as np

from gpusim.calib import CABLE_K, FILTER_K_AT_REF, OBSTRUCTION_K, SEAL_CD, SEAL_OPEN_FRACTION
from gpusim.flow import Branch
from gpusim.layout import gap_table, inlet_area_m2, is_vertical, sort_gpus
from gpusim.models import BuildCfg, CaseModel
from gpusim.physics import air_density, fan_tables, orifice_k, quadratic_curve, rpm_from_duty, scale_parallel

AMB = "amb"


def _fan_qp(fan, rpm: float, parallel: int, p_scale: float):
    q, p = fan_tables(list(zip(fan.pq_m3h, fan.pq_mmh2o)))
    p = p * p_scale
    q, p = scale_parallel(q, p, parallel)
    return q, p, rpm, fan.rpm_max


def _blower_qp(params: dict, duty: float):
    qmax_m3h = params["qmax_m3s"] * 3600.0
    pmax_mm = params["pmax_pa"] / 9.80665
    q, p = fan_tables(quadratic_curve(qmax_m3h, pmax_mm, n=11))
    # Duty is a fraction of max RPM (affinity Q ∝ duty), with a floor at rpm_min.
    rpm = max(float(params["rpm_min"]), float(duty) * float(params["rpm_max"]))
    return q, p, rpm, params["rpm_max"]


class Network:
    def __init__(self, branches: list[Branch], nodes: list[str], gaps: dict, ordered_ids: list[str]):
        self.branches = branches
        self.nodes = nodes
        self.gaps = gaps
        self.ordered_ids = ordered_ids

    def by_id(self, ident: str) -> Branch | None:
        for br in self.branches:
            if br.id == ident:
                return br
        return None


def build_network(
    build: BuildCfg,
    case: CaseModel | None,
    fans: dict,
    cards: dict,
    radiators: dict,
    duties: dict[str, float],
    node_temp: dict[str, float],
    sample: dict | None = None,
) -> Network:
    sample = sample or {}
    k_scale = float(sample.get("k_scale", 1.0))
    seal_scale = float(sample.get("seal_scale", 1.0))
    ippc_scale = float(sample.get("ippc_p_scale", 1.0))
    t_ref = build.ambient_c + build.room_reingestion_c + float(sample.get("ambient_offset", 0.0))
    rho_ref = air_density(t_ref, build.altitude_m)

    def rho_for(node: str) -> float:
        return air_density(node_temp.get(node, t_ref), build.altitude_m)

    branches: list[Branch] = []
    nodes: set[str] = {AMB}

    def add(br: Branch) -> None:
        br.k = max(br.k, 1.0) * (k_scale if br.kind != "bleed" else 1.0)
        branches.append(br)
        nodes.add(br.a)
        nodes.add(br.b)

    def bleed(node: str) -> None:
        area = float(sample.get("bleed_area_m2", 8.0e-6))
        add(
            Branch(
                id=f"bleed-{node}",
                a=AMB,
                b=node,
                k=orifice_k(area, rho_ref, 0.6),
                k_lin=0.5,
                rho=rho_ref,
                kind="bleed",
                label=f"Numerical bleed into {node}",
            )
        )

    if build.open_air or (case is not None and build.case == "open-air"):
        return _open_air(build, cards, duties, sample, rho_ref, add, bleed, nodes, branches)

    assert case is not None
    gaps = gap_table(build, case, cards)
    ordered = [g.id for g in sort_gpus(build)]
    direct = case.airflow_layout == "direct_front_to_gpu"
    intake_node = "gpu" if direct else "case"

    for name in ("case", "gpu"):
        bleed(name)
    if build.buoyancy:
        # Stack effect is a few tenths of a pascal; kept as a pressure bias via k_lin sign later.
        pass

    _add_mounts(
        build, case, fans, intake_node, rho_ref, rho_for, ippc_scale, sample, add,
    )
    _add_radiator(build, case, fans, radiators, rho_ref, ippc_scale, sample, add)
    _add_panel_leaks(build, case, rho_ref, seal_scale, direct, add)
    _add_spill(build, case, rho_ref, sample, add)

    shroud_on = build.shroud.mode in ("on", "passive")
    if shroud_on:
        bleed("plenum")
        _add_shroud_fans(build, fans, rho_ref, ippc_scale, sample, add)
    else:
        bleed("plume")
        add(
            Branch(
                id="plume-room",
                a="plume",
                b=AMB,
                k=orifice_k(float(sample.get("plume_area_m2", 0.04)), rho_ref, 0.8),
                k_lin=0.2,
                rho=rho_for("plume"),
                kind="plume",
                label="Rear exhaust plume mixing into the room",
            )
        )

    _add_rear_slots(build, case, rho_ref, seal_scale, shroud_on, sample, add)

    for gpu in sort_gpus(build):
        params = dict(sample.get("cards", {}).get(gpu.card, {}))
        # caller merges card tuning; sample['cards'][id] is a full dict when MC-ing
        if not params:
            from gpusim.calib import card_tuning

            params = card_tuning(gpu.card)
        gap = gaps[gpu.id]
        area = inlet_area_m2(
            gap["gap_mm"], gap["state"], params["inlet_width_m"], params["inlet_eye_m2"]
        )
        feed = "gpu"
        add(
            Branch(
                id=f"gap-{gpu.id}",
                a=feed,
                b=f"cin-{gpu.id}",
                k=orifice_k(area, rho_ref, 0.62),
                k_lin=2.0,
                rho=rho_for(feed),
                kind="gap",
                label=f"{gpu.id} inlet slit ({gap['state']}, {gap['gap_mm']:.1f} mm)",
            )
        )
        bleed(f"cin-{gpu.id}")
        if gap["lowest"] and not gap["vertical"]:
            bypass = float(sample.get("bottom_bypass_m2", 1.15e-3))
            if build.psu_location == "open":
                bypass = float(sample.get("bottom_bypass_open_psu_m2", bypass * 1.8))
            add(
                Branch(
                    id=f"bypass-{gpu.id}",
                    a="gpu",
                    b=f"cin-{gpu.id}",
                    k=orifice_k(bypass, rho_ref, 0.7),
                    k_lin=1.0,
                    rho=rho_for("gpu"),
                    kind="bypass",
                    label=f"{gpu.id} PSU-shroud bypass into the lowest inlet",
                )
            )
        q, p, rpm, rpm_ref = _blower_qp(params, duties.get(gpu.id, 0.7))
        add(
            Branch(
                id=f"blower-{gpu.id}",
                a=f"cin-{gpu.id}",
                b=f"cex-{gpu.id}",
                k=float(params["channel_k"]),
                k_lin=5.0,
                rho=rho_for(f"cin-{gpu.id}"),
                kind="blower",
                label=f"{gpu.id} blower and fin channel",
                q_tab=q,
                p_tab=p,
                rpm=rpm,
                rpm_ref=rpm_ref,
                heat_tag=f"gpu:{gpu.id}",
            )
        )
        bleed(f"cex-{gpu.id}")
        dest = "plenum" if shroud_on else "plume"
        add(
            Branch(
                id=f"bracket-{gpu.id}",
                a=f"cex-{gpu.id}",
                b=dest,
                k=orifice_k(params["bracket_vent_m2"], rho_ref, 0.62),
                k_lin=1.0,
                rho=rho_for(f"cex-{gpu.id}"),
                kind="bracket",
                label=f"{gpu.id} rear bracket vent into the {dest}",
            )
        )
        if not shroud_on:
            recirc = float(sample.get("recirc_area_m2", 1.1e-4))
            add(
                Branch(
                    id=f"recirc-{gpu.id}",
                    a=f"cex-{gpu.id}",
                    b="gpu",
                    k=orifice_k(recirc, rho_ref, 0.6),
                    k_lin=1.0,
                    rho=rho_for(f"cex-{gpu.id}"),
                    kind="recirc",
                    label=f"{gpu.id} exhaust short-circuit back into the GPU zone",
                )
            )

    if build.buoyancy:
        _apply_buoyancy(branches, node_temp, t_ref, case)

    return Network(branches, sorted(nodes), gaps, ordered)


def _open_air(build, cards, duties, sample, rho_ref, add, bleed, nodes, branches) -> Network:
    from gpusim.calib import card_tuning
    from gpusim.layout import sort_gpus

    gaps = {}
    ordered = []
    for gpu in sort_gpus(build):
        params = dict(sample.get("cards", {}).get(gpu.card) or card_tuning(gpu.card))
        bleed(f"cin-{gpu.id}")
        bleed(f"cex-{gpu.id}")
        add(
            Branch(
                id=f"gap-{gpu.id}",
                a=AMB,
                b=f"cin-{gpu.id}",
                # Same eye area the case uses once the slit is no longer the limiter,
                # so open air is not an unrealistically easy inlet.
                k=orifice_k(params["inlet_eye_m2"], rho_ref, 0.72),
                k_lin=1.0,
                rho=rho_ref,
                kind="gap",
                label=f"{gpu.id} open-air inlet",
            )
        )
        q, p, rpm, rpm_ref = _blower_qp(params, duties.get(gpu.id, 0.7))
        add(
            Branch(
                id=f"blower-{gpu.id}",
                a=f"cin-{gpu.id}",
                b=f"cex-{gpu.id}",
                k=float(params["channel_k"]),
                k_lin=5.0,
                rho=rho_ref,
                kind="blower",
                label=f"{gpu.id} blower and fin channel",
                q_tab=q,
                p_tab=p,
                rpm=rpm,
                rpm_ref=rpm_ref,
                heat_tag=f"gpu:{gpu.id}",
            )
        )
        add(
            Branch(
                id=f"bracket-{gpu.id}",
                a=f"cex-{gpu.id}",
                b=AMB,
                k=orifice_k(params["bracket_vent_m2"], rho_ref, 0.7),
                k_lin=1.0,
                rho=rho_ref,
                kind="bracket",
                label=f"{gpu.id} open-air exhaust",
            )
        )
        gaps[gpu.id] = {
            "gap_mm": 80.0,
            "state": "open_slot",
            "upstream": None,
            "lowest": False,
            "vertical": False,
        }
        ordered.append(gpu.id)
    return Network(branches, sorted(nodes), gaps, ordered)


def _resolved_mounts(build: BuildCfg, case: CaseModel) -> list:
    by_id = {m.id: m for m in build.mounts}
    resolved = []
    for layout in case.mounts:
        if layout.id in by_id:
            mount = by_id[layout.id]
            if mount.size_mm <= 0:
                mount.size_mm = layout.size_mm
            resolved.append(mount)
        else:
            from gpusim.models import MountCfg

            resolved.append(
                MountCfg(
                    id=layout.id,
                    panel=layout.panel,
                    size_mm=layout.size_mm,
                    state="blanked",
                )
            )
    return resolved


def _panel_target(panel: str, intake_node: str) -> str:
    if panel == "front":
        return intake_node
    if panel == "bottom":
        return "gpu"
    return "case"


def _add_mounts(build, case, fans, intake_node, rho_ref, rho_for, ippc_scale, sample, add) -> None:
    cage = build.drive_cage == "present"
    for mount in _resolved_mounts(build, case):
        if mount.state == "radiator":
            continue
        target = _panel_target(mount.panel, intake_node)
        filt = build.filters.get(mount.panel, "none")
        k_extra = FILTER_K_AT_REF.get(filt, 0.0)
        if mount.panel == "front" and cage:
            k_extra += float(sample.get("drive_cage_k", 6.0e4))
        hole = 0.55 * (mount.size_mm / 1000.0) ** 2
        if mount.state == "blanked":
            add(
                Branch(
                    id=f"mount-{mount.id}",
                    a=AMB,
                    b=target,
                    k=orifice_k(hole * 0.01, rho_ref, 0.6),
                    k_lin=1.0,
                    rho=rho_ref,
                    kind="blank",
                    label=f"{mount.id} blanked mount",
                )
            )
            continue
        if mount.state == "empty" or not mount.fan:
            add(
                Branch(
                    id=f"mount-{mount.id}",
                    a=AMB,
                    b=target,
                    k=orifice_k(hole, rho_ref, 0.68) + k_extra,
                    k_lin=0.5,
                    rho=rho_ref,
                    kind="orifice",
                    label=f"{mount.id} open mount",
                )
            )
            continue
        fan = fans[mount.fan]
        p_scale = ippc_scale if fan.id == "noctua-nf-a14-ippc-3000" else 1.0
        rpm = rpm_from_duty(fan.rpm_min, fan.rpm_max, mount.duty)
        q, p, rpm, rpm_ref = _fan_qp(fan, rpm, 1, p_scale)
        forward_a, forward_b = (AMB, target) if mount.direction == "intake" else (target, AMB)
        add(
            Branch(
                id=f"mount-{mount.id}",
                a=forward_a,
                b=forward_b,
                k=orifice_k(hole, rho_ref, 0.72) + k_extra,
                k_lin=1.0,
                rho=rho_for(forward_a) if forward_a != AMB else rho_ref,
                kind="fan",
                label=f"{mount.id} {fan.name} {mount.direction}",
                q_tab=q,
                p_tab=p,
                rpm=rpm,
                rpm_ref=rpm_ref,
            )
        )


def _add_radiator(build, case, fans, radiators, rho_ref, ippc_scale, sample, add) -> None:
    rad_cfg = build.radiator
    if not rad_cfg.model:
        return
    rad = radiators[rad_cfg.model]
    fan_id = rad_cfg.fan or rad.default_fan
    fan = fans[fan_id]
    count = rad_cfg.fan_count or rad.fan_count
    p_scale = ippc_scale if fan.id == "noctua-nf-a14-ippc-3000" else 1.0
    rpm = rpm_from_duty(fan.rpm_min, fan.rpm_max, rad_cfg.fan_duty)
    q, p, rpm, rpm_ref = _fan_qp(fan, rpm, count, p_scale)
    k_path = 8.0e4 * (rad.thickness_mm / 38.0) * (max(rad.fpi, 1.0) / 18.0)
    k_rad = k_path / float(count * count)
    filt = build.filters.get(rad_cfg.panel, "none")
    k_rad += FILTER_K_AT_REF.get(filt, 0.0) / float(count * count)
    if rad_cfg.direction == "intake":
        a, b = AMB, "case"
    else:
        a, b = "case", AMB
    add(
        Branch(
            id="radiator",
            a=a,
            b=b,
            k=k_rad,
            k_lin=2.0,
            rho=rho_ref if a == AMB else air_density_safe(build, "case"),
            kind="radiator",
            label=f"{rad.name} {rad_cfg.panel} {rad_cfg.direction}",
            q_tab=q,
            p_tab=p,
            rpm=rpm,
            rpm_ref=rpm_ref,
            heat_tag="cpu",
        )
    )


def air_density_safe(build, _node: str) -> float:
    return air_density(build.ambient_c, build.altitude_m)


def _seal_area(build, name: str, geometric: float, seal_scale: float) -> float:
    level = int(build.seals.get(name, 3))
    level = min(5, max(1, level))
    if name == "side":
        if build.side_panel == "removed":
            level = 5
        elif build.side_panel == "mesh":
            level = max(level, 4)
    frac = SEAL_OPEN_FRACTION[level] * seal_scale
    cd = SEAL_CD[level]
    return max(geometric * frac, 1e-7), cd


def _add_panel_leaks(build, case, rho_ref, seal_scale, direct, add) -> None:
    targets = {
        "front": "gpu" if direct else "case",
        "top": "case",
        "bottom": "case",
        "side": "case",
        "seams": "case",
    }
    for name, geometric in case.leak_areas_m2.items():
        area, cd = _seal_area(build, name, geometric, seal_scale)
        target = targets.get(name, "case")
        add(
            Branch(
                id=f"leak-{name}",
                a=target,
                b=AMB,
                k=orifice_k(area, rho_ref, cd),
                k_lin=0.4,
                rho=rho_ref,
                kind="leak",
                label=f"{name} seal level {build.seals.get(name, 3)}",
            )
        )


def _add_spill(build, case, rho_ref, sample, add) -> None:
    from gpusim.calib import CABLE_K as cables
    from gpusim.calib import OBSTRUCTION_K as obst

    base = float(sample.get("spill_area_direct_m2", 0.045))
    if case.airflow_layout != "direct_front_to_gpu":
        base = float(sample.get("spill_area_mixed_m2", 0.012))
    mult = obst.get(build.obstruction, 1.0) * cables.get(build.cables, 1.0)
    area = base / mult
    add(
        Branch(
            id="spill",
            a="gpu",
            b="case",
            k=orifice_k(area, rho_ref, 0.75),
            k_lin=0.3,
            rho=rho_ref,
            kind="spill",
            label="GPU zone to main case volume",
        )
    )


def _add_rear_slots(build, case, rho_ref, seal_scale, shroud_on, sample, add) -> None:
    n_slots = case.horizontal_slots + case.vertical_slots
    geometric = n_slots * case.rear_slot_area_m2
    if shroud_on:
        frac = float(sample.get("shroud_bypass_fraction", 0.55))
        # Tape still closes holes the shroud would otherwise inhale.
        area, cd = _seal_area(build, "rear_slots", geometric, seal_scale)
        area = max(area, geometric * frac * min(seal_scale, 1.0) * 0.15)
        # Use the more open of "seal applied" and a shroud mouth, but if the
        # user sealed to level 1 the seal result is already tiny — keep it.
        level = int(build.seals.get("rear_slots", 4))
        if level <= 2:
            mouth = area
        else:
            mouth = geometric * frac
        add(
            Branch(
                id="rear-slots",
                a="gpu",
                b="plenum",
                k=orifice_k(mouth, rho_ref, 0.7),
                k_lin=0.4,
                rho=rho_ref,
                kind="rear-slot",
                label="Open slot mouths into the rear shroud plenum",
            )
        )
    else:
        area, cd = _seal_area(build, "rear_slots", geometric, seal_scale)
        reingest = float(sample.get("reingest_fraction", 0.22))
        add(
            Branch(
                id="rear-slots",
                a="gpu",
                b=AMB,
                k=orifice_k(area * (1.0 - reingest), rho_ref, cd),
                k_lin=0.4,
                rho=rho_ref,
                kind="rear-slot",
                label="Open rear slots exchanging with room air",
            )
        )
        add(
            Branch(
                id="rear-reingest",
                a="gpu",
                b="plume",
                k=orifice_k(max(area * reingest, 1e-6), rho_ref, cd),
                k_lin=0.4,
                rho=rho_ref,
                kind="reingest",
                label="Rear-slot reingestion of the exhaust plume",
            )
        )


def _add_shroud_fans(build, fans, rho_ref, ippc_scale, sample, add) -> None:
    shell = float(sample.get("shroud_shell_area_m2", 8.0e-4))
    add(
        Branch(
            id="shroud-shell",
            a="plenum",
            b=AMB,
            k=orifice_k(shell, rho_ref, 0.6),
            k_lin=0.4,
            rho=rho_ref,
            kind="shroud-leak",
            label="Shroud shell leakage",
        )
    )
    if build.shroud.mode != "on" or build.shroud.count <= 0:
        return
    fan = fans[build.shroud.fan]
    p_scale = ippc_scale if "ippc" in fan.id or "industrial" in fan.id else 1.0
    rpm = rpm_from_duty(fan.rpm_min, fan.rpm_max, build.shroud.duty)
    q, p, rpm, rpm_ref = _fan_qp(fan, rpm, build.shroud.count, p_scale)
    hole = 0.55 * (fan.size_mm / 1000.0) ** 2 * build.shroud.count
    add(
        Branch(
            id="shroud-fans",
            a="plenum",
            b=AMB,
            k=orifice_k(hole, rho_ref, 0.7),
            k_lin=1.0,
            rho=rho_ref,
            kind="shroud-fan",
            label=f"Rear shroud {build.shroud.count}× {fan.name}",
            q_tab=q,
            p_tab=p,
            rpm=rpm,
            rpm_ref=rpm_ref,
        )
    )


def _apply_buoyancy(branches, node_temp, t_amb, case) -> None:
    """Hot GPU-zone air wants to rise into the case. A small linear bias.

    ΔP ≈ ρ g H (T_zone − T_amb) / T_zone, applied by shifting k_lin on the spill
    branch. Off unless the build asks for it. The magnitude is usually < 1 Pa.
    """
    t_zone = node_temp.get("gpu", t_amb)
    height = max((case.height_mm if case else 500) / 1000.0 * 0.45, 0.15)
    rho = air_density(t_zone, 0.0)
    t_k = t_zone + 273.15
    dp = rho * 9.81 * height * (t_zone - t_amb) / max(t_k, 1.0)
    for br in branches:
        if br.id == "spill" and abs(t_zone - t_amb) > 0.2:
            # Positive dp pushes flow from gpu → case, i.e. reduces the required
            # pressure drop, which is a negative addition to P_a − P_b.
            br.k_lin = br.k_lin  # kept; encode as a fixed fan-like offset via rpm-less tab
            # Represent as an extra constant pressure using a flat fan curve.
            q = np.array([0.0, 0.2])
            # P_fan ≈ dp across a wide flow range (a weak constant source).
            br.q_tab = q
            br.p_tab = np.array([max(dp, 0.0), max(dp, 0.0) * 0.2])
            br.rpm = 1.0
            br.rpm_ref = 1.0
            break
