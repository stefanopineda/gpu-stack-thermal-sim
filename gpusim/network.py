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

from gpusim.calib import (
    CABLE_INLET_K,
    CABLE_K,
    DEFAULT_SEALS,
    FILTER_K_AT_REF,
    OBSTRUCTION_K,
    SEAL_CD,
    SEAL_NAMES,
    SEAL_OPEN_FRACTION,
)
from gpusim.flow import Branch
from gpusim.layout import exit_area_m2, gap_table, inlet_area_m2, sort_gpus
from gpusim.models import BuildCfg, CaseModel
from gpusim.physics import air_density, fan_tables, orifice_k, quadratic_curve, rpm_from_duty, scale_parallel

AMB = "amb"

# What each branch kind is, in words, for the network view and the API.
ROLE = {
    "fan": "case fan: pressure source in series with its own impedance",
    "blank": "blanked mount (near-closed plate)",
    "orifice": "empty mount (open orifice)",
    "leak": "seal resistance (panel mesh / gaps)",
    "spill": "internal resistance: GPU zone → main case volume",
    "gap": "inter-card slot resistance (card inlet slit)",
    "blower": "GPU fan + heatsink fin-channel resistance",
    "gpu-fan": "GPU axial fans + heatsink fin-channel resistance",
    "up-exit": "flow-through exhaust into the gap above the card",
    "bracket": "rear bracket vent",
    "recirc": "blower exhaust short-circuit back into the GPU zone",
    "plume": "rear exhaust plume mixing into the room",
    "rear-slot": "open rear slot mouths",
    "reingest": "rear-slot reingestion of the exhaust plume",
    "shroud-fan": "rear shroud fans (pressure source)",
    "shroud-leak": "rear shroud shell leakage",
    "radiator": "radiator core + its fans",
    "cpu-cooler": "CPU tower cooler: fan + fin stack",
    "cpu-exit": "internal resistance: CPU cooler outlet → case",
    "bleed": "numerical bleed (regularisation, not a leak path)",
    "plume-ingest": "plume ingestion: lower card's exhaust into the upper card's intake",
}


def internal_k_mult(build: BuildCfg) -> float:
    """k multiplier for internal branches from obstruction and cable management."""
    return float(OBSTRUCTION_K.get(build.obstruction, 1.0) * CABLE_K.get(build.cables, 1.0))


def seal_level(build: BuildCfg, name: str) -> int:
    level = int(build.seals.get(name, DEFAULT_SEALS.get(name, 3)))
    level = min(5, max(1, level))
    if name == "side":
        if build.side_panel == "removed":
            level = 1
        elif build.side_panel == "mesh":
            level = min(level, 3)
    return level


def _fan_qp(fan, rpm: float, parallel: int, p_scale: float):
    q, p = fan_tables(list(zip(fan.pq_m3h, fan.pq_mmh2o)))
    p = p * p_scale
    q, p = scale_parallel(q, p, parallel)
    return q, p, rpm, fan.rpm_max


def _blower_qp(params: dict, duty: float):
    qmax_m3h = params["qmax_m3s"] * 3600.0
    pmax_mm = params["pmax_pa"] / 9.80665
    q, p = fan_tables(quadratic_curve(qmax_m3h, pmax_mm, n=11))
    # Duty is a fraction of max RPM (affinity Q ∝ duty). No floor: a curve
    # that asks for 0 % stops the fan (rev 4 custom_accelerated at 25 °C).
    rpm = max(float(duty), 0.0) * float(params["rpm_max"])
    return q, p, rpm, params["rpm_max"]


class Network:
    def __init__(self, branches: list[Branch], nodes: list[str], gaps: dict, ordered_ids: list[str]):
        self.branches = branches
        self.nodes = nodes
        self.gaps = gaps
        self.ordered_ids = ordered_ids
        # Interfaces at seal level 5: no branch, infinite resistance. Listed so
        # the network view can still draw them.
        self.sealed: list[dict] = []
        # (lower gpu, upper gpu, gap mm) pairs where the lower card's exhaust
        # jet points at the upper card's fan face.
        self.plume_pairs: list[tuple[str, str, float]] = []
        self.cooler: dict[str, str] = {}

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

    air_cpu = build.cpu.cooling == "air"
    if build.cpu.cooling == "water" and not build.radiator.model and build.cpu.power_w > 0:
        raise ValueError(
            "CPU is water-cooled but the build has no radiator. "
            "Set radiator.model or switch cpu.cooling to 'air'."
        )
    if air_cpu:
        bleed("cpu")
        _add_cpu_cooler(build, fans, rho_ref, rho_for, sample, add)
    _add_mounts(
        build, case, fans, intake_node, rho_ref, rho_for, ippc_scale, sample, add, air_cpu,
    )
    _add_radiator(build, case, fans, radiators, rho_ref, ippc_scale, sample, add, intake_node)
    sealed: list[dict] = []
    _add_panel_leaks(build, case, rho_ref, seal_scale, direct, add, sealed)
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

    cooler: dict[str, str] = {}
    for gpu in sort_gpus(build):
        params = dict(sample.get("cards", {}).get(gpu.card, {}))
        # caller merges card tuning; sample['cards'][id] is a full dict when MC-ing
        if not params:
            from gpusim.calib import card_tuning

            params = card_tuning(gpu.card)
        card = cards[gpu.card]
        through = card.cooler == "flow_through"
        cooler[gpu.id] = card.cooler
        gap = gaps[gpu.id]
        bleed(f"cin-{gpu.id}")
        _add_inlet_sides(gpu, gap, params, rho_ref, rho_for, add, CABLE_INLET_K.get(build.cables, 1.0))
        q, p, rpm, rpm_ref = _blower_qp(params, duties.get(gpu.id, 0.7))
        add(
            Branch(
                id=f"blower-{gpu.id}",
                a=f"cin-{gpu.id}",
                b=f"cex-{gpu.id}",
                k=float(params["channel_k"]),
                k_lin=5.0,
                rho=rho_for(f"cin-{gpu.id}"),
                kind="gpu-fan" if through else "blower",
                label=f"{gpu.id} {'axial fans' if through else 'blower'} and fin channel",
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
        if through:
            above = gap.get("above") or {"gap_mm": 30.0, "state": "open_slot", "neighbor": None}
            area = exit_area_m2(above["gap_mm"], params["exit_width_m"], params["exit_area_m2"])
            toward = above.get("neighbor") or ("free air" if gap.get("vertical") else "CPU area")
            # The jet rises past the card into the upper case volume, not back
            # into the fresh GPU zone the cards breathe from. The share the
            # card above swallows is the plume overlay in thermal.py.
            add(
                Branch(
                    id=f"upexit-{gpu.id}",
                    a=f"cex-{gpu.id}",
                    b="case",
                    k=orifice_k(area, rho_ref, 0.65),
                    k_lin=1.0,
                    rho=rho_for(f"cex-{gpu.id}"),
                    kind="up-exit",
                    label=(
                        f"{gpu.id} exhaust up through the backplate side "
                        f"({above['gap_mm']:.1f} mm toward {toward})"
                    ),
                )
            )
        elif not shroud_on:
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

    # A flow-through card's jet points at the fan face of the card directly above.
    pairs = []
    for gpu in sort_gpus(build):
        if cooler.get(gpu.id) != "flow_through":
            continue
        above = gaps[gpu.id].get("above") or {}
        upper = above.get("neighbor")
        if upper and not gaps[gpu.id].get("vertical"):
            pairs.append((gpu.id, upper, float(above["gap_mm"])))

    if build.buoyancy:
        _apply_buoyancy(branches, node_temp, t_ref, case)

    net = Network(branches, sorted(nodes), gaps, ordered)
    net.sealed = sealed
    net.plume_pairs = pairs
    net.cooler = cooler
    return net


def _open_air(build, cards, duties, sample, rho_ref, add, bleed, nodes, branches) -> Network:
    from gpusim.calib import card_tuning
    from gpusim.layout import sort_gpus

    gaps = {}
    ordered = []
    cooler = {}
    for gpu in sort_gpus(build):
        params = dict(sample.get("cards", {}).get(gpu.card) or card_tuning(gpu.card))
        cooler[gpu.id] = cards[gpu.card].cooler
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
                kind="gpu-fan" if cards[gpu.card].cooler == "flow_through" else "blower",
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
        if cards[gpu.card].cooler == "flow_through":
            add(
                Branch(
                    id=f"upexit-{gpu.id}",
                    a=f"cex-{gpu.id}",
                    b=AMB,
                    k=orifice_k(params["exit_area_m2"], rho_ref, 0.65),
                    k_lin=1.0,
                    rho=rho_ref,
                    kind="up-exit",
                    label=f"{gpu.id} open-air exhaust through the backplate side",
                )
            )
        gaps[gpu.id] = {
            "gap_mm": 80.0,
            "state": "open_slot",
            "vertical": False,
            "inlet_faces": "both",
            "cooler": cards[gpu.card].cooler,
            "above": {"gap_mm": 80.0, "state": "open_slot", "neighbor": None},
            "below": {"gap_mm": 80.0, "state": "open_slot", "neighbor": None},
            "sides": [
                {
                    "name": "fan",
                    "gap_mm": 80.0,
                    "state": "open_slot",
                    "fraction": 1.0,
                    "neighbor": None,
                }
            ],
        }
        ordered.append(gpu.id)
    net = Network(branches, sorted(nodes), gaps, ordered)
    net.cooler = cooler
    return net


def _add_inlet_sides(gpu, gap, params, rho_ref, rho_for, add, k_mult: float = 1.0) -> None:
    """One orifice per inlet face. Area is the slot-map slit, capped by that face's share of the eye."""
    eye = float(params["inlet_eye_m2"])
    width = float(params["inlet_width_m"])
    sides = gap.get("sides") or []
    if not sides:
        sides = [{"name": "fan", "gap_mm": gap["gap_mm"], "state": gap["state"], "fraction": 1.0, "neighbor": None}]
    for side in sides:
        share = eye * float(side["fraction"])
        area = inlet_area_m2(side["gap_mm"], side["state"], width, share)
        neighbor = side.get("neighbor") or "open"
        add(
            Branch(
                id=f"gap-{gpu.id}-{side['name']}",
                a="gpu",
                b=f"cin-{gpu.id}",
                k=orifice_k(area, rho_ref, 0.62) * k_mult,
                k_lin=2.0,
                rho=rho_for("gpu"),
                kind="gap",
                label=(
                    f"{gpu.id} {side['name']} inlet ({side['state']}, "
                    f"{side['gap_mm']:.1f} mm, toward {neighbor})"
                ),
            )
        )


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


def _panel_target(panel: str, intake_node: str, air_cpu: bool = False) -> str:
    if panel == "front":
        return intake_node
    if panel == "bottom":
        return "gpu"
    if panel == "rear" and air_cpu:
        # The rear fan sits right behind a tower cooler in nearly every build.
        return "cpu"
    return "case"


def _add_mounts(build, case, fans, intake_node, rho_ref, rho_for, ippc_scale, sample, add, air_cpu=False) -> None:
    cage = build.drive_cage == "present"
    for mount in _resolved_mounts(build, case):
        if mount.state == "radiator":
            continue
        target = _panel_target(mount.panel, intake_node, air_cpu)
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


def _add_radiator(build, case, fans, radiators, rho_ref, ippc_scale, sample, add, intake_node="case") -> None:
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
    # Front radiator breathes the same volume the front fans feed; bottom
    # sits under the cards; top (and legacy rear/side) is the main volume.
    inside = {"front": intake_node, "bottom": "gpu"}.get(rad_cfg.panel, "case")
    if rad_cfg.direction == "intake":
        a, b = AMB, inside
    else:
        a, b = inside, AMB
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
            heat_tag="cpu" if build.cpu.cooling == "water" else None,
        )
    )


def air_density_safe(build, _node: str) -> float:
    return air_density(build.ambient_c, build.altitude_m)


def _seal_area(build, name: str, geometric: float, seal_scale: float):
    level = seal_level(build, name)
    frac = min(SEAL_OPEN_FRACTION[level] * seal_scale, 1.0)
    cd = SEAL_CD[level]
    return geometric * frac, cd


def _add_panel_leaks(build, case, rho_ref, seal_scale, direct, add, sealed=None) -> None:
    targets = {
        "front": "gpu" if direct else "case",
        "top": "case",
        "bottom": "case",
        "side": "case",
        "seams": "case",
    }
    for name, geometric in case.leak_areas_m2.items():
        level = seal_level(build, name)
        area, cd = _seal_area(build, name, geometric, seal_scale)
        target = targets.get(name, "case")
        if area <= 0.0:
            # Level 5: solid glass or metal, taped. No branch; R = ∞.
            if sealed is not None:
                sealed.append({"id": f"leak-{name}", "a": target, "b": AMB, "level": level, "label": f"{name}: {SEAL_NAMES[level]}"})
            continue
        add(
            Branch(
                id=f"leak-{name}",
                a=target,
                b=AMB,
                k=orifice_k(area, rho_ref, cd),
                k_lin=0.4,
                rho=rho_ref,
                kind="leak",
                label=f"{name} seal level {level} ({SEAL_NAMES[level]}, {SEAL_OPEN_FRACTION[level]:.0%} open)",
            )
        )


def _add_cpu_cooler(build, fans, rho_ref, rho_for, sample, add) -> None:
    """Air-cooled CPU: tower fan + fin stack from the case into the cooler outlet."""
    cpu = build.cpu
    fan_id = cpu.cooler_fan if cpu.cooler_fan in fans else "generic-140"
    fan = fans[fan_id]
    rpm = rpm_from_duty(fan.rpm_min, fan.rpm_max, cpu.cooler_duty)
    q, p, rpm, rpm_ref = _fan_qp(fan, rpm, max(int(cpu.cooler_fan_count), 1), 1.0)
    k_hs = float(cpu.heatsink_k if cpu.heatsink_k is not None else sample.get("cpu_heatsink_k", 2.5e4))
    add(
        Branch(
            id="cpu-cooler",
            a="case",
            b="cpu",
            k=k_hs,
            k_lin=2.0,
            rho=rho_for("case"),
            kind="cpu-cooler",
            label=f"CPU tower cooler, {cpu.cooler_fan_count}× {fan.name}, {cpu.power_w:.0f} W",
            q_tab=q,
            p_tab=p,
            rpm=rpm,
            rpm_ref=rpm_ref,
            heat_tag="cpu",
        )
    )
    area = float(sample.get("cpu_exit_area_m2", 0.03))
    add(
        Branch(
            id="cpu-exit",
            a="cpu",
            b="case",
            k=orifice_k(area, rho_ref, 0.75) * internal_k_mult(build),
            k_lin=0.3,
            rho=rho_for("cpu"),
            kind="cpu-exit",
            label="CPU cooler outlet back into the case volume",
        )
    )


def _add_spill(build, case, rho_ref, sample, add) -> None:
    base = float(sample.get("spill_area_direct_m2", 0.045))
    if case.airflow_layout != "direct_front_to_gpu":
        base = float(sample.get("spill_area_mixed_m2", 0.012))
    add(
        Branch(
            id="spill",
            a="gpu",
            b="case",
            k=orifice_k(base, rho_ref, 0.75) * internal_k_mult(build),
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
        frac = float(sample.get("shroud_bypass_fraction", 0.04))
        # Tape still closes holes the shroud would otherwise inhale.
        area, cd = _seal_area(build, "rear_slots", geometric, seal_scale)
        area = max(area, geometric * 1e-4)
        # Taped slots (level 4–5) keep the seal result. Otherwise the open
        # mouths bypass into the plenum through the shroud's baffled fraction.
        level = seal_level(build, "rear_slots")
        if level >= 4:
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
        if area <= 0.0:
            return
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
