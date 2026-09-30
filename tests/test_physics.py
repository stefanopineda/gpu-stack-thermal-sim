import time

from gpusim.bounds import evaluate_bounds, solution_energy_ok
from gpusim.factors import apply_cell, close_packed, iter_cells, open_air_build, reference_build
from gpusim.library import get_library
from gpusim.physics import electrical_power
from gpusim.solve import solve


def _lib():
    return get_library()


def test_open_air_and_aggressive_and_anchors():
    lib = _lib()
    report = evaluate_bounds(lib.builds["meshify2xl-stefano"], lib)
    failed = [c for c in report["checks"] if not c["pass"]]
    assert not failed, failed


def test_energy_mass_and_every_cell():
    lib = _lib()
    base = lib.builds["meshify2xl-stefano"]
    for cell in iter_cells():
        sol = solve(apply_cell(base, library=lib, **cell), lib)
        assert sol.converged
        assert solution_energy_ok(sol)
        assert sol.solve_time_s < 0.5
        for node, residual in sol.node_residual.items():
            assert abs(residual) < 1e-4, (cell, node, residual)


def test_every_case_preset_converges():
    lib = _lib()
    for case_id in lib.cases:
        sol = solve(reference_build(case_id, lib), lib, do_throttle=False, outer=5)
        assert sol.converged
        assert solution_energy_ok(sol)


def test_close_pack_middle_cards_are_hottest_unthrottled():
    lib = _lib()
    sol = solve(close_packed(lib.builds["meshify2xl-stefano"], 4, library=lib), lib, do_throttle=False)
    temps = [c.t_die_unthrottled_c for c in sol.cards]
    assert temps[1] > temps[0] and temps[1] > temps[3]
    assert temps[2] > temps[0] and temps[2] > temps[3]
    assert max(temps) > 85


def test_speed_of_one_configuration():
    lib = _lib()
    build = apply_cell(lib.builds["meshify2xl-stefano"], "gap1", "standard", "off", "leaky", library=lib)
    solve(build, lib)  # warm imports / caches
    started = time.perf_counter()
    sol = solve(build, lib)
    assert time.perf_counter() - started < 0.5
    assert sol.converged


def test_stefano_meshify_soaks_2026_09_30():
    """Four 5-minute full-load soaks. Hottest die, full board power."""
    lib = _lib()
    base = lib.builds["meshify2xl-stefano"]
    spaced_off = apply_cell(base, "gap1", "standard", "off", "leaky", library=lib)
    spaced_on = apply_cell(base, "gap1", "standard", "on", "leaky", library=lib)
    spaced_on.shroud.intake = "open"
    stacked_off = close_packed(base, 4, shroud="off", library=lib)
    stacked_on = close_packed(base, 4, shroud="on", library=lib)
    stacked_on.shroud.intake = "taped"
    targets = (89.0, 79.0, 93.0, 91.0)
    hottest = []
    for build, target in zip((spaced_off, spaced_on, stacked_off, stacked_on), targets):
        sol = solve(build, lib)
        assert sol.converged and sol.energy_error <= 0.02
        assert abs(sol.hottest_die - target) <= 1.0
        hottest.append(sol.hottest_die)
    # Shroud benefit ~10 °C spaced, ~2 °C stacked and taped.
    assert 8.0 <= hottest[0] - hottest[1] <= 12.0
    assert 0.5 <= hottest[2] - hottest[3] <= 3.5


def test_open_air_reference_band_directly():
    sol = solve(open_air_build())
    # Rev 3 fit was ~83 °C. nu_C was lowered for the 2026-09-30 soaks, so open
    # air rides higher. Still a full-power blower, not a runaway.
    card = sol.cards[0]
    assert 84 <= card.t_die_unthrottled_c <= 93
    # The throttle flag is the 88 °C mark. Power does not fold until cutoff_c
    # (96), so open air stays at full board power.
    assert card.power_w > 295
    assert card.throttle is (card.t_die_unthrottled_c >= 88.0)


def test_power_model_clamps_and_responds_to_undervolt():
    full, _, _ = electrical_power(300, 0, 0, 0, 2286, 1750, 0.12)
    undervolt, _, _ = electrical_power(300, 0, 0, -100, 2286, 1750, 0.12)
    overclock, _, _ = electrical_power(300, 400, 0, 0, 2286, 1750, 0.12)
    assert abs(full - 300) < 1e-6
    assert undervolt < full - 1
    assert abs(overclock - 300) < 1e-6  # still power-limited
