"""Calibration bounds from SPEC rev 3 section 10.

Tolerances are applied to the nominal (non-Monte-Carlo) solution. Anchor A is
86 °C ± 3 °C. Anchor B requires an unthrottled hottest die at or above the
90 °C cutoff and throttle = True. Open air at 300 W must land in 75–85 °C.
"""

from __future__ import annotations

from gpusim.factors import apply_cell, close_packed, open_air_build
from gpusim.models import BuildCfg
from gpusim.solve import Solution, solve


def _check(name: str, ok: bool, detail: str) -> dict:
    return {"name": name, "pass": bool(ok), "detail": detail}


def evaluate_bounds(build: BuildCfg, library=None) -> dict:
    open_air = solve(open_air_build(), library)
    aggressive = solve(open_air_build(fan_curve="maxq_aggressive"), library)
    anchor_a = solve(
        apply_cell(build, "gap1", "standard", "off", "leaky", library=library),
        library,
    )
    anchor_b = solve(close_packed(build, 4, library=library), library)
    shroud_off = solve(
        apply_cell(build, "gap1", "standard", "off", "leaky", library=library),
        library,
        do_throttle=False,
    )
    shroud_on = solve(
        apply_cell(build, "gap1", "standard", "on", "leaky", library=library),
        library,
        do_throttle=False,
    )

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

    checks = [
        _check(
            "open_air_300w",
            75.0 <= open_die <= 85.0,
            f"single card open air die {open_die:.2f} °C (band 75–85, target ~83)",
        ),
        _check(
            "anchor_a",
            83.0 <= a_hot <= 89.0,
            f"anchor A hottest unthrottled die {a_hot:.2f} °C (86 ± 3)",
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
            "maxq_aggressive_open_air",
            aggr_die < 75.0,
            f"aggressive curve, open air, die {aggr_die:.2f} °C (under ~75)",
        ),
        _check(
            "shroud_raises_flow",
            flow_on > flow_off,
            f"mean blower flow {flow_off:.2f} CFM shroud off → {flow_on:.2f} CFM shroud on",
        ),
    ]
    return {
        "pass": all(item["pass"] for item in checks),
        "checks": checks,
        "open_air_c": open_die,
        "aggressive_c": aggr_die,
        "anchor_a_c": a_hot,
        "anchor_b_unthrottled_c": b_unth,
        "shroud_flow_cfm": {"off": flow_off, "on": flow_on},
    }


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
