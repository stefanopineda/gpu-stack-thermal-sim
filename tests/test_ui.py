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
    mike = next(s for s in presets["scenarios"] if s["id"] == "mike-bradley-demo")
    assert "Mike Bradley" in mike["title"] and "79 °C" in mike["disclaimer"]

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


def test_phone_ui_keeps_desktop_split():
    """iPhone-width fixes stay in the static UI; the desktop Split control stays."""
    client = TestClient(app)
    css = client.get("/static/style.css").text
    js = client.get("/static/scene.js").text
    app_js = client.get("/static/app.js").text
    html = client.get("/").text
    assert 'touch-action: none' in css
    assert ".view3d" in css and "#scene" in css
    assert "passive: false" in js and "preventDefault" in js and "setPointerCapture" in js
    assert 'pointerType === "touch"' in js and "ResizeObserver" in js and "relayout(" in js
    assert "if (!w || !h) return" in js
    assert "aspectChanged" in js
    assert "body.mtab-pc .view3d { height: 100%; min-height: 0; }" in css
    assert "body.mtab-customize .readout { display: none !important; }" in css
    assert "grid-template-rows: minmax(0, 1fr)" in css
    assert "grid-template-columns: minmax(0, 1fr) !important" in css
    assert '[data-mtab="split"] { display: none; }' in css
    assert "repeat(4, minmax(0, 1fr))" in css
    assert 'tab === "split"' in app_js and 'mode === "split"' in app_js
    assert 'data-mtab="split"' in html and 'data-net="split"' in html


def test_phone_selects_wrap_full_option():
    """Under 800px the chosen option is a wrapping label, not an ellipsis."""
    client = TestClient(app)
    css = client.get("/static/style.css").text
    js = client.get("/static/app.js").text
    phone = css.split("@media (max-width: 800px)", 1)[1].split("@media (min-width: 801px)", 1)[0]
    assert ".select-face .select-value" in phone
    assert "overflow-wrap: break-word" in phone
    assert "text-overflow: clip" in phone
    assert "ellipsis" not in phone
    assert "@media (min-width: 801px)" in css and ".select-face { display: contents; }" in css
    assert "fitPhoneSelects" in js and "function isNarrow()" in js


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
