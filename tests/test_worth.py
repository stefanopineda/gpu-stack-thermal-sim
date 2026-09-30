"""'Worth it?': single changes ranked on the build as it stands."""

import json

from fastapi.testclient import TestClient

from gpusim.browser_api import dispatch
from gpusim.library import get_library
from gpusim.ui.app import app
from gpusim.worth import NOISE_FLOOR_C, _power_cap, worth_it


def _rows(result):
    return {r["id"]: r for r in result["rows"]}


def test_meshify_shroud_is_worth_about_two_degrees_and_inside_the_noise():
    lib = get_library()
    result = worth_it(lib.builds["meshify2xl-stefano"], lib, mc=4)
    rows = _rows(result)
    shroud = rows["shroud"]
    assert shroud["framing"] == "shroud_on"  # his build has it on: the row takes it off
    assert -3.5 < shroud["gain_c"] < -1.0
    assert shroud["inside_noise"]
    assert rows["fan_curve"]["gain_c"] > NOISE_FLOOR_C and not rows["fan_curve"]["inside_noise"]
    gains = [r["gain_c"] for r in result["rows"]]
    assert gains == sorted(gains, reverse=True)
    for row in result["rows"]:
        lo, hi = row["band_c"]
        assert lo <= hi


def test_touching_stack_ranks_spacing_as_a_rebuild_worth_doing():
    lib = get_library()
    rows = _rows(worth_it(lib.builds["mike-bradley-dengen-x-station"], lib))
    space = rows["space_cards"]
    assert space["effort"] == "rebuild"
    assert space["gain_c"] > NOISE_FLOOR_C and not space["inside_noise"]
    assert "shroud" in rows and rows["shroud"]["framing"] == ""  # no shroud yet: the row adds one
    assert "power_cap" not in rows
    assert all("80 %" not in r["title"] for r in rows.values())


def test_power_cap_uses_stock_tbp_and_skips_a_limit_already_at_or_below_it():
    lib = get_library()
    mike = lib.builds["mike-bradley-dengen-x-station"]
    # 275 W on a 600 W card is already under half of stock, and under 80 % (480 W).
    assert _power_cap(mike, lib) is None

    at_cap = mike.model_copy(deep=True)
    for gpu in at_cap.gpus:
        gpu.power_limit_w = 480
    assert _power_cap(at_cap, lib) is None

    # Still above 80 % of stock: the suggestion is 480 W, not 80 % of 500 W.
    partial = mike.model_copy(deep=True)
    for gpu in partial.gpus:
        gpu.power_limit_w = 500
    partial_cap = _power_cap(partial, lib)
    assert partial_cap is not None
    assert partial_cap.title == "Cap GPU power at 80 %"
    assert {g.power_limit_w for g in partial_cap.build.gpus} == {480}

    stock = mike.model_copy(deep=True)
    for gpu in stock.gpus:
        gpu.power_limit_w = lib.cards[gpu.card].tbp_w
    stock_cap = _power_cap(stock, lib)
    assert stock_cap is not None
    assert stock_cap.title == "Cap GPU power at 80 %"
    assert {g.power_limit_w for g in stock_cap.build.gpus} == {480}
    assert "480 W" in stock_cap.detail

    # One card still at stock, the others already under the cap: only the stock card moves.
    mixed = mike.model_copy(deep=True)
    mixed.gpus[0].power_limit_w = 600
    mixed_cap = _power_cap(mixed, lib)
    assert mixed_cap is not None
    limits = {g.id: g.power_limit_w for g in mixed_cap.build.gpus}
    assert limits[mixed.gpus[0].id] == 480
    assert set(limits.values()) == {480, 275}

    meshify = lib.builds["meshify2xl-stefano"]
    meshify_cap = _power_cap(meshify, lib)
    assert meshify_cap is not None
    assert meshify_cap.title == "Cap GPU power at 80 %"
    assert {g.power_limit_w for g in meshify_cap.build.gpus} == {240}

    ranked = _rows(worth_it(stock, lib))
    assert ranked["power_cap"]["title"] == "Cap GPU power at 80 %"
    assert {g["power_limit_w"] for g in ranked["power_cap"]["build"]["gpus"]} == {480}


def test_applied_candidate_is_a_valid_build_the_solver_accepts():
    lib = get_library()
    client = TestClient(app)
    build = lib.builds["meshify2xl-stefano"].model_dump(mode="json")
    res = client.post("/api/worth", json={"build": build, "mc": 0})
    assert res.status_code == 200
    body = res.json()
    assert any(r["title"] == "Cap GPU power at 80 %" for r in body["rows"])
    row = body["rows"][0]
    assert client.post("/api/solve", json=row["build"]).status_code == 200


def test_browser_dispatch_serves_worth():
    lib = get_library()
    body = json.dumps({"build": lib.builds["corsair-9000d-sample"].model_dump(mode="json"), "mc": 0})
    status, payload = dispatch("POST", "/api/worth", body)
    assert status == 200
    assert json.loads(payload)["rows"]
