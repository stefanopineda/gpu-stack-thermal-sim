"""Slot geometry. Card 1 is the top card, closest to the CPU.

A dual-slot card plugged into slot s occupies s and s+1. Its blower inlet
faces the neighbouring slot above it (toward the CPU), which is either the
previous card's backplate, an empty slot, or the CPU-area clearance.
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


def gap_table(
    build: BuildCfg,
    case: CaseModel,
    cards: dict[str, CardModel],
) -> dict[str, dict]:
    """Per placed GPU: gap feeding the blower inlet, and who sits upstream."""
    ordered = sort_gpus(build)
    horizontals = [g for g in ordered if not is_vertical(g.slot)]
    lowest_id = horizontals[-1].id if horizontals else None
    info: dict[str, dict] = {}
    for gpu in ordered:
        card = cards[gpu.card]
        if is_vertical(gpu.slot):
            gap = max(case.clearance_above_top_mm, 22.0)
            state = gpu.gap_override or "open_slot"
            info[gpu.id] = {
                "gap_mm": gap,
                "state": state,
                "upstream": None,
                "lowest": False,
                "vertical": True,
                "thickness_mm": card.thickness_mm,
            }
            continue
        upstream = _nearest_above(gpu, horizontals)
        if upstream is None:
            gap = case.clearance_above_top_mm
            state = "open_slot"
        else:
            up_card = cards[upstream.card]
            empty = slot_number(gpu.slot) - (slot_number(upstream.slot) + up_card.slots)
            empty = max(empty, 0)
            slack = up_card.slots * case.slot_pitch_mm - up_card.thickness_mm
            gap = empty * case.slot_pitch_mm + max(slack, 0.4)
            if empty <= 0:
                state = "no_slot"
            elif build.brackets_removed:
                state = "open_slot"
            else:
                state = "blocked_slot"
        if gpu.gap_override:
            state = gpu.gap_override
        info[gpu.id] = {
            "gap_mm": float(gap),
            "state": state,
            "upstream": None if upstream is None else upstream.id,
            "lowest": gpu.id == lowest_id,
            "vertical": False,
            "thickness_mm": card.thickness_mm,
        }
    return info


def _nearest_above(gpu, horizontals):
    above = [
        other
        for other in horizontals
        if slot_number(other.slot) < slot_number(gpu.slot)
    ]
    if not above:
        return None
    return max(above, key=lambda other: slot_number(other.slot))


def inlet_area_m2(gap_mm: float, state: str, inlet_width_m: float, eye_m2: float) -> float:
    """Area of the slit feeding the blower eye. The eye itself is the ceiling."""
    gap_m = max(float(gap_mm), 0.3) / 1000.0
    area = inlet_width_m * gap_m
    if state == "blocked_slot":
        area *= 0.22
    elif state == "no_slot":
        area *= 0.85  # geometric gap already small; a little extra shroud overlap
    return float(min(area, eye_m2))
