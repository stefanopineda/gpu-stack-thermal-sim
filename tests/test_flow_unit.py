"""Mass balance on a tiny fan + orifice network, independent of the presets."""

import numpy as np

from gpusim.flow import Branch, solve_network
from gpusim.physics import fan_tables, quadratic_curve


def test_fan_into_orifice_conserves_mass():
    q, p = fan_tables(quadratic_curve(200.0, 4.0, n=9))  # 200 m³/h, 4 mmH2O
    branches = [
        Branch(
            id="fan",
            a="amb",
            b="case",
            k=2.0e4,
            k_lin=1.0,
            rho=1.2,
            kind="fan",
            label="fan",
            q_tab=q,
            p_tab=p,
            rpm=1500,
            rpm_ref=1500,
        ),
        Branch(
            id="out",
            a="case",
            b="amb",
            k=3.0e4,
            k_lin=1.0,
            rho=1.2,
            kind="orifice",
            label="out",
        ),
    ]
    sol = solve_network(branches, ["amb", "case"])
    assert sol.converged
    assert abs(sol.residual["case"]) < 1e-6
    assert sol.flow_m3s["fan"] > 0
    assert abs(sol.flow_m3s["fan"] - sol.flow_m3s["out"]) < 1e-6
    # Dead-head pressure of this fan is 4 mmH2O ≈ 39 Pa, so the case sits below that.
    assert 0 < sol.pressure["case"] < 39.3


def test_blocked_fan_holds_static_pressure():
    q, p = fan_tables(quadratic_curve(100.0, 2.0, n=7))
    branches = [
        Branch(
            id="fan",
            a="amb",
            b="box",
            k=1.0e3,
            k_lin=0.5,
            rho=1.2,
            kind="fan",
            label="fan",
            q_tab=q,
            p_tab=p,
            rpm=1000,
            rpm_ref=1000,
        ),
        Branch(
            id="leak",
            a="box",
            b="amb",
            k=1.0e9,
            k_lin=1.0,
            rho=1.2,
            kind="leak",
            label="almost closed",
        ),
    ]
    sol = solve_network(branches, ["amb", "box"])
    assert sol.converged
    # Nearly dead-headed: pressure close to Pmax, flow small.
    assert sol.pressure["box"] > 15
    assert sol.flow_m3s["fan"] < 0.01
    assert abs(sol.mass_kg_s["fan"] + sol.mass_kg_s["leak"] * -1) < 1e-5 or abs(
        sol.flow_m3s["fan"] - sol.flow_m3s["leak"]
    ) < 1e-5
