"""Slot geometry. Card 1 is the top card, closest to the CPU.

A dual-slot card plugged into slot s occupies s and s+1. The blower fan face
points down, toward the case floor, in a standard ATX tower. The gap on that
side is whatever the slot map puts below the card: the next card, empty slots,
or the PSU-shroud clearance when nothing is below. The backplate / end opening
points up, toward the card above or the CPU-area clearance. There is no
special case for the lowest card.
"""

from __future__ import annotations

from gpusim.models import BuildCfg, CardModel, CaseModel

SLOT_PITCH_MM = 20.32


def is_vertical(slot: str) -> bool:
    return str(slot).lower().startswith("v")


def slot_number(slot: str) -> int:
    text = str(slot).lower()
    if text.startswith("v"):
        return int(text[1:])
    return int(text)


def sort_gpus(build: BuildCfg) -> list:
    """Top-to-bottom: horizontal slots ascending, then vertical slots."""

    def key(gpu):
        if is_vertical(gpu.slot):
            return (1, slot_number(gpu.slot))
        return (0, slot_number(gpu.slot))

    return sorted(build.gpus, key=key)


def _pair_gap(upper_slot: int, upper_slots: int, upper_thickness: float, lower_slot: int, pitch: float, brackets_removed: bool):
    """Air gap between the bottom face of the upper card and the top face of the lower one."""
    empty = lower_slot - (upper_slot + upper_slots)
    empty = max(empty, 0)
    slack = upper_slots * pitch - upper_thickness
    gap = empty * pitch + max(slack, 0.4)
    # A rear slot cover closes the opening in the rear wall, not the air gap
    # between two cards: the fan face still breathes the gap from the front and
    # the glass side. So covers do not change the inlet state (rev 4.1; rev 3–4
    # wrongly marked a covered gap as blocked_slot). blocked_slot is kept for an
    # explicit gap_override, e.g. cables stuffed between the cards.
    state = "no_slot" if empty <= 0 else "open_slot"
    return float(gap), state


def _floor_clearance_mm(build: BuildCfg, case: CaseModel) -> float:
    """Open distance under the lowest horizontal card, from the case, not from which card it is."""
    gap = float(case.psu_shroud_clearance_mm)
    if build.psu_location == "open" or not case.psu_shroud:
        gap *= 1.8
    return gap


def gap_table(
    build: BuildCfg,
    case: CaseModel,
    cards: dict[str, CardModel],
) -> dict[str, dict]:
    """Per placed GPU, the fan-side and backplate-side gaps from the slot map."""
    ordered = sort_gpus(build)
    horizontals = [g for g in ordered if not is_vertical(g.slot)]
    info: dict[str, dict] = {}
    for gpu in ordered:
        card = cards[gpu.card]
        faces = (card.inlet_faces or "both").lower()
        split = float(card.inlet_split if card.inlet_split is not None else 0.75)
        split = min(max(split, 0.05), 0.95)
        if faces == "floor":
            fan_frac, back_frac = 1.0, 0.0
        elif faces == "cpu":
            fan_frac, back_frac = 0.0, 1.0
        else:
            fan_frac, back_frac = split, 1.0 - split

        if is_vertical(gpu.slot):
            gap = float(case.vertical_inlet_gap_mm)
            state = gpu.gap_override or "open_slot"
            sides = []
            if fan_frac > 0:
                sides.append(_side("fan", gap, state, fan_frac, None))
            if back_frac > 0:
                sides.append(_side("backplate", gap, state, back_frac, None))
            info[gpu.id] = _record(card, True, sides, gpu.gap_override)
            # Off to the side: the exhaust face opens onto free air, no card above.
            info[gpu.id]["above"] = {"gap_mm": gap, "state": state, "neighbor": None}
            info[gpu.id]["below"] = {"gap_mm": gap, "state": state, "neighbor": None}
            continue

        below = _nearest_below(gpu, horizontals)
        above = _nearest_above(gpu, horizontals)
        pitch = case.slot_pitch_mm
        if below is None:
            floor_gap = _floor_clearance_mm(build, case)
            floor_state = "open_slot"
            floor_neighbor = None
        else:
            floor_gap, floor_state = _pair_gap(
                slot_number(gpu.slot),
                card.slots,
                card.thickness_mm,
                slot_number(below.slot),
                pitch,
                build.brackets_removed,
            )
            floor_neighbor = below.id
        if above is None:
            cpu_gap = float(case.clearance_above_top_mm)
            cpu_state = "open_slot"
            cpu_neighbor = None
        else:
            above_card = cards[above.card]
            cpu_gap, cpu_state = _pair_gap(
                slot_number(above.slot),
                above_card.slots,
                above_card.thickness_mm,
                slot_number(gpu.slot),
                pitch,
                build.brackets_removed,
            )
            cpu_neighbor = above.id
        if gpu.gap_override:
            floor_state = gpu.gap_override
        sides = []
        if fan_frac > 0:
            sides.append(_side("fan", floor_gap, floor_state, fan_frac, floor_neighbor))
        if back_frac > 0:
            sides.append(_side("backplate", cpu_gap, cpu_state, back_frac, cpu_neighbor))
        info[gpu.id] = _record(card, False, sides, gpu.gap_override)
        # Both faces, whatever the inlet split. A flow-through card exhausts
        # into the gap above; its fan side draws from the gap below.
        info[gpu.id]["above"] = {"gap_mm": float(cpu_gap), "state": cpu_state, "neighbor": cpu_neighbor}
        info[gpu.id]["below"] = {"gap_mm": float(floor_gap), "state": floor_state, "neighbor": floor_neighbor}
    return info


def _side(name: str, gap_mm: float, state: str, fraction: float, neighbor: str | None) -> dict:
    return {
        "name": name,
        "gap_mm": float(gap_mm),
        "state": state,
        "fraction": float(fraction),
        "neighbor": neighbor,
    }


def _record(card: CardModel, vertical: bool, sides: list[dict], override: str | None) -> dict:
    fan = next((s for s in sides if s["name"] == "fan"), None)
    primary = fan or (sides[0] if sides else {"gap_mm": 20.0, "state": "open_slot"})
    return {
        "gap_mm": primary["gap_mm"],
        "state": override or primary["state"],
        "vertical": vertical,
        "sides": sides,
        "thickness_mm": card.thickness_mm,
        "inlet_faces": card.inlet_faces,
        "cooler": card.cooler,
    }


def _nearest_above(gpu, horizontals):
    above = [other for other in horizontals if slot_number(other.slot) < slot_number(gpu.slot)]
    if not above:
        return None
    return max(above, key=lambda other: slot_number(other.slot))


def _nearest_below(gpu, horizontals):
    below = [other for other in horizontals if slot_number(other.slot) > slot_number(gpu.slot)]
    if not below:
        return None
    return min(below, key=lambda other: slot_number(other.slot))


def exit_area_m2(gap_mm: float, exit_width_m: float, cutout_m2: float) -> float:
    """Flow-through exhaust leaving the backplate side into the gap above."""
    gap_m = max(float(gap_mm), 0.3) / 1000.0
    return float(min(max(exit_width_m * gap_m, 1e-8), max(cutout_m2, 1e-8)))


def inlet_area_m2(gap_mm: float, state: str, inlet_width_m: float, eye_m2: float) -> float:
    """Slit area feeding one side of the blower eye. The eye share is the ceiling."""
    gap_m = max(float(gap_mm), 0.3) / 1000.0
    area = inlet_width_m * gap_m
    if state == "blocked_slot":
        area *= 0.22
    elif state == "no_slot":
        area *= 0.85
    return float(min(max(area, 1e-8), max(eye_m2, 1e-8)))
