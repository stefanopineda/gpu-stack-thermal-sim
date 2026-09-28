"""16-cell factorial on a build, plus the stock row and the open-air reference."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from gpusim.bounds import bounds_markdown, evaluate_bounds, solution_energy_ok
from gpusim.factors import STOCK, apply_cell, cell_id, iter_cells, open_air_build
from gpusim.library import Library, get_library
from gpusim.models import BuildCfg
from gpusim.plots import write_plots
from gpusim.solve import solve, solve_monte_carlo


def _row(label: str, cell: dict | None, sol, mc_rows=None) -> dict:
    row = {
        "config": label,
        "spacing": None if cell is None else cell["spacing"],
        "pressure": None if cell is None else cell["pressure"],
        "shroud": None if cell is None else cell["shroud"],
        "leakage": None if cell is None else cell["leakage"],
        "case_pressure_pa": sol.case_pressure_pa,
        "energy_error": sol.energy_error,
        "residual_kg_s": sol.residual_kg_s,
        "converged": sol.converged,
        "solve_time_s": sol.solve_time_s,
        "hottest_die_c": sol.hottest_die,
        "hottest_unthrottled_c": sol.hottest_unthrottled,
        "mean_die_c": sol.mean_die,
        "any_throttle": any(c.throttle for c in sol.cards),
    }
    for index, card in enumerate(sol.cards, start=1):
        row[f"t_die_{index}_c"] = card.t_die_c
        row[f"t_die_unthrottled_{index}_c"] = card.t_die_unthrottled_c
        row[f"t_mem_{index}_c"] = card.t_mem_c
        row[f"t_exh_{index}_c"] = card.t_exh_c
        row[f"flow_cfm_{index}"] = card.flow_cfm
        row[f"mass_kg_s_{index}"] = card.mass_kg_s
        row[f"duty_{index}"] = card.duty
        row[f"throttle_{index}"] = card.throttle
        row[f"power_w_{index}"] = card.power_w
        row[f"slot_{index}"] = card.slot
    if mc_rows:
        for index in range(1, len(sol.cards) + 1):
            samples = [r.cards[index - 1].t_die_unthrottled_c for r in mc_rows]
            row[f"mc_p05_die_{index}_c"] = float(np.percentile(samples, 5))
            row[f"mc_p95_die_{index}_c"] = float(np.percentile(samples, 95))
        hottest = [r.hottest_unthrottled for r in mc_rows]
        row["mc_p05_hottest_c"] = float(np.percentile(hottest, 5))
        row["mc_p95_hottest_c"] = float(np.percentile(hottest, 95))
    return row


def _rank_key(row: dict):
    return (
        row["hottest_die_c"],
        row["hottest_unthrottled_c"],
        row["mean_die_c"],
        row["config"],
    )


def results_markdown(frame: pd.DataFrame, build_name: str) -> str:
    ranked = frame[frame["config"] != "open-air"].sort_values(
        ["hottest_die_c", "hottest_unthrottled_c", "mean_die_c", "config"]
    )
    lines = [
        f"# Sweep results — {build_name}",
        "",
        "Ranked by throttled hottest die, then unthrottled hottest die, then mean die.",
        "Lower is better. Throttled equilibrium sits on the cutoff, so the unthrottled",
        "column is what separates two configs that both hit 90 °C.",
        "",
        "Typical accuracy ±5–10 °C absolute. Trust the order more than the number.",
        "GPU water blocks are out of scope.",
        "",
        "| Rank | Config | Hottest °C | Unthrottled °C | Mean °C | Case Pa | Throttle |",
        "|---|---|---:|---:|---:|---:|---|",
    ]
    for rank, (_, row) in enumerate(ranked.iterrows(), start=1):
        lines.append(
            f"| {rank} | `{row['config']}` | {row['hottest_die_c']:.1f} | "
            f"{row['hottest_unthrottled_c']:.1f} | {row['mean_die_c']:.1f} | "
            f"{row['case_pressure_pa']:.1f} | {row['any_throttle']} |"
        )
    open_rows = frame[frame["config"] == "open-air"]
    if len(open_rows):
        o = open_rows.iloc[0]
        lines += [
            "",
            f"Open-air reference (not ranked): die {o['hottest_unthrottled_c']:.1f} °C.",
        ]
    lines.append("")
    return "\n".join(lines)


def write_hypothesis(frame: pd.DataFrame, path: Path, mc: int) -> None:
    stock = frame[frame["config"] == "stock"]
    if stock.empty:
        return
    base = float(stock.iloc[0]["hottest_unthrottled_c"])
    cells = frame[~frame["config"].isin(["stock", "open-air"])].copy()
    cells["delta"] = cells["hottest_unthrottled_c"] - base
    # Prefer configs that actually change something and are cooler.
    cooler = cells.sort_values(["hottest_unthrottled_c", "mean_die_c"]).head(5)
    lines = [
        "# What to test on the real machine",
        "",
        "The model is a hypothesis generator. These are the cells most worth a Saturday",
        "on Stefano's Meshify, cheapest and most informative first. Deltas are versus",
        f"the stock cell (stacked, standard pressure, shroud off, leaky), whose",
        f"unthrottled hottest die is {base:.1f} °C.",
        "",
        "Monte Carlo sample count for the bands below: "
        + (str(mc) if mc else "not run (nominal only)")
        + ".",
        "",
    ]
    # Order the narrative by how easy the change is, not only by predicted °C.
    ease = {
        "gap1": "Move cards apart by one slot. No parts.",
        "shroud on": "Fit the rear shroud and its two fans. Hardware already in hand.",
        "fan curve": "Raise the GPU fan cap in the vendor tool. No hardware.",
        "sealed": "Tape panel gaps. Reversible, fiddly.",
        "high": "Flip the radiator and the rear fan to intake. A few screws.",
    }
    steps = []
    for _, row in cooler.iterrows():
        steps.append(row)
    # Present gap1 first if present, then shroud, then the coldest remaining.
    def sort_ease(row):
        name = row["config"]
        if "gap1" in name and "sh-off" in name:
            return (0, row["hottest_unthrottled_c"])
        if "sh-on" in name:
            return (1, row["hottest_unthrottled_c"])
        if row["pressure"] == "high":
            return (3, row["hottest_unthrottled_c"])
        return (2, row["hottest_unthrottled_c"])

    ordered = sorted(steps, key=sort_ease)
    for index, row in enumerate(ordered, start=1):
        delta = row["hottest_unthrottled_c"] - base
        band = ""
        if "mc_p05_hottest_c" in row and pd.notna(row["mc_p05_hottest_c"]):
            band = (
                f" Monte Carlo hottest-die band "
                f"{row['mc_p05_hottest_c']:.1f}–{row['mc_p95_hottest_c']:.1f} °C."
            )
        why = []
        if row["spacing"] == "gap1":
            why.append(ease["gap1"])
        if row["shroud"] == "on":
            why.append(ease["shroud on"])
        if row["pressure"] == "high":
            why.append(ease["high"])
        if row["leakage"] == "sealed":
            why.append(ease["sealed"])
        lines += [
            f"## {index}. `{row['config']}`",
            "",
            f"Predicted unthrottled hottest die {row['hottest_unthrottled_c']:.1f} °C "
            f"({delta:+.1f} °C vs stock). Throttled equilibrium {row['hottest_die_c']:.1f} °C."
            + band,
            "",
            "Why it should move: " + (" ".join(why) or "Combined factor change."),
            "",
        ]
    lines += [
        "## Suggested order",
        "",
        "1. Spacing (gap1, shroud still off). Confirms anchor A against anchor B with no new parts.",
        "2. Shroud on, same spacing. Isolates the plenum fans.",
        "3. GPU fan curve to maxq_aggressive, which is not a sweep factor — do it on the winning geometry.",
        "4. Only then tape the case or flip the radiator. Those fight each other (CPU heat vs recirculation).",
        "",
        "Confidence is higher for the order than for the absolute degree. If two neighbouring",
        "cells differ by less than about 3 °C, treat them as a tie until the bench says otherwise.",
        "",
    ]
    path.write_text("\n".join(lines))


def resolve_plots_dir(out_dir: str | Path, plots_dir: str | Path | None) -> Path:
    """Default plots/<build> only when --out is the default results directory.

    A custom --out keeps the charts under that tree so a hand-written
    HYPOTHESIS.md at the repo root is not the only thing a sweep can clobber,
    and so plots travel with the tables.
    """
    if plots_dir is not None:
        return Path(plots_dir)
    out = Path(out_dir)
    try:
        default = out.resolve() == Path("results").resolve()
    except OSError:
        default = out == Path("results")
    if default:
        return Path("plots")
    return out / "plots"


def run_sweep(
    build: BuildCfg | None = None,
    build_id: str = "meshify2xl-stefano",
    mc: int = 200,
    out_dir: str | Path = "results",
    plots_dir: str | Path | None = None,
    seed: int = 12345,
    library: Library | None = None,
    write_hypothesis_to: str | Path | None = None,
) -> pd.DataFrame:
    lib = library or get_library()
    build = build or lib.builds[build_id]
    rows = []
    solutions = {}
    for cell in iter_cells():
        label = cell_id(cell)
        configured = apply_cell(build, library=lib, **cell)
        sol = solve(configured, lib)
        mc_rows = solve_monte_carlo(configured, n=mc, seed=seed, library=lib) if mc else None
        rows.append(_row(label, cell, sol, mc_rows))
        solutions[label] = sol
        if cell == STOCK:
            rows.append(_row("stock", cell, sol, mc_rows))
            solutions["stock"] = sol
    air = solve(open_air_build(), lib)
    rows.append(_row("open-air", None, air, None))
    solutions["open-air"] = air

    frame = pd.DataFrame(rows)
    out = Path(out_dir) / build.id
    plot_root = resolve_plots_dir(out_dir, plots_dir) / build.id
    out.mkdir(parents=True, exist_ok=True)
    plot_root.mkdir(parents=True, exist_ok=True)
    frame.to_csv(out / "results.csv", index=False)
    (out / "results.md").write_text(results_markdown(frame, build.name))

    report = evaluate_bounds(build, lib)
    extra = []
    for label, sol in solutions.items():
        if label == "open-air":
            continue
        ok = sol.converged and solution_energy_ok(sol)
        extra.append(
            {
                "name": f"cell:{label}",
                "pass": ok,
                "detail": (
                    f"converged={sol.converged}, residual={sol.residual_kg_s:.2e} kg/s, "
                    f"energy error={sol.energy_error:.3%}"
                ),
            }
        )
    report["pass"] = report["pass"] and all(item["pass"] for item in extra)
    (out / "bounds_check.json").write_text(json.dumps({"summary": report["pass"], "checks": report["checks"] + extra}, indent=2))
    (out / "bounds_check.md").write_text(bounds_markdown(report, extra))
    write_plots(frame, plot_root, build, lib)
    # The curated HYPOTHESIS.md at the repo root is hand-written. The sweep
    # only emits a generated sibling next to the tables.
    auto_path = Path(write_hypothesis_to) if write_hypothesis_to else out / "hypothesis_auto.md"
    write_hypothesis(frame, auto_path, mc)
    if not report["pass"]:
        failed = [c["name"] for c in report["checks"] + extra if not c["pass"]]
        # Loud, but the files are still written so the miss is inspectable.
        print("BOUNDS CHECK FAILED:", ", ".join(failed))
    return frame
