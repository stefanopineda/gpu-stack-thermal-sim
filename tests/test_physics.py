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


def test_open_air_reference_band_directly():
    sol = solve(open_air_build())
    assert 75 <= sol.cards[0].t_die_unthrottled_c <= 85
    assert sol.cards[0].throttle is False


def test_power_model_clamps_and_responds_to_undervolt():
    full, _, _ = electrical_power(300, 0, 0, 0, 2286, 1750, 0.12)
    undervolt, _, _ = electrical_power(300, 0, 0, -100, 2286, 1750, 0.12)
    overclock, _, _ = electrical_power(300, 400, 0, 0, 2286, 1750, 0.12)
    assert abs(full - 300) < 1e-6
    assert undervolt < full - 1
    assert abs(overclock - 300) < 1e-6  # still power-limited
