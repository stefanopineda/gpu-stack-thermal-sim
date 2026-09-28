"""Coarse search for an air-cooled layout. Water blocks are not candidates."""

from __future__ import annotations

import numpy as np

from gpusim.factors import apply_leakage, apply_pressure, layout_slots, reference_build
from gpusim.library import get_library
from gpusim.models import GpuCfg
from gpusim.solve import solve, solve_monte_carlo


def _layouts(case, count: int, width: int):
    found = []
    stacked = layout_slots(count, "stacked", case.horizontal_slots, width)
    if len(stacked) == count:
        found.append(("horizontal-stacked", stacked, None))
    gapped = layout_slots(count, "gap1", case.horizontal_slots, width)
    if len(gapped) == count and gapped != stacked:
        found.append(("horizontal-gap1", gapped, None))
    if case.vertical_positions and count >= 2:
        for spacing, name in (("gap1", "gap-plus-vertical"), ("stacked", "stack-plus-vertical")):
            horizontal = layout_slots(count - 1, spacing, case.horizontal_slots, width)
            if len(horizontal) == count - 1:
                slot = case.vertical_positions[min(1, len(case.vertical_positions) - 1)].id
                found.append((name, horizontal, slot))
    # De-duplicate identical slot maps.
    unique = []
    seen = set()
    for name, slots, vertical in found:
        key = (tuple(slots), vertical)
        if key in seen:
            continue
        seen.add(key)
        unique.append((name, slots, vertical))
    return unique


def _base_for(case_id: str, library):
    if case_id == "meshify2xl" and "meshify2xl-stefano" in library.builds:
        base = library.builds["meshify2xl-stefano"].model_copy(deep=True)
    else:
        base = reference_build(case_id, library)
    base.illustrative_mock = False
    return base


def optimize(cards: int, case_id: str = "meshify2xl", mc: int = 200, seed: int = 12345, library=None) -> dict:
    if cards < 1 or cards > 8:
        raise ValueError("Card count must be between 1 and 8.")
    lib = library or get_library()
    if case_id not in lib.cases:
        raise ValueError(f"Unknown case '{case_id}'. Known: {', '.join(sorted(lib.cases))}")
    case = lib.cases[case_id]
    base = _base_for(case_id, lib)
    card_id = base.gpus[0].card
    width = lib.cards[card_id].slots
    layouts = _layouts(case, cards, width)
    if not layouts:
        raise ValueError(f"{case.name} cannot hold {cards} dual-slot cards.")

    best = None
    tried = 0
    for name, slots, vertical in layouts:
        for shroud in ("off", "on"):
            for pressure in ("standard", "high"):
                for leakage in ("leaky", "sealed"):
                    for curve in ("stock", "maxq_aggressive"):
                        trial = base.model_copy(deep=True)
                        gpus = []
                        for index, slot in enumerate(slots, start=1):
                            gpus.append(
                                GpuCfg(
                                    id=f"gpu{index}",
                                    slot=str(slot),
                                    card=card_id,
                                    fan_curve=curve,
                                    power_limit_w=300,
                                )
                            )
                        if vertical:
                            gpus.append(
                                GpuCfg(
                                    id=f"gpu{len(gpus)+1}",
                                    slot=vertical,
                                    card=card_id,
                                    fan_curve=curve,
                                    power_limit_w=300,
                                )
                            )
                        trial.gpus = gpus
                        trial.shroud.mode = shroud
                        apply_pressure(trial, pressure)
                        apply_leakage(trial, leakage)
                        trial.id = f"opt-{name}-{shroud}-{pressure}-{leakage}-{curve}"
                        trial.name = trial.id
                        sol = solve(trial, lib, do_throttle=False, outer=5)
                        tried += 1
                        score = (sol.hottest_unthrottled, sol.mean_die, sol.hottest_die)
                        if best is None or score < best[0]:
                            best = (score, trial, sol, {
                                "layout": name,
                                "slots": [str(s) for s in slots] + ([vertical] if vertical else []),
                                "shroud": shroud,
                                "pressure": pressure,
                                "leakage": leakage,
                                "fan_curve": curve,
                            })
    assert best is not None
    _, winner, nominal, desc = best
    # Uncertainty on the winner only. The search itself is nominal.
    mc_summary = None
    if mc:
        draws = solve_monte_carlo(winner, n=mc, seed=seed, library=lib, outer=4)
        hottest = np.array([d.hottest_unthrottled for d in draws])
        mc_summary = {
            "n": mc,
            "seed": seed,
            "hottest_p05_c": float(np.percentile(hottest, 5)),
            "hottest_p95_c": float(np.percentile(hottest, 95)),
            "per_card_p05_c": [
                float(np.percentile([d.cards[i].t_die_unthrottled_c for d in draws], 5))
                for i in range(len(nominal.cards))
            ],
            "per_card_p95_c": [
                float(np.percentile([d.cards[i].t_die_unthrottled_c for d in draws], 95))
                for i in range(len(nominal.cards))
            ],
        }
    solved = solve(winner, lib)
    return {
        "case": case_id,
        "cards": cards,
        "tried": tried,
        "description": desc,
        "illustrative_mock": bool(winner.illustrative_mock),
        "note": (
            "Air-cooled search only. GPU water blocks are out of scope. "
            "Ranked by unthrottled hottest die, then mean die."
        ),
        "hottest_die_c": solved.hottest_die,
        "hottest_unthrottled_c": solved.hottest_unthrottled,
        "mean_die_c": solved.mean_die,
        "case_pressure_pa": solved.case_pressure_pa,
        "per_card": [c.__dict__ for c in solved.cards],
        "monte_carlo": mc_summary,
        "build": winner.model_dump(),
    }
