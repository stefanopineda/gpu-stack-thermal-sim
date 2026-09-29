"""Rev 4 items 9, 10, 13: seal scale, CPU cooling, internal resistance."""

import pytest

from gpusim.calib import SEAL_OPEN_FRACTION
from gpusim.factors import apply_cell
from gpusim.library import get_library
from gpusim.models import BuildCfg
from gpusim.network import build_network
from gpusim.solve import prepare_sample, solve


def _anchor_a():
    lib = get_library()
    return apply_cell(lib.builds["meshify2xl-stefano"], "gap1", "standard", "off", "leaky", library=lib)


def _net(build):
    lib = get_library()
    return build_network(
        build, lib.cases[build.case], lib.fans, lib.cards, lib.radiators, {}, {}, prepare_sample(build)
    )


def test_seal_scale_runs_open_to_sealed():
    assert SEAL_OPEN_FRACTION[1] == 1.0
    assert 0.40 <= SEAL_OPEN_FRACTION[3] <= 0.50
    assert SEAL_OPEN_FRACTION[5] == 0.0
    values = [SEAL_OPEN_FRACTION[level] for level in range(1, 6)]
    assert values == sorted(values, reverse=True)


def test_level_five_is_an_infinite_resistance_and_is_still_reported():
    build = _anchor_a()
    assert build.seals["side"] == 5
    net = _net(build)
    assert net.by_id("leak-side") is None
    assert any(s["id"] == "leak-side" for s in net.sealed)
    sol = solve(build, get_library())
    side = next(b for b in sol.branches if b["id"] == "leak-side")
    assert side["kind"] == "sealed" and side["k"] is None and side["flow_m3s"] == 0.0


def test_opening_the_side_panel_lets_air_through():
    build = _anchor_a()
    build.seals["side"] = 1
    net = _net(build)
    assert net.by_id("leak-side") is not None


def test_air_cooled_cpu_adds_heat_and_a_cooler_branch():
    lib = get_library()
    water = _anchor_a()
    air = water.model_copy(deep=True)
    air.cpu.cooling = "air"
    air.radiator.model = None
    for mount in air.mounts:
        if mount.state == "radiator":
            mount.state = "blanked"
    net = _net(air)
    cooler = net.by_id("cpu-cooler")
    assert cooler is not None and cooler.heat_tag == "cpu"
    assert net.by_id("mount-rear-1").a == "cpu"  # rear exhaust pulls from the cooler outlet
    sol = solve(air, lib)
    assert sol.converged and sol.energy_error < 0.02
    assert abs(sol.heat_w - (4 * 300 + air.cpu.power_w)) < 5
    assert sol.node_temp["cpu"] > sol.node_temp["case"]


def test_water_cpu_without_radiator_fails_loudly():
    build = _anchor_a()
    build.radiator.model = None
    with pytest.raises(ValueError, match="radiator"):
        solve(build, get_library())


def test_rev3_build_without_cpu_block_migrates():
    raw = get_library().builds["meshify2xl-stefano"].model_dump()
    raw.pop("cpu")
    raw["radiator"]["cpu_power_w"] = 140
    build = BuildCfg.model_validate(raw)
    assert build.cpu.cooling == "water"
    assert build.cpu.power_w == 140


def test_obstruction_and_cables_raise_internal_k():
    low = _anchor_a()
    high = low.model_copy(deep=True)
    high.obstruction = "high"
    high.cables = "cluttered"
    k_low = _net(low).by_id("spill").k
    k_high = _net(high).by_id("spill").k
    assert abs(k_high / k_low - 6.0 * 2.0) < 1e-6
    lib = get_library()
    assert solve(high, lib, do_throttle=False).hottest_unthrottled > solve(low, lib, do_throttle=False).hottest_unthrottled


def test_slot_covers_close_the_rear_not_the_gap_between_cards():
    covered = _anchor_a()
    covered.brackets_removed = False
    open_ = _anchor_a()
    lib = get_library()
    from gpusim.layout import gap_table

    gaps = gap_table(covered, lib.cases[covered.case], lib.cards)
    assert all(side["state"] != "blocked_slot" for g in gaps.values() for side in g["sides"])
    k_open = _net(open_).by_id("rear-slots").k
    k_covered = _net(covered).by_id("rear-slots").k
    assert k_covered > 20 * k_open  # covers leave only seams


def test_rear_slot_flow_follows_case_pressure():
    """Open slot mouths only re-ingest the plume when the case is below room pressure."""
    lib = get_library()
    from gpusim.factors import apply_cell

    def no_extra_intakes(build):
        for mount in build.mounts:
            if mount.panel in ("top", "bottom") and mount.state == "fan":
                mount.state, mount.fan = "blanked", None
        return build

    builds = [
        no_extra_intakes(apply_cell(lib.builds["meshify2xl-stefano"], "gap1", "standard", "off", "leaky", library=lib)),
        apply_cell(lib.builds["meshify2xl-stefano"], "gap1", "high", "off", "leaky", library=lib),
    ]
    signs = set()
    for build in builds:
        sol = solve(build, lib)
        reingest = next(b for b in sol.branches if b["id"] == "rear-reingest")
        positive = sol.pressures["gpu"] > 0
        signs.add(positive)
        assert (reingest["flow_cfm"] > 0) == positive  # + is out of the case
    assert signs == {True, False}


def test_psu_fan_up_is_an_exhaust_and_down_is_not():
    down = _anchor_a()
    up = down.model_copy(deep=True)
    up.psu_fan = "up"
    assert _net(down).by_id("psu-fan") is None
    branch = _net(up).by_id("psu-fan")
    assert branch is not None and branch.a == "gpu" and branch.b == "amb"
    sol = solve(up, get_library())
    assert next(b for b in sol.branches if b["id"] == "psu-fan")["flow_cfm"] > 0
