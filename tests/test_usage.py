"""First-party usage log: what is stored, what is dropped, and where totals are read."""

import importlib.util
import json
from pathlib import Path

from fastapi.testclient import TestClient
from typer.testing import CliRunner

from gpusim.cli import app as cli
from gpusim.ui.app import app
from gpusim.usage import aggregate, read_events, record_events, sanitize_event


def _write_usage_page():
    spec = importlib.util.spec_from_file_location("build_public_site", Path("scripts/build_public_site.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.write_usage_page

SID = "11111111-1111-4111-8111-111111111111"
SID_B = "22222222-2222-4222-8222-222222222222"
runner = CliRunner()


def _event(name, props, sid=SID):
    return {"sid": sid, "name": name, "props": props}


def test_sanitize_drops_identity_and_keeps_coarse_context():
    page = sanitize_event(
        _event(
            "page_view",
            {
                "referrer": "https://news.ycombinator.com/item?id=1&email=a@b.com#top",
                "vw": 1280,
                "vh": 800,
                "lang": "en-US",
                "device": "desktop",
                "template": "meshify2xl-stefano",
                "query": "email=a@b.com",
                "ip": "203.0.113.4",
                "hash": "#b=secret",
                "country": "US",
            },
        )
    )
    assert page["props"]["referrer"] == "https://news.ycombinator.com"
    assert page["props"]["template"] == "meshify2xl-stefano"
    assert "country" not in page["props"]
    assert "query" not in page["props"]
    assert "ip" not in page["props"]
    assert "hash" not in page["props"]
    assert sanitize_event(_event("dropdown", {"control": "Case", "value": "person@example.com"})) is None
    assert sanitize_event(_event("copy_link", {"url": "https://gpuism.com/?x=1#b=secret"}))["props"] == {}
    assert sanitize_event({"sid": "not-a-uuid", "name": "page_view", "props": {"vw": 1, "vh": 1}}) is None


def test_aggregate_dwell_and_actions():
    events = [
        sanitize_event(_event("page_view", {"referrer": "", "vw": 390, "vh": 800, "lang": "en-US", "device": "phone", "demo": "stefano"})),
        sanitize_event(_event("page_view", {"referrer": "https://x.com/status/1", "vw": 1440, "vh": 900, "device": "desktop"}, sid=SID_B)),
        sanitize_event(_event("dwell", {"ms": 8000, "pc": 3000, "worth": 5000, "case": 8000})),
        sanitize_event(_event("tab", {"tab": "worth"})),
        sanitize_event(_event("case", {"case": "meshify2xl"})),
        sanitize_event(_event("preset", {"id": "meshify2xl-stefano", "source": "quick"})),
        sanitize_event(_event("dropdown", {"control": "GPU fan curve", "value": "custom_accelerated"})),
        sanitize_event(_event("worth", {"id": "fan_curve", "action": "apply"})),
        sanitize_event(_event("view", {"view": "side"})),
        sanitize_event(_event("unit", {"unit": "F"})),
        sanitize_event(_event("copy_link", {})),
        sanitize_event(_event("optimize", {"case": "meshify2xl", "cards": 4})),
    ]
    summary = aggregate([event for event in events if event])
    assert summary["page_views"] == 2
    assert summary["sessions"] == 2
    assert summary["dwell_ms"] == 8000
    assert summary["dwell_tabs_ms"]["pc"] == 3000
    assert summary["dwell_tabs_ms"]["worth"] == 5000
    assert summary["dwell_tabs_ms"]["case"] == 8000
    assert summary["counts"] == {
        "tab": 1,
        "case": 1,
        "preset": 1,
        "dropdown": 1,
        "worth": 1,
        "view": 1,
        "unit": 1,
        "copy_link": 1,
        "optimize": 1,
    }
    assert summary["presets"]["meshify2xl-stefano"] == 1
    assert summary["dropdowns"]["GPU fan curve"]["custom_accelerated"] == 1
    assert summary["referrers"]["(direct)"] == 1
    assert summary["referrers"]["https://x.com"] == 1
    assert summary["devices"] == {"phone": 1, "desktop": 1}
    assert SID not in json.dumps(summary)
    assert SID_B not in json.dumps(summary)


def test_collect_endpoint_stores_country_only_from_host(tmp_path, monkeypatch):
    path = tmp_path / "events.jsonl"
    monkeypatch.setenv("GPUSIM_USAGE_LOG", str(path))
    client = TestClient(app)
    body = {
        "events": [
            _event(
                "page_view",
                {
                    "referrer": "https://news.ycombinator.com/item?id=1&email=a@b.com",
                    "vw": 1280,
                    "vh": 800,
                    "lang": "en-US",
                    "device": "desktop",
                    "template": "meshify2xl-stefano",
                    "ip": "203.0.113.4",
                },
            ),
            _event("dropdown", {"control": "Case", "value": "person@example.com"}),
            _event("dwell", {"ms": 5000, "pc": 2000, "customize": 3000}),
            _event("tab", {"tab": "customize"}),
            _event("case", {"case": "meshify2xl"}),
            _event("preset", {"id": "corsair-9000d-sample", "source": "template"}),
            _event("worth", {"id": "shroud", "action": "row"}),
            _event("view", {"view": "front"}),
            _event("unit", {"unit": "C"}),
            _event("copy_link", {"url": "https://gpuism.com/#b=secret"}),
            _event("optimize", {"case": "meshify2xl", "cards": 4}),
        ]
    }
    stored = client.post("/usage/collect", json=body, headers={"CF-IPCountry": "US"})
    assert stored.status_code == 204
    text = path.read_text()
    assert "a@b.com" not in text
    assert "203.0.113.4" not in text
    assert "testclient" not in text
    assert "#b=" not in text
    assert "item?id" not in text
    assert '"country": "US"' in text
    summary = client.get("/usage/summary.json").json()
    assert summary["source"] == "server"
    assert summary["page_views"] == 1
    assert summary["sessions"] == 1
    assert summary["dwell_ms"] == 5000
    assert summary["dwell_tabs_ms"]["customize"] == 3000
    assert summary["counts"]["dropdown"] == 0
    assert summary["counts"]["copy_link"] == 1
    assert summary["counts"]["optimize"] == 1
    assert summary["countries"] == {"US": 1}
    assert summary["entry"]["template"]["meshify2xl-stefano"] == 1
    lines = read_events(path)
    assert all("ip" not in event["props"] for event in lines)

    bare = client.post(
        "/usage/collect",
        json={"events": [_event("page_view", {"vw": 800, "vh": 600, "device": "phone"}, sid=SID_B)]},
        headers={"CF-IPCountry": "XX"},
    )
    assert bare.status_code == 204
    assert "XX" not in path.read_text()
    assert client.post("/usage/collect", json={"events": "nope"}).status_code == 400
    assert client.post("/usage/collect", content=b"x" * 33000).status_code == 413
    page = client.get("/usage")
    assert page.status_code == 200
    assert "usage-report.js" in page.text
    assert "/usage" not in app.openapi()["paths"]


def test_reader_copy_and_publish_hook(tmp_path):
    report = Path("gpusim/ui/static/usage-report.js").read_text()
    tracker = Path("gpusim/ui/static/usage.js").read_text()
    assert "GitHub Pages cannot run that endpoint" in report
    assert "POST /usage/collect" in report
    assert "gpusim usage" in report
    assert "location.hash" not in tracker
    assert "location.href" not in tracker
    assert 'COLLECT = "/usage/collect"' in tracker
    assert "gpuism.com" in tracker and "127.0.0.1" in tracker
    assert "localStorage" in tracker
    html = Path("gpusim/ui/static/index.html").read_text()
    app_js = Path("gpusim/ui/static/app.js").read_text()
    assert 'href="/usage/"' in html
    for needle in ('track("view"', 'track("unit"', 'track("copy_link"', 'track("optimize"', 'track("preset"', 'track("tab"', "data-usage-worth"):
        assert needle in app_js
    ci = Path(".github/workflows/ci.yml").read_text()
    assert "--exclude 'usage/events.jsonl'" in ci
    dest = tmp_path / "usage"
    write_page = _write_usage_page()
    write_page(Path("gpusim/ui/static/usage.html").read_text(), dest, "abc123")
    published = (dest / "index.html").read_text()
    assert 'src="../static/usage-report.js?v=abc123"' in published
    missing = runner.invoke(cli, ["usage", "--log", "/tmp/gpusim-usage-does-not-exist.jsonl"])
    assert missing.exit_code == 0
    assert "No usage log" in missing.stdout


def test_cli_prints_totals(tmp_path, monkeypatch):
    path = tmp_path / "events.jsonl"
    monkeypatch.setenv("GPUSIM_USAGE_LOG", str(path))
    record_events([_event("dwell", {"ms": 1500, "network": 1500})])
    result = runner.invoke(cli, ["usage"])
    assert result.exit_code == 0, result.output
    assert "Time on site: 2 s" in result.stdout or "Time on site: 1 s" in result.stdout
    assert "network" in result.stdout
    listed = runner.invoke(cli, ["usage", "--json"])
    assert listed.exit_code == 0
    payload = json.loads(listed.stdout)
    assert payload["dwell_tabs_ms"]["network"] == 1500
