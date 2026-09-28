"""Rev 4 item 12: stacked flow-through cards breathe each other's exhaust."""

import pytest

from gpusim.layout import plume_fraction
from gpusim.library import get_library
from gpusim.models import GpuCfg
from gpusim.solve import solve


def _pair(card: str, step: int, sample=None, shroud="off"):
    lib = get_library()
    build = lib.builds["meshify2xl-stefano"].model_copy(deep=True)
    power = lib.cards[card].tbp_w
    build.gpus = [
        GpuCfg(id="gpu1", slot="1", card=card, power_limit_w=power),
        GpuCfg(id="gpu2", slot=str(1 + step), card=card, power_limit_w=power),
    ]
    build.shroud.mode = shroud
    return solve(build, lib, sample=sample, do_throttle=False)


def _balanced(sol):
    assert sol.converged
    assert sol.energy_error < 0.02
    assert sol.advection_residual_kg_s < 1e-6
    for node, residual in sol.node_residual.items():
        assert abs(residual) < 1e-4, (node, residual)


@pytest.mark.parametrize("card", ["rtx-5090-fe", "rtx-pro-6000-blackwell-workstation"])
def test_upper_flow_through_card_runs_hotter_and_the_gap_closes_with_spacing(card):
    deltas = []
    for step in (3, 4, 5):  # one, two, three empty slots between two dual-slot cards
        sol = _pair(card, step)
        _balanced(sol)
        upper, lower = sol.cards[0], sol.cards[1]
        assert upper.t_die_unthrottled_c > lower.t_die_unthrottled_c + 1.0
        assert upper.t_in_c > lower.t_in_c
        assert sol.plume and sol.plume[0]["upper"] == "gpu1" and sol.plume[0]["lower"] == "gpu2"
        deltas.append(upper.t_die_unthrottled_c - lower.t_die_unthrottled_c)
    assert deltas[0] > deltas[1] > deltas[2] > 0


def test_plume_term_is_what_makes_the_upper_card_hot():
    with_plume = _pair("rtx-5090-fe", 3)
    without = _pair("rtx-5090-fe", 3, sample={"plume_phi_max": 0.0})
    d_with = with_plume.cards[0].t_die_unthrottled_c - with_plume.cards[1].t_die_unthrottled_c
    d_without = without.cards[0].t_die_unthrottled_c - without.cards[1].t_die_unthrottled_c
    assert d_with > d_without + 4.0
    _balanced(without)


def test_ingested_mass_never_exceeds_the_jet():
    sol = _pair("rtx-5090-fe", 3)
    transfer = sol.plume[0]
    assert 0 < transfer["share_of_lower_jet"] <= 0.98 + 1e-9
    assert 0 < transfer["share_of_upper_intake"] <= transfer["phi"] + 1e-9
    assert transfer["t_from_c"] > sol.cards[1].t_in_c


def test_plume_fraction_falls_with_gap():
    values = [plume_fraction(g, 0.85, 40.0) for g in (0.5, 21, 41, 62, 120)]
    assert values == sorted(values, reverse=True)
    assert values[0] <= 0.85
    assert values[-1] < 0.05


def test_blower_stack_has_no_plume_transfer():
    sol = _pair("rtx-pro-6000-blackwell-maxq", 3)
    assert sol.plume == []
    _balanced(sol)


def test_three_flow_through_cards_heat_upward_and_throttle_cleanly():
    lib = get_library()
    build = lib.builds["meshify2xl-stefano"].model_copy(deep=True)
    build.gpus = [
        GpuCfg(id=f"gpu{i}", slot=str(slot), card="rtx-5090-fe", power_limit_w=575)
        for i, slot in enumerate((1, 4, 7), start=1)
    ]
    sol = solve(build, lib)
    temps = [c.t_die_unthrottled_c for c in sol.cards]
    assert temps[0] > temps[2] and temps[1] > temps[2]
    assert all(c.t_die_c <= 90.5 for c in sol.cards)
    assert sol.solve_time_s < 0.5
    _balanced(sol)


def test_touching_flow_through_stack_matches_mike_bradleys_numbers():
    """Anchor C: no runaway, heats bottom to top, ends near his published readings."""
    from gpusim.bounds import anchor_c_checks

    checks = anchor_c_checks(get_library())
    assert len(checks) == 2
    assert all(c["pass"] for c in checks), checks


def test_touching_pair_uses_the_series_duct():
    sol = _pair("rtx-5090-fe", 2)
    stack = [b for b in sol.branches if b["kind"] == "stack"]
    assert stack and stack[0]["flow_cfm"] > 20
    upper, lower = sol.cards[0], sol.cards[1]
    assert upper.t_die_unthrottled_c < 150
    assert upper.t_die_unthrottled_c > lower.t_die_unthrottled_c
    _balanced(sol)
