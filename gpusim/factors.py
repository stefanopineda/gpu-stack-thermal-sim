"""Factorial-sweep edits and the reference layouts used by tests and the CLI.

Card 1 stays the top horizontal card. The 4th card of Stefano's sweep stays in
a vertical slot; spacing only moves the three horizontal cards.
"""

from __future__ import annotations

from gpusim.library import Library, get_library
from gpusim.models import BuildCfg, GpuCfg, MountCfg

SWEEP_LEVELS = {
    "spacing": ("stacked", "gap1"),
    "pressure": ("high", "standard"),
    "shroud": ("off", "on"),
    "leakage": ("sealed", "leaky"),
}

STOCK = {
    "spacing": "stacked",
    "pressure": "standard",
    "shroud": "off",
    "leakage": "leaky",
}


def iter_cells():
    for spacing in SWEEP_LEVELS["spacing"]:
        for pressure in SWEEP_LEVELS["pressure"]:
            for shroud in SWEEP_LEVELS["shroud"]:
                for leakage in SWEEP_LEVELS["leakage"]:
                    yield {
                        "spacing": spacing,
                        "pressure": pressure,
                        "shroud": shroud,
                        "leakage": leakage,
                    }


def cell_id(cell: dict) -> str:
    return (
        f"s-{cell['spacing']}__p-{cell['pressure']}"
        f"__sh-{cell['shroud']}__l-{cell['leakage']}"
    )


def layout_slots(count: int, spacing: str, n_slots: int, width: int = 2) -> list[int]:
    step = width if spacing == "stacked" else width + 1
    slots: list[int] = []
    cursor = 1
    for _ in range(count):
        if cursor + width - 1 > n_slots:
            break
        slots.append(cursor)
        cursor += step
    if len(slots) < count and spacing != "stacked":
        return layout_slots(count, "stacked", n_slots, width)
    return slots


def apply_pressure(build: BuildCfg, mode: str) -> None:
    """high: every case fan and the radiator intake. standard: the build's own
    fan directions as saved (rev 4.1 — rev 4 forced top/rear to exhaust, which
    overrode a deliberate top intake), radiator exhaust."""
    if mode not in ("high", "standard"):
        raise ValueError(f"Unknown pressure mode '{mode}'")
    for mount in build.mounts:
        if mount.state == "fan" and mode == "high":
            mount.direction = "intake"
    if build.radiator and build.radiator.model:
        build.radiator.direction = "intake" if mode == "high" else "exhaust"


# Seal levels, rev 4 direction (1 open … 5 sealed; see calib.SEAL_OPEN_FRACTION).
# sealed: foil tape on the mesh around the fans, taped seams and slot mouths.
# leaky: realistic stock. Mesh + filter front and top, restricted floor,
# solid glass side, seams at small gaps. Rear slots at 3 (45 %): brackets are
# out, but roughly half of the slot openings sit behind the cards' own brackets.
LEAKAGE_SEALS = {
    "sealed": {"front": 4, "top": 4, "bottom": 5, "side": 5, "seams": 5, "rear_slots": 5},
    "leaky": {"front": 3, "top": 3, "bottom": 4, "side": 5, "seams": 4, "rear_slots": 3},
}


def apply_leakage(build: BuildCfg, mode: str) -> None:
    if mode not in LEAKAGE_SEALS:
        raise ValueError(f"Unknown leakage level '{mode}'")
    build.seals = dict(LEAKAGE_SEALS[mode])


def _set_curve(build: BuildCfg, fan_curve: str) -> None:
    for gpu in build.gpus:
        gpu.fan_curve = fan_curve


def apply_cell(
    build: BuildCfg,
    spacing: str,
    pressure: str,
    shroud: str,
    leakage: str,
    fan_curve: str = "stock",
    vertical_slot: str = "v2",
    library: Library | None = None,
) -> BuildCfg:
    """Return a new build: 3 horizontal cards + 1 vertical (when the case has one)."""
    lib = library or get_library()
    case = lib.cases[build.case]
    out = build.model_copy(deep=True)
    proto = out.gpus[0]
    card = lib.cards[proto.card]
    slots = layout_slots(3, spacing, case.horizontal_slots, card.slots)
    gpus = []
    for index, slot in enumerate(slots, start=1):
        gpus.append(
            GpuCfg(
                id=f"gpu{index}",
                slot=str(slot),
                card=proto.card,
                fan_curve=fan_curve,
                custom_curve=proto.custom_curve,
                power_limit_w=proto.power_limit_w,
                memory_clock_offset_mhz=proto.memory_clock_offset_mhz,
                core_clock_offset_mhz=proto.core_clock_offset_mhz,
                undervolt_mv=proto.undervolt_mv,
            )
        )
    if case.vertical_slots and case.vertical_positions:
        wanted = vertical_slot
        ids = [v.id for v in case.vertical_positions]
        slot_id = wanted if wanted in ids else ids[min(1, len(ids) - 1)]
        gpus.append(
            GpuCfg(
                id=f"gpu{len(gpus)+1}",
                slot=slot_id,
                card=proto.card,
                fan_curve=fan_curve,
                power_limit_w=proto.power_limit_w,
            )
        )
    out.gpus = gpus
    apply_pressure(out, pressure)
    apply_leakage(out, leakage)
    if shroud not in ("off", "on", "passive"):
        raise ValueError(f"Unknown shroud mode '{shroud}'")
    out.shroud.mode = shroud
    out.id = f"{build.id}__{cell_id({'spacing': spacing, 'pressure': pressure, 'shroud': shroud, 'leakage': leakage})}"
    out.name = f"{build.name} [{spacing}, {pressure}, shroud {shroud}, {leakage}]"
    return out


def close_packed(
    build: BuildCfg,
    count: int = 4,
    fan_curve: str = "stock",
    pressure: str = "standard",
    shroud: str = "off",
    leakage: str = "leaky",
    library: Library | None = None,
) -> BuildCfg:
    """All-horizontal stack with no empty slots. Anchor B uses count=4."""
    lib = library or get_library()
    case = lib.cases[build.case]
    out = build.model_copy(deep=True)
    proto = out.gpus[0]
    card = lib.cards[proto.card]
    slots = layout_slots(count, "stacked", case.horizontal_slots, card.slots)
    if len(slots) < count:
        raise ValueError(
            f"{case.id} has {case.horizontal_slots} slots; "
            f"cannot place {count} dual-slot cards."
        )
    out.gpus = [
        GpuCfg(
            id=f"gpu{i}",
            slot=str(slot),
            card=proto.card,
            fan_curve=fan_curve,
            power_limit_w=proto.power_limit_w,
        )
        for i, slot in enumerate(slots, start=1)
    ]
    apply_pressure(out, pressure)
    apply_leakage(out, leakage)
    out.shroud.mode = shroud
    out.id = f"{build.id}__close{count}"
    out.name = f"{build.name} [{count} close-packed horizontal]"
    return out


def open_air_build(
    card: str = "rtx-pro-6000-blackwell-maxq",
    fan_curve: str = "stock",
    power_w: float = 300,
    ambient_c: float = 25,
) -> BuildCfg:
    return BuildCfg(
        id="open-air",
        name="Single card in open air",
        case="open-air",
        open_air=True,
        ambient_c=ambient_c,
        gpus=[
            GpuCfg(
                id="gpu1",
                slot="1",
                card=card,
                fan_curve=fan_curve,
                power_limit_w=power_w,
            )
        ],
        notes="No case, no recirculation. Calibration reference.",
    )


def reference_build(case_id: str, library: Library | None = None) -> BuildCfg:
    """A small, solvable population of every case preset (convergence check)."""
    lib = library or get_library()
    case = lib.cases[case_id]
    card = lib.cards["rtx-pro-6000-blackwell-maxq"]
    n = 2 if case.horizontal_slots >= card.slots * 2 else 1
    slots = layout_slots(n, "stacked", case.horizontal_slots, card.slots)
    gpus = [
        GpuCfg(id=f"gpu{i}", slot=str(slot), card=card.id, fan_curve="stock", power_limit_w=300)
        for i, slot in enumerate(slots, start=1)
    ]
    mounts = []
    front = [m for m in case.mounts if m.panel == "front"]
    for index, layout in enumerate(front[: min(3, len(front))]):
        fan = "generic-140" if layout.size_mm >= 140 else "generic-120"
        if fan not in lib.fans:
            fan = "generic-120"
        mounts.append(
            MountCfg(
                id=layout.id,
                panel="front",
                size_mm=layout.size_mm,
                fan=fan if layout.size_mm in (120, 140, 170) else "generic-120",
                state="fan",
                direction="intake",
                duty=1.0,
            )
        )
    rear = [m for m in case.mounts if m.panel == "rear"]
    if rear:
        layout = rear[0]
        fan = "generic-140" if layout.size_mm >= 140 else "generic-120"
        mounts.append(
            MountCfg(
                id=layout.id,
                panel="rear",
                size_mm=layout.size_mm,
                fan=fan,
                state="fan",
                direction="exhaust",
                duty=1.0,
            )
        )
    build = BuildCfg(
        id=f"{case_id}-reference",
        name=f"{case.name} reference",
        case=case_id,
        ambient_c=25,
        gpus=gpus,
        mounts=mounts,
        radiator={
            "model": "arctic-360" if case.radiator_support.get("top") else None,
            "panel": "top",
            "direction": "exhaust",
            "fan": "arctic-p12-pwm-pst",
            "fan_count": 3,
        },
        cpu={"power_w": 125, "cooling": "water" if case.radiator_support.get("top") else "air"},
        shroud={"mode": "off", "fan": "noctua-nf-a14-ippc-3000", "count": 2, "duty": 1},
        obstruction="low",
        cables="clean",
        brackets_removed=True,
        side_panel=case.side_panel,
    )
    # Radiator only where the case lists top support. pydantic already coerced
    # the dict if we passed a model; BuildCfg.radiator is a model, so a dict
    # works via validation only at construct time — we passed a dict to the
    # field, pydantic accepts it.
    if not case.radiator_support.get("top"):
        build.radiator.model = None
    apply_leakage(build, "leaky")
    return build


def apply_scenario_step(build: BuildCfg, step, library: Library | None = None) -> BuildCfg:
    out = _scenario_layout(build, step, library)
    if getattr(step, "card", None):
        lib = library or get_library()
        card = lib.cards[step.card]
        for gpu in out.gpus:
            gpu.card = card.id
            gpu.power_limit_w = card.tbp_w
    if getattr(step, "power_limit_w", None):
        for gpu in out.gpus:
            gpu.power_limit_w = float(step.power_limit_w)
    if getattr(step, "fan_duty", None) is not None:
        duty = float(step.fan_duty)
        for gpu in out.gpus:
            gpu.fan_curve = "custom"
            gpu.custom_curve = [[0.0, duty], [100.0, duty]]
    intake = getattr(step, "shroud_intake", None)
    if intake:
        if intake not in ("open", "taped"):
            raise ValueError("shroud_intake must be open or taped")
        out.shroud.intake = intake
    return out


def _scenario_layout(build: BuildCfg, step, library: Library | None = None) -> BuildCfg:
    layout = step.layout
    fan_curve = step.fan_curve or "stock"
    pressure = step.pressure or "standard"
    shroud = step.shroud or "off"
    leakage = step.leakage or "leaky"
    if layout == "close4":
        return close_packed(build, 4, fan_curve, pressure, shroud, leakage, library)
    if layout in ("gap1_vertical", "stacked_vertical"):
        spacing = "gap1" if layout.startswith("gap") else "stacked"
        return apply_cell(
            build, spacing, pressure, shroud, leakage, fan_curve, library=library
        )
    if layout in ("keep", "optimal"):
        out = build.model_copy(deep=True)
        if step.pressure:
            apply_pressure(out, step.pressure)
        if step.leakage:
            apply_leakage(out, step.leakage)
        if step.shroud:
            out.shroud.mode = step.shroud
        if step.fan_curve:
            _set_curve(out, step.fan_curve)
        return out
    raise ValueError(f"Unknown scenario layout '{layout}'")
