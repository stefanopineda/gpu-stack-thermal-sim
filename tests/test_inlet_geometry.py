"""Fan face points at the floor. Gaps come from the slot map."""

from gpusim.factors import close_packed
from gpusim.layout import gap_table
from gpusim.library import get_library
from gpusim.network import build_network
from gpusim.solve import prepare_sample


def test_close_pack_floor_gap_is_the_psu_clearance_not_a_bypass():
    lib = get_library()
    build = close_packed(lib.builds["meshify2xl-stefano"], 4, library=lib)
    case = lib.cases["meshify2xl"]
    gaps = gap_table(build, case, lib.cards)
    floor = next(side for side in gaps["gpu4"]["sides"] if side["name"] == "fan")
    assert floor["neighbor"] is None
    assert floor["state"] == "open_slot"
    assert abs(floor["gap_mm"] - case.psu_shroud_clearance_mm) < 0.1
    mid = next(side for side in gaps["gpu2"]["sides"] if side["name"] == "fan")
    assert mid["state"] == "no_slot"
    assert mid["neighbor"] == "gpu3"
    assert mid["gap_mm"] < 8
    back = next(side for side in gaps["gpu2"]["sides"] if side["name"] == "backplate")
    assert back["neighbor"] == "gpu1"
    card = lib.cards["rtx-pro-6000-blackwell-maxq"]
    assert card.inlet_faces == "both"
    assert 0.6 <= card.inlet_split <= 0.9

    sample = prepare_sample(build)
    net = build_network(build, case, lib.fans, lib.cards, lib.radiators, {}, {}, sample)
    assert not any(br.id.startswith("bypass-") or br.kind == "bypass" for br in net.branches)
    assert any(br.id == "gap-gpu4-fan" for br in net.branches)
    assert any(br.id == "gap-gpu1-backplate" for br in net.branches)