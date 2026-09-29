"""Rear-shroud mouths: open plenum versus taped stack.

Orientation A pulls interior inter-card gaps into the plenum, in parallel with
the GPU exhaust openings. Orientation B tapes those gaps down to a crack.
Shroud off keeps neither branch.
"""

from gpusim.factors import apply_cell, apply_scenario_step, close_packed
from gpusim.library import get_library
from gpusim.network import build_network
from gpusim.physics import shroud_mouth_loss
from gpusim.solve import prepare_sample, solve


def _lib():
    return get_library()


def _net(build):
    lib = _lib()
    return build_network(
        build, lib.cases[build.case], lib.fans, lib.cards, lib.radiators, {}, {}, prepare_sample(build)
    )


def _stefano():
    return _lib().builds["meshify2xl-stefano"].model_copy(deep=True)


def _kinds(net, kind):
    return [b for b in net.branches if b.kind == kind]


def test_mouth_resistance_scales_with_gap_height():
    """R drops as the aperture grows: k ∝ 1/A² and A ∝ gap × span."""
    tight = shroud_mouth_loss(0.6, 3.6, 0.111, 0.267, 1.2, 1.8e-5, 0.62)
    open_ = shroud_mouth_loss(24.0, 24.0, 0.111, 0.267, 1.2, 1.8e-5, 0.62)
    assert tight is not None and open_ is not None
    area_ratio = open_[2] / tight[2]
    assert abs(area_ratio - 24.0 / 0.6) < 1e-6
    # Orifice term dominates; the ratio of k is the square of the area ratio.
    assert tight[0] / open_[0] > 0.5 * area_ratio**2


def test_open_plenum_pulls_interior_gaps_only():
    build = _stefano()
    assert build.shroud.mode == "on" and build.shroud.intake == "open"
    net = _net(build)
    pulls = _kinds(net, "shroud-pull")
    assert sorted(b.id for b in pulls) == ["shroud-pull-gpu1-gpu2", "shroud-pull-gpu2-gpu3"]
    assert _kinds(net, "shroud-crack") == []
    # Vertical card and the two exterior faces are not mouths.
    assert all("gpu4" not in b.id for b in pulls)
    assert net.by_id("rear-slots") is None
    brackets = _kinds(net, "bracket")
    assert len(brackets) == 4 and all(b.b == "plenum" for b in brackets)
    # Wider gap, lower resistance. The two gap1 mouths match; a tight pair does not.
    stacked = close_packed(build, 4, shroud="on", library=_lib())
    stacked.shroud.intake = "open"
    wide = pulls[0].k
    tight = _kinds(_net(stacked), "shroud-pull")[0].k
    assert tight > 20 * wide


def test_taped_is_gpu_mouths_plus_a_crack():
    build = close_packed(_stefano(), 4, shroud="on", library=_lib())
    build.shroud.intake = "taped"
    net = _net(build)
    assert _kinds(net, "shroud-pull") == []
    cracks = _kinds(net, "shroud-crack")
    assert sorted(b.id for b in cracks) == [
        "shroud-crack-gpu1-gpu2",
        "shroud-crack-gpu2-gpu3",
        "shroud-crack-gpu3-gpu4",
    ]
    assert all(b.a == "gpu" and b.b == "plenum" for b in cracks)
    brackets = _kinds(net, "bracket")
    assert len(brackets) == 4 and all(b.b == "plenum" for b in brackets)
    # The crack is a high-R orifice, not the open gap and not a deleted branch.
    open_stack = build.model_copy(deep=True)
    open_stack.shroud.intake = "open"
    open_k = _kinds(_net(open_stack), "shroud-pull")[0].k
    assert cracks[0].k > 10 * open_k


def test_shroud_off_drops_pull_and_crack_branches():
    base = _stefano()
    off = base.model_copy(deep=True)
    off.shroud.mode = "off"
    net = _net(off)
    assert _kinds(net, "shroud-pull") == []
    assert _kinds(net, "shroud-crack") == []
    assert net.by_id("plenum") is None or net.by_id("shroud-fans") is None
    assert all(b.kind != "shroud-fan" for b in net.branches)
    taped = close_packed(base, 4, shroud="on", library=_lib())
    taped.shroud.intake = "taped"
    taped.shroud.mode = "off"
    gone = _net(taped)
    assert _kinds(gone, "shroud-pull") == [] and _kinds(gone, "shroud-crack") == []
    assert all(b.b != "plenum" for b in gone.branches)


def test_covers_close_the_rear_mouth_the_shroud_would_pull():
    open_ = _stefano()
    covered = open_.model_copy(deep=True)
    covered.brackets_removed = False
    k_open = _net(open_).by_id("shroud-pull-gpu1-gpu2").k
    k_covered = _net(covered).by_id("shroud-pull-gpu1-gpu2").k
    assert k_covered > 20 * k_open


def test_tape_raises_through_gpu_flow_and_open_keeps_the_bypass():
    """Same spacing: taping the gaps moves air through the coolers."""
    lib = _lib()
    gap = apply_cell(lib.builds["meshify2xl-stefano"], "gap1", "standard", "on", "leaky", library=lib)
    gap.shroud.intake = "open"
    taped = gap.model_copy(deep=True)
    taped.shroud.intake = "taped"
    sol_open = solve(gap, lib, do_throttle=False)
    sol_taped = solve(taped, lib, do_throttle=False)
    assert sol_open.converged and sol_taped.converged
    assert sol_open.energy_error < 0.02 and sol_taped.energy_error < 0.02

    def mean(sol):
        return sum(c.flow_cfm for c in sol.cards) / len(sol.cards)

    def kind_cfm(sol, kind):
        return sum(b["flow_cfm"] for b in sol.branches if b["kind"] == kind and b["flow_cfm"] > 0)

    assert mean(sol_taped) > mean(sol_open)
    assert kind_cfm(sol_open, "shroud-pull") > kind_cfm(sol_taped, "shroud-crack")
    # Most of the taped shroud's inlet is the GPU mouths, not the crack.
    mouths = kind_cfm(sol_taped, "bracket")
    crack = kind_cfm(sol_taped, "shroud-crack")
    assert mouths > 5 * crack


def test_orientation_a_runs_cooler_than_the_taped_stack():
    """Full hardware A/B: gapped open plenum versus stacked and taped."""
    lib = _lib()
    from gpusim.models import ScenarioStep

    base = lib.builds["meshify2xl-stefano"]
    step_a = ScenarioStep(
        id="a",
        title="A",
        talking_points=["a"],
        layout="gap1_vertical",
        pressure="standard",
        shroud="on",
        shroud_intake="open",
        leakage="leaky",
        fan_curve="stock",
    )
    step_b = ScenarioStep(
        id="b",
        title="B",
        talking_points=["b"],
        layout="close4",
        pressure="standard",
        shroud="on",
        shroud_intake="taped",
        leakage="leaky",
        fan_curve="stock",
    )
    sol_a = solve(apply_scenario_step(base, step_a, lib), lib, do_throttle=False)
    sol_b = solve(apply_scenario_step(base, step_b, lib), lib, do_throttle=False)
    assert sol_a.hottest_unthrottled < sol_b.hottest_unthrottled
    assert sol_a.energy_error < 0.02 and sol_b.energy_error < 0.02


def test_worth_offers_the_orientation_pair():
    from gpusim.worth import worth_it

    lib = _lib()
    rows = {r["id"]: r for r in worth_it(lib.builds["meshify2xl-stefano"], lib)["rows"]}
    row = rows["shroud_orientation"]
    assert row["framing"] == "shroud_ab"
    assert row["effort"] == "rebuild"
    assert row["build"]["shroud"]["intake"] == "taped"
    assert row["build"]["shroud"]["mode"] == "on"
