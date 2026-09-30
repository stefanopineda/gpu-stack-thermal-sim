"""Rev 4 item 14: the agent API."""

import json
from pathlib import Path

from fastapi.testclient import TestClient

from gpusim.ui.app import app, simapi_schemas

EXAMPLES = Path(__file__).resolve().parent.parent / "examples" / "api"
client = TestClient(app)


def _load(name):
    return json.loads((EXAMPLES / name).read_text())


def test_simulate_saved_meshify_matches_the_solver():
    body = client.post("/api/v1/simulate", json=_load("simulate_meshify.json"))
    assert body.status_code == 200, body.text
    out = body.json()
    assert out["api_version"] == "1" and out["spec_revision"] == 4
    assert len(out["cards"]) == 4
    # Spaced, shroud on: the 2026-09-30 soak is 79 °C.
    assert 74 < out["summary"]["hottest_die_c"] < 84
    assert out["summary"]["energy_balance_error"] < 0.02
    assert "±5–10 °C" in out["accuracy"]
    assert "network" not in out  # summary detail


def test_simulate_custom_rig_with_inline_fan_and_full_detail():
    out = client.post("/api/v1/simulate", json=_load("simulate_custom_rig.json")).json()
    assert [c["card"] for c in out["cards"]] == ["rtx-5090-fe", "rtx-5090-fe"]
    assert out["plume"] and out["plume"][0]["upper"] == "gpu1"
    kinds = {b["kind"] for b in out["network"]["branches"]}
    assert {"up-exit", "cpu-cooler", "plume-ingest", "sealed", "gap"} <= kinds
    first = out["thermal"][0]
    for key in ("t_zone_c", "t_inlet_c", "r_conv_k_per_w", "t_heatsink_c", "r_tim_k_per_w", "t_die_c"):
        assert key in first


def test_rank_orders_variants_and_keeps_errors_in_place():
    request = _load("rank_meshify_variants.json")
    request["variants"].append({"name": "broken", "set": {"gpus.*.card": "no-such-card"}})
    out = client.post("/api/v1/rank", json=request).json()
    ranked = [r for r in out["results"] if "rank" in r]
    keys = [
        (1, r["summary"]["hottest_unthrottled_c"]) if r["summary"]["any_throttle"] else (0, r["summary"]["hottest_die_c"])
        for r in ranked
    ]
    assert keys == sorted(keys)
    assert out["ranking"].startswith("Lower is better")
    assert ranked[0]["name"] == "custom accelerated GPU curve"
    broken = next(r for r in out["results"] if r["name"] == "broken")
    assert "no-such-card" in broken["error"]


def test_sweep_runs_a_factorial():
    out = client.post("/api/v1/sweep", json=_load("sweep_5090_spacing.json")).json()
    assert out["cells"] == 6
    assert all("rank" in r for r in out["results"])
    stock = {r["settings"]["spacing"]: r for r in out["results"] if r["settings"]["fan_curve"] == "stock"}
    gap = {k: v["cards"][0]["t_die_unthrottled_c"] - v["cards"][1]["t_die_unthrottled_c"] for k, v in stock.items()}
    assert gap["gap1"] > gap["gap2"] > gap["gap3"] > 0


def test_inline_card_borrows_calibration():
    spec = _load("simulate_meshify.json")
    spec["extra_cards"] = [
        {"id": "my-250w-blower", "calibration_from": "rtx-pro-6000-blackwell-maxq", "tbp_w": 250}
    ]
    for gpu in spec["build"]["gpus"]:
        gpu["card"] = "my-250w-blower"
        gpu["power_limit_w"] = 250
    out = client.post("/api/v1/simulate", json=spec)
    assert out.status_code == 200, out.text
    assert out.json()["summary"]["hottest_die_c"] < 84


def test_bad_spec_is_a_422_with_a_reason():
    spec = _load("simulate_meshify.json")
    spec["build"]["case"] = "not-a-case"
    res = client.post("/api/v1/simulate", json=spec)
    assert res.status_code == 422
    assert "unknown case" in res.json()["detail"]
    spec = _load("simulate_meshify.json")
    spec["build"]["gpus"][1]["slot"] = "2"  # overlaps gpu1 (slots 1–2)
    res = client.post("/api/v1/simulate", json=spec)
    assert res.status_code == 422 and "overlaps" in res.json()["detail"]


def test_presets_schema_and_exported_files():
    presets = client.get("/api/v1/presets").json()
    assert "rtx-5090-fe" in {c["id"] for c in presets["cards"]}
    assert presets["seal_levels"][0]["open_fraction"] == 1.0
    assert presets["seal_levels"][-1]["open_fraction"] == 0.0
    assert client.get("/api/v1/builds/meshify2xl-stefano").json()["case"] == "meshify2xl"
    schema = client.get("/api/v1/schema").json()
    assert set(schema) == {"SimSpec", "RankRequest", "SweepRequest"}
    docs = Path(__file__).resolve().parent.parent / "docs"
    exported = json.loads((docs / "openapi.json").read_text())
    assert set(exported["paths"]) == set(app.openapi()["paths"])
    assert json.loads((docs / "simspec.schema.json").read_text()) == json.loads(json.dumps(simapi_schemas()))
    assert client.get("/docs").status_code == 200
