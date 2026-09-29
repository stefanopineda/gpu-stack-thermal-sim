"""'Worth it?': single changes ranked on the build as it stands."""

import json

from fastapi.testclient import TestClient

from gpusim.browser_api import dispatch
from gpusim.library import get_library
from gpusim.ui.app import app
from gpusim.worth import NOISE_FLOOR_C, worth_it


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


def test_applied_candidate_is_a_valid_build_the_solver_accepts():
    lib = get_library()
    client = TestClient(app)
    build = lib.builds["meshify2xl-stefano"].model_dump(mode="json")
    res = client.post("/api/worth", json={"build": build, "mc": 0})
    assert res.status_code == 200
    row = res.json()["rows"][0]
    assert client.post("/api/solve", json=row["build"]).status_code == 200


def test_browser_dispatch_serves_worth():
    lib = get_library()
    body = json.dumps({"build": lib.builds["corsair-9000d-sample"].model_dump(mode="json"), "mc": 0})
    status, payload = dispatch("POST", "/api/worth", body)
    assert status == 200
    assert json.loads(payload)["rows"]
