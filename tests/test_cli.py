from typer.testing import CliRunner

from gpusim.calibrate import fit_log
from gpusim.cli import app
from gpusim.factors import open_air_build
from gpusim.solve import solve_monte_carlo

runner = CliRunner()


def test_version_and_single_run():
    version = runner.invoke(app, ["version"])
    assert version.exit_code == 0
    assert "0.4" in version.stdout
    result = runner.invoke(
        app,
        ["run", "--spacing", "gap1", "--pressure", "standard", "--shroud", "off", "--leakage", "leaky"],
    )
    assert result.exit_code == 0, result.output
    assert "gpu1" in result.stdout
    assert "°C" in result.stdout


def test_monte_carlo_is_deterministic():
    build = open_air_build()
    first = solve_monte_carlo(build, n=3, seed=7)
    second = solve_monte_carlo(build, n=3, seed=7)
    assert [c.cards[0].t_die_unthrottled_c for c in first] == [
        c.cards[0].t_die_unthrottled_c for c in second
    ]


def test_calibrate_log_returns_finite_fit():
    fitted = fit_log("examples/nvidia_smi.csv")
    assert fitted["rows"] >= 3
    assert fitted["nu_C"] > 0
    assert fitted["r_tim"] > 0
    assert fitted["rmse_c"] < 30
