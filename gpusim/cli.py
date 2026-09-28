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
    plots: Path | None = typer.Option(
        None,
        help="PNG directory. Default is plots/ when --out is results, otherwise <out>/plots.",
    ),
) -> None:
    """Run the 16-cell factorial, the stock row, and the open-air reference."""
    from gpusim.sweep import rank_frame, resolve_plots_dir, run_sweep

    plot_root = resolve_plots_dir(out, plots)
    frame = run_sweep(build_id=build, mc=mc, out_dir=out, plots_dir=plot_root)
    ranked = rank_frame(frame)
    typer.echo(ranked[["config", "hottest_die_c", "hottest_unthrottled_c", "mean_die_c", "case_pressure_pa"]].to_string(index=False))
    typer.echo(f"Wrote {out / build}")
    typer.echo(f"Plots in {plot_root / build}")


@app.command()
def run(
    build: str = typer.Option("meshify2xl-stefano"),
    spacing: str = typer.Option("stacked", help="stacked or gap1"),
    pressure: str = typer.Option("standard", help="standard or high"),
    shroud: str = typer.Option("off", help="off, on, or passive"),
    leakage: str = typer.Option("leaky", help="leaky or sealed"),
    rear_duct: str = typer.Option(None, help="Set 'passive' to force the unpowered duct"),
    fan_curve: str = typer.Option("stock", help="stock, custom_accelerated (alias maxq_aggressive), or custom"),
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


def _read_json(path: Path) -> dict:
    import json

    return json.loads(Path(path).read_text())


def _write_json(data: dict, out: Path | None) -> None:
    import json

    text = json.dumps(data, indent=2, default=str)
    if out:
        Path(out).write_text(text + "\n")
        typer.echo(f"Wrote {out}")
    else:
        typer.echo(text)


@app.command()
def simulate(
    spec: Path = typer.Argument(..., exists=True, help="SimSpec JSON (same body as POST /api/v1/simulate)"),
    out: Path | None = typer.Option(None, help="Write the JSON result here instead of stdout"),
) -> None:
    """Solve one full PC spec from a JSON file. Offline twin of /api/v1/simulate."""
    from gpusim import api

    _write_json(api.simulate(api.SimSpec.model_validate(_read_json(spec))), out)


@app.command()
def rank(
    request: Path = typer.Argument(..., exists=True, help="RankRequest (variants) or SweepRequest (factors) JSON"),
    out: Path | None = typer.Option(None, help="Write the JSON result here instead of stdout"),
) -> None:
    """Rank variants or a factorial from a JSON file. Offline twin of /api/v1/rank and /api/v1/sweep."""
    from gpusim import api

    body = _read_json(request)
    if "factors" in body:
        result = api.sweep(api.SweepRequest.model_validate(body))
    else:
        result = api.rank(api.RankRequest.model_validate(body))
    if out:
        _write_json(result, out)
        return
    for row in result["results"]:
        if "error" in row:
            typer.echo(f"  -  {row['name']}: ERROR {row['error']}")
            continue
        s = row["summary"]
        temps = ", ".join(f"{c['t_die_unthrottled_c']:.1f}" for c in row["cards"])
        typer.echo(
            f"{row['rank']:>3}  {row['name']}: hottest {s['hottest_die_c']:.1f} °C "
            f"(unthrottled {s['hottest_unthrottled_c']:.1f}; cards {temps})"
        )


@app.command()
def schema(
    out: Path = typer.Option(Path("docs"), help="Directory for openapi.json and simspec.schema.json"),
) -> None:
    """Export the OpenAPI document and the request JSON Schemas."""
    import json

    from gpusim.ui.app import app as fastapi_app
    from gpusim.ui.app import simapi_schemas

    out.mkdir(parents=True, exist_ok=True)
    (out / "openapi.json").write_text(json.dumps(fastapi_app.openapi(), indent=2) + "\n")
    (out / "simspec.schema.json").write_text(json.dumps(simapi_schemas(), indent=2) + "\n")
    typer.echo(f"Wrote {out / 'openapi.json'} and {out / 'simspec.schema.json'}")


def _port_is_free(host: str, port: int) -> bool:
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
        except OSError:
            return False
    return True


def choose_port(host: str, requested: int) -> tuple[int, bool]:
    """Use the requested port, or the next free one. The bool is True if we moved."""
    if _port_is_free(host, requested):
        return requested, False
    for port in range(requested + 1, requested + 30):
        if _port_is_free(host, port):
            return port, True
    raise typer.BadParameter(
        f"Port {requested} is busy and nothing is free through {requested + 29}."
    )


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

    chosen, moved = choose_port(host, port)
    if moved:
        typer.echo(f"Port {port} is busy. Using {chosen}.")
    url = f"http://{host}:{chosen}"
    typer.echo(f"gpusim ui at {url}")
    if open_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    uvicorn.run(fastapi_app, host=host, port=chosen, log_level="info")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
