"""The browser JSON routes match the in-process solver."""

import json

from gpusim.browser_api import dispatch
from gpusim.library import load_library
from gpusim.solve import solve


def test_browser_solve_matches_the_python_solver():
    lib = load_library()
    build = lib.builds["mike-bradley-dengen-x-station"]
    status, payload = dispatch("POST", "/api/solve", build.model_dump_json())
    assert status == 200
    body = json.loads(payload)
    direct = solve(build, lib)
    assert abs(body["hottest_die_c"] - direct.hottest_die) < 1e-6
    assert [c["id"] for c in body["cards"]] == [c.id for c in direct.cards]
    assert abs(body["cards"][0]["t_die_c"] - direct.cards[0].t_die_c) < 1e-6


def test_browser_presets_and_unknown_build():
    status, payload = dispatch("GET", "/api/presets")
    assert status == 200
    assert any(b["id"] == "mike-bradley-dengen-x-station" for b in json.loads(payload)["builds"])
    status, payload = dispatch("GET", "/api/build/does-not-exist")
    assert status == 404
