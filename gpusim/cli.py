"""Command line for the air-cooled multi-GPU simulator."""

from __future__ import annotations

from pathlib import Path

import typer

from gpusim import __version__

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help=(
        "Air-cooled multi-GPU airflow and temperature simulator (not CFD). "
        "GPU water blocks are out of scope. Temperatures are Celsius."
    ),
)


def _echo_solution(sol) -> None:
    typer.echo(
        f"{sol.build_id}: hottest {sol.hottest_die:.1f} °C "
        f"(unthrottled {sol.hottest_unthrottled:.1f} °C), "
        f"case {sol.case_pressure_pa:.1f} Pa, "
        f"energy error {sol.energy_error:.2%}, {sol.solve_time_s*1000:.0f} ms"
    )
    for card in sol.cards:
        flag = " THROTTLE" if card.throttle else ""
        typer.echo(
            f"  {card.id} slot {card.slot}: die {card.t_die_c:.1f} °C "
            f"(unthrottled {card.t_die_unthrottled_c:.1f}), "
            f"mem {card.t_mem_c:.1f}, exh {card.t_exh_c:.1f}, "
            f"{card.flow_cfm:.1f} CFM, duty {card.duty:.0%}{flag}"
        )


@app.callback()
def main_callback() -> None:
    """Compact flow-network + thermal-network model. Not CFD."""


@app.command()
def version() -> None:
    """Print the package version."""
    typer.echo(__version__)


@app.command()
def sweep(
    build: str = typer.Option("meshify2xl-stefano", help="Build id in presets/builds"),
    mc: int = typer.Option(200, help="Monte Carlo samples per cell. 0 skips uncertainty."),
    out: Path = typer.Option(Path("results"), help="Directory for tables and the bounds check"),
    plots: Path = typer.Option(Path("plots"), help="Directory for PNG charts"),
) -> None:
    """Run the 16-cell factorial, the stock row, and the open-air reference."""
    from gpusim.sweep import run_sweep

    frame = run_sweep(build_id=build, mc=mc, out_dir=out, plots_dir=plots)
    ranked = frame[frame["config"] != "open-air"].sort_values(
        ["hottest_die_c", "hottest_unthrottled_c", "mean_die_c"]
    )
    typer.echo(ranked[["config", "hottest_die_c", "hottest_unthrottled_c", "mean_die_c", "case_pressure_pa"]].to_string(index=False))
    typer.echo(f"Wrote {out / build}")


@app.command()
def run(
    build: str = typer.Option("meshify2xl-stefano"),
    spacing: str = typer.Option("stacked", help="stacked or gap1"),
    pressure: str = typer.Option("standard", help="standard or high"),
    shroud: str = typer.Option("off", help="off, on, or passive"),
    leakage: str = typer.Option("leaky", help="leaky or sealed"),
    rear_duct: str = typer.Option(None, help="Set 'passive' to force the unpowered duct"),
    fan_curve: str = typer.Option("stock", help="stock, maxq_aggressive, or custom"),
) -> None:
    """Solve one factorial point on a saved build."""
    from gpusim.factors import apply_cell
    from gpusim.library import get_library
    from gpusim.solve import solve

    lib = get_library()
    if rear_duct == "passive":
        shroud = "passive"
    configured = apply_cell(
        lib.builds[build],
        spacing=spacing,
        pressure=pressure,
        shroud=shroud,
        leakage=leakage,
        fan_curve=fan_curve,
        library=lib,
    )
    _echo_solution(solve(configured, lib))


@app.command()
def optimize(
    cards: int = typer.Option(4, "--cards"),
    case: str = typer.Option("meshify2xl", "--case"),
    mc: int = typer.Option(200, help="Monte Carlo samples on the winning config only"),
) -> None:
    """Search fan direction, shroud, spacing and GPU fan curve for an air-cooled build."""
    from gpusim.optimize import optimize as search

    result = search(cards=cards, case_id=case, mc=mc)
    desc = result["description"]
    typer.echo(
        f"Best of {result['tried']} configs on {result['case']}: "
        f"{desc['layout']}, shroud {desc['shroud']}, {desc['pressure']} pressure, "
        f"{desc['leakage']}, curve {desc['fan_curve']}"
    )
    typer.echo(
        f"Hottest die {result['hottest_die_c']:.1f} °C "
        f"(unthrottled {result['hottest_unthrottled_c']:.1f} °C), "
        f"case {result['case_pressure_pa']:.1f} Pa"
    )
    if result["monte_carlo"]:
        mc_info = result["monte_carlo"]
        typer.echo(
            f"MC {mc_info['n']} samples, hottest unthrottled "
            f"{mc_info['hottest_p05_c']:.1f}–{mc_info['hottest_p95_c']:.1f} °C"
        )
    if result["illustrative_mock"]:
        typer.echo("Illustrative mock — not a measurement or claim about anyone's real build.")
    typer.echo(result["note"])


@app.command()
def schematic(
    build: str = typer.Option("meshify2xl-stefano"),
    out: Path = typer.Option(Path("plots/schematic.png")),
) -> None:
    """Write a network schematic PNG (graphviz if installed, else matplotlib)."""
    from gpusim.library import get_library
    from gpusim.schematic import draw_schematic

    lib = get_library()
    path = draw_schematic(lib.builds[build], out, lib)
    typer.echo(f"Wrote {path}")


@app.command()
def calibrate(
    log: Path = typer.Option(..., "--log", exists=True, help="nvidia-smi CSV"),
) -> None:
    """Least-squares fit of the Nusselt coefficient and TIM resistance."""
    from gpusim.calibrate import fit_log

    fitted = fit_log(log)
    typer.echo(
        f"nu_C={fitted['nu_C']:.4f}  r_tim={fitted['r_tim']:.4f} K/W  "
        f"RMSE={fitted['rmse_c']:.2f} °C over {fitted['rows']} rows"
    )
    typer.echo(fitted["note"])


@app.command()
def ui(
    host: str = typer.Option("127.0.0.1"),
    port: int = typer.Option(8000),
    open_browser: bool = typer.Option(True, help="Open the visualizer in a browser"),
) -> None:
    """Serve the OBS-oriented 3D visualizer."""
    import threading
    import webbrowser

    import uvicorn

    from gpusim.ui.app import app as fastapi_app

    url = f"http://{host}:{port}"
    if open_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    typer.echo(f"gpusim ui at {url}")
    uvicorn.run(fastapi_app, host=host, port=port, log_level="info")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
