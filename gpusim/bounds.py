"""Calibration bounds.

Tolerances are applied to the nominal (non-Monte-Carlo) solution. Anchor A is
the 2026-09-30 spaced, shroud-off soak: hottest die 89 °C ± 2 °C. Anchor B
requires the stacked full-power hottest die near that day's 93 °C soak, at or
above 90 °C, with the throttle flag set. Open air moved when ``nu_C`` was
refit to those soaks; the check keeps the new prediction from running away.
"""

from __future__ import annotations

from gpusim.factors import apply_cell, close_packed, open_air_build
from gpusim.models import BuildCfg
from gpusim.solve import Solution, solve


# Review-derived open-air targets at 25 °C ambient (see card presets).
FLOW_THROUGH_OPEN_AIR = {
    "rtx-5090-fe": (76.0, 575),
    "rtx-pro-6000-blackwell-workstation": (76.0, 600),
    "rtx-3090-fe": (68.0, 350),
}


def _check(name: str, ok: bool, detail: str) -> dict:
    return {"name": name, "pass": bool(ok), "detail": detail}


def evaluate_bounds(build: BuildCfg, library=None) -> dict:
    open_air = solve(open_air_build(), library)
    aggressive = solve(open_air_build(fan_curve="custom_accelerated"), library)
    anchor_a = solve(
        apply_cell(build, "gap1", "standard", "off", "leaky", library=library),
        library,
    )
    anchor_b = solve(close_packed(build, 4, library=library), library)
    shroud_off_build = apply_cell(build, "gap1", "standard", "off", "leaky", library=library)
    shroud_open_build = apply_cell(build, "gap1", "standard", "on", "leaky", library=library)
    shroud_open_build.shroud.intake = "open"
    shroud_taped_build = shroud_open_build.model_copy(deep=True)
    shroud_taped_build.shroud.intake = "taped"
    shroud_off = solve(shroud_off_build, library, do_throttle=False)
    shroud_on = solve(shroud_open_build, library, do_throttle=False)
    shroud_taped = solve(shroud_taped_build, library, do_throttle=False)

    open_die = open_air.cards[0].t_die_unthrottled_c
    aggr_die = aggressive.cards[0].t_die_unthrottled_c
    a_hot = anchor_a.hottest_unthrottled
    b_cards = anchor_b.cards
    b_unth = [c.t_die_unthrottled_c for c in b_cards]
    # Card order is top-to-bottom. Middle two of a 4-high stack are indexes 1 and 2.
    middle_hottest = (
        len(b_unth) >= 4
        and b_unth[1] > b_unth[0]
        and b_unth[1] > b_unth[3]
        and b_unth[2] > b_unth[0]
        and b_unth[2] > b_unth[3]
    )
    flow_off = sum(c.flow_cfm for c in shroud_off.cards) / len(shroud_off.cards)
    flow_on = sum(c.flow_cfm for c in shroud_on.cards) / len(shroud_on.cards)
    flow_taped = sum(c.flow_cfm for c in shroud_taped.cards) / len(shroud_taped.cards)

    def _positive(sol, kind: str) -> float:
        return sum(b["flow_cfm"] for b in sol.branches if b["kind"] == kind and b["flow_cfm"] > 0)

    bypass_open = _positive(shroud_on, "shroud-pull")
    crack_taped = _positive(shroud_taped, "shroud-crack")

    checks = [
        _check(
            "open_air_300w",
            84.0 <= open_die <= 93.0,
            f"single card open air die {open_die:.2f} °C "
            "(rev 3 target ~83; 2026-09-30 fin-path refit, band 84–93)",
        ),
        _check(
            "anchor_a",
            87.0 <= a_hot <= 91.0,
            f"anchor A hottest unthrottled die {a_hot:.2f} °C (2026-09-30 soak 89 ± 2)",
        ),
        _check(
            "anchor_b_throttle",
            max(b_unth) >= 90.0 and any(c.throttle for c in b_cards),
            f"anchor B unthrottled {['%.1f' % t for t in b_unth]} °C, "
            f"throttle {[c.throttle for c in b_cards]}",
        ),
        _check(
            "close_pack_middle_hottest",
            middle_hottest and max(b_unth) > 85.0,
            f"close-packed unthrottled dies {['%.1f' % t for t in b_unth]} °C "
            "(indexes 1 and 2 are the middle cards)",
        ),
        _check(
            "custom_accelerated_open_air",
            aggr_die < open_die - 8.0 and aggr_die < 84.0,
            f"custom accelerated curve (0 % at 25 °C → 100 % at 70 °C), open air, die {aggr_die:.2f} °C "
            f"(at least 8 °C below stock open air {open_die:.1f}, and under 84)",
        ),
        _check(
            "shroud_raises_flow",
            flow_taped > flow_off and flow_taped > flow_on,
            f"mean blower flow shroud off {flow_off:.2f} → open plenum {flow_on:.2f} → "
            f"taped mouths {flow_taped:.2f} CFM (same gap1 layout)",
        ),
        _check(
            "open_shroud_bypasses",
            bypass_open > crack_taped and bypass_open > 5.0,
            f"gap bypass {bypass_open:.1f} CFM open plenum vs crack {crack_taped:.2f} CFM taped",
        ),
    ]
    # Flow-through cards: one card in open air, stock curve, against the review
    # temperature each block was set to (docs/CALIBRATION.md). ±5 °C.
    for card_id, (target, power) in FLOW_THROUGH_OPEN_AIR.items():
        if library is not None and card_id not in library.cards:
            continue
        sol = solve(open_air_build(card=card_id, power_w=power), library)
        die = sol.cards[0].t_die_unthrottled_c
        checks.append(
            _check(
                f"open_air_{card_id}",
                abs(die - target) <= 5.0,
                f"{card_id} at {power} W, open air, stock curve: die {die:.2f} °C (target ~{target:.0f} ± 5)",
            )
        )
    checks += anchor_c_checks(library)
    return {
        "pass": all(item["pass"] for item in checks),
        "checks": checks,
        "open_air_c": open_die,
        "aggressive_c": aggr_die,
        "anchor_a_c": a_hot,
        "anchor_b_unthrottled_c": b_unth,
        "shroud_flow_cfm": {"off": flow_off, "on": flow_on, "taped": flow_taped},
    }


# Mike Bradley's published stack (anchor C): end cards only, °C.
ANCHOR_C = {0.8: (49.0, 79.0), 1.0: (49.0, 69.0)}


def anchor_c_checks(library=None) -> list[dict]:
    """4× RTX PRO 6000 Workstation touching, 275 W, unified GPU fan duty.

    Top card within ±5 °C of his reading, bottom within ±6 °C (his room
    temperature is not published; the model assumes 25 °C), and the stack
    must heat monotonically from the bottom up.
    """
    from gpusim.factors import apply_scenario_step
    from gpusim.library import get_library
    from gpusim.models import ScenarioStep

    lib = library or get_library()
    if "mike-bradley-dengen-x-station" not in lib.builds:
        return []
    out = []
    for duty, (bottom, top) in ANCHOR_C.items():
        step = ScenarioStep(id="c", title="c", talking_points=[], layout="keep", fan_duty=duty)
        sol = solve(apply_scenario_step(lib.builds["mike-bradley-dengen-x-station"], step, lib), lib)
        temps = [c.t_die_unthrottled_c for c in sol.cards]
        rising = all(a > b for a, b in zip(temps, temps[1:]))
        ok = abs(temps[0] - top) <= 5.0 and abs(temps[-1] - bottom) <= 6.0 and rising
        out.append(
            _check(
                f"anchor_c_fans_{int(duty * 100)}",
                ok,
                f"Mike Bradley stack, fans {duty:.0%}: top→bottom {['%.1f' % t for t in temps]} °C "
                f"(published top {top:.0f}, bottom {bottom:.0f}; rising bottom→top {rising})",
            )
        )
    return out


def bounds_markdown(report: dict, extra: list[dict] | None = None) -> str:
    lines = [
        "# Bounds check",
        "",
        "Nominal solutions. Monte Carlo bands are a separate uncertainty, not these pass/fail limits.",
        "",
        "| Check | Result | Detail |",
        "|---|---|---|",
    ]
    items = list(report["checks"]) + list(extra or [])
    for item in items:
        flag = "PASS" if item["pass"] else "FAIL"
        lines.append(f"| {item['name']} | {flag} | {item['detail']} |")
    lines.append("")
    lines.append(f"Overall: {'PASS' if report['pass'] and all(i['pass'] for i in (extra or [])) else 'FAIL'}")
    lines.append("")
    return "\n".join(lines)


def solution_energy_ok(sol: Solution, limit: float = 0.02) -> bool:
    return sol.energy_error <= limit and sol.residual_kg_s < 1e-5
