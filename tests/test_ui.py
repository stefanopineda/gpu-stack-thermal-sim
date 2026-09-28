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
    assert "Presentation" in text
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
