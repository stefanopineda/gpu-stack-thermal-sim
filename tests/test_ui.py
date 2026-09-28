from fastapi.testclient import TestClient

from gpusim.ui.app import app


def test_visualizer_smoke():
    client = TestClient(app)
    page = client.get("/")
    assert page.status_code == 200
    text = page.text
    assert "Quick start" in text
    assert "Demo" in text
    assert "Compare" in text
    assert "Present" in text
    assert "water" in text.lower()
    assert "Celsius" in text or "°C" in text

    assert client.get("/api/health").json()["ok"] is True
    presets = client.get("/api/presets").json()
    scenario_ids = {s["id"] for s in presets["scenarios"]}
    assert scenario_ids >= {"stefano-demo", "mike-bradley-demo"}
    assert any(b["id"] == "meshify2xl-stefano" for b in presets["builds"])
    assert any("mock" in (s.get("disclaimer") or s["title"]).lower() or s["illustrative_mock"] for s in presets["scenarios"])

    build = client.get("/api/build/meshify2xl-stefano").json()
    solved = client.post("/api/solve", json=build)
    assert solved.status_code == 200
    body = solved.json()
    assert len(body["cards"]) == 4
    assert "branches" in body

    for scenario_id in ("stefano-demo", "mike-bradley-demo"):
        step = client.post("/api/scenario", json={"scenario_id": scenario_id, "step": 0})
        assert step.status_code == 200, step.text
        payload = step.json()
        assert payload["step"]["talking_points"]
        assert payload["solution"]["cards"]


def test_visualizer_modules_and_rev4_payload():
    client = TestClient(app)
    for name in ("app.js", "scene.js", "network.js", "tips.js", "style.css", "vendor/three.module.js"):
        res = client.get(f"/static/{name}")
        assert res.status_code == 200, name
        assert res.headers.get("cache-control") == "no-cache"
    tips = client.get("/static/tips.js").text
    assert "0 % open" in tips and "70 °C" in tips  # seal and custom-accelerated assumptions
    presets = client.get("/api/presets").json()
    assert {c["cooler"] for c in presets["cards"]} == {"blower", "flow_through"}
    assert presets["seal_levels"][0]["level"] == 1
    body = client.post("/api/solve", json=client.get("/api/build/corsair-9000d-sample").json()).json()
    first = body["cards"][0]
    assert first["thermal"]["r_conv_k_per_w"] > 0
    assert any(b["kind"] == "sealed" for b in body["branches"])
    front = [m for m in client.get("/api/build/corsair-9000d-sample").json()["mounts"] if m["panel"] == "front"]
    assert len(front) == 8 and all(m["fan"] == "corsair-af120-rgb-elite" for m in front)
