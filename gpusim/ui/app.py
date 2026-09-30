"""FastAPI app: the visualizer plus the agent API (/api/v1, docs at /docs).

The public site (gpuism.com) runs these same routes in Pyodide. This process
is the local server.
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from gpusim import __version__
from gpusim import api as simapi
from gpusim.browser_api import (
    ApiError,
    build_payload,
    optimize_payload,
    presets_payload,
    scenario_payload,
    solve_payload,
    worth_payload,
)
from gpusim.calib import GLOBAL_FAN_CURVES
from gpusim.library import get_library
from gpusim.models import BuildCfg
from gpusim.usage import country_from_headers, log_path, record_events, summary_for

STATIC = Path(__file__).resolve().parent / "static"
DESCRIPTION = """
Compact airflow + thermal network for **air-cooled** multi-GPU workstations
(not CFD; GPU water blocks are out of scope; Celsius).

Agents: POST a full PC spec to `/api/v1/simulate`, a base spec plus variants to
`/api/v1/rank`, or a base spec plus factors to `/api/v1/sweep`. Start from a
saved build at `/api/v1/builds/{id}` and the id lists at `/api/v1/presets`.

Typical accuracy ±5–10 °C absolute; better for ranking than for absolute
temperatures.
"""
TAGS = [
    {"name": "agent API v1", "description": "Stable JSON interface for agents and scripts."},
    {"name": "visualizer", "description": "Endpoints the browser UI uses. Not versioned."},
]
app = FastAPI(title="gpusim", version=__version__, description=DESCRIPTION, openapi_tags=TAGS)
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.middleware("http")
async def _revalidate_static(request, call_next):
    """Browsers revalidate the page and its modules, so a restarted server is never stale."""
    response = await call_next(request)
    if request.url.path == "/" or request.url.path.startswith("/static/") or request.url.path.startswith("/usage"):
        response.headers["Cache-Control"] = "no-cache"
    return response


class OptimizeRequest(BaseModel):
    cards: int = 4
    case: str = "meshify2xl"
    mc: int = 40


class WorthRequest(BaseModel):
    build: BuildCfg
    mc: int = 0


class ScenarioRequest(BaseModel):
    scenario_id: str
    step: int = 0


def _http(exc: ApiError) -> HTTPException:
    return HTTPException(exc.status, exc.detail)


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/health", tags=["visualizer"])
def health():
    return {"ok": True, "units": "C", "water_blocks": False}


@app.get("/api/presets", tags=["visualizer"])
def presets():
    return presets_payload()


@app.get("/api/build/{build_id}", tags=["visualizer"])
def get_build(build_id: str):
    try:
        return build_payload(build_id)
    except ApiError as exc:
        raise _http(exc) from exc


@app.post("/api/solve", tags=["visualizer"])
def api_solve(build: BuildCfg):
    try:
        return solve_payload(build)
    except ApiError as exc:
        raise _http(exc) from exc


@app.post("/api/optimize", tags=["visualizer"])
def api_optimize(body: OptimizeRequest):
    try:
        return optimize_payload(body.model_dump())
    except ApiError as exc:
        raise _http(exc) from exc


@app.post("/api/worth", tags=["visualizer"])
def api_worth(body: WorthRequest):
    """Rank single changes to the build by how much cooler the hottest die gets (paired MC band when mc > 0)."""
    try:
        return worth_payload({"build": body.build, "mc": body.mc})
    except ApiError as exc:
        raise _http(exc) from exc


@app.post("/api/scenario", tags=["visualizer"])
def api_scenario(body: ScenarioRequest):
    try:
        return scenario_payload(body.model_dump())
    except ApiError as exc:
        raise _http(exc) from exc


# ------------------------------------------------------------------ agent API v1


def _bad(exc: Exception) -> HTTPException:
    return HTTPException(422, str(exc))


@app.post("/api/v1/simulate", tags=["agent API v1"])
def v1_simulate(spec: simapi.SimSpec):
    """Solve one full PC spec. Returns per-card die / memory / inlet / exhaust
    temperatures, flow, fan duty, throttle state, case pressure, and (with
    `options.detail = "full"`) the flow network and each card's thermal chain."""
    try:
        return simapi.simulate(spec)
    except Exception as exc:
        raise _bad(exc) from exc


@app.post("/api/v1/rank", tags=["agent API v1"])
def v1_rank(request: simapi.RankRequest):
    """Solve a base spec and named variants (merge patches and/or macro settings),
    then rank them by hottest die. A variant that fails reports its error in place."""
    try:
        return simapi.rank(request)
    except Exception as exc:
        raise _bad(exc) from exc


@app.post("/api/v1/sweep", tags=["agent API v1"])
def v1_sweep(request: simapi.SweepRequest):
    """Full factorial over the given factors (≤ 256 cells), ranked."""
    try:
        return simapi.sweep(request)
    except Exception as exc:
        raise _bad(exc) from exc


@app.get("/api/v1/presets", tags=["agent API v1"])
def v1_presets():
    """Ids an agent can reference: cases (with slot counts and mount ids), cards,
    fans, radiators, saved builds, fan curves, seal levels, sweep macros."""
    lib = get_library()
    return {
        "api_version": simapi.API_VERSION,
        "cases": [
            {
                "id": c.id,
                "name": c.name,
                "horizontal_slots": c.horizontal_slots,
                "vertical_slots": [v.id for v in c.vertical_positions],
                "mounts": [{"id": m.id, "panel": m.panel, "size_mm": m.size_mm} for m in c.mounts],
                "radiator_support": c.radiator_support,
            }
            for c in lib.cases.values()
        ],
        "cards": [
            {"id": c.id, "name": c.name, "tbp_w": c.tbp_w, "slots": c.slots, "cooler": c.cooler, "template": c.template}
            for c in lib.cards.values()
        ],
        "fans": [
            {"id": f.id, "name": f.name, "size_mm": f.size_mm, "airflow_cfm": f.airflow_cfm,
             "static_pressure_mmh2o": f.static_pressure_mmh2o, "rpm_max": f.rpm_max}
            for f in lib.fans.values()
        ],
        "radiators": [{"id": r.id, "name": r.name, "size_mm": r.size_mm} for r in lib.radiators.values()],
        "builds": [{"id": b.id, "name": b.name, "case": b.case, "illustrative_mock": b.illustrative_mock} for b in lib.builds.values()],
        "fan_curves": ["stock", *GLOBAL_FAN_CURVES, "custom"],
        "fan_curve_aliases": {"maxq_aggressive": "custom_accelerated"},
        "seal_levels": simapi.seal_table(),
        "sweep_macros": list(simapi.MACROS),
        "accuracy": simapi.ACCURACY,
        "scope": simapi.SCOPE,
    }


@app.get("/api/v1/builds/{build_id}", tags=["agent API v1"])
def v1_build(build_id: str):
    """A saved build, as a ready-to-edit `build` object for /simulate."""
    lib = get_library()
    if build_id not in lib.builds:
        raise HTTPException(404, f"Unknown build {build_id}. Known: {', '.join(sorted(lib.builds))}")
    return lib.builds[build_id].model_dump()


@app.get("/api/v1/schema", tags=["agent API v1"])
def v1_schema():
    """JSON Schemas for the request bodies (same as docs/simspec.schema.json)."""
    return simapi_schemas()


@app.post("/usage/collect", include_in_schema=False)
async def usage_collect(request: Request):
    """Append a batch of usage events. The body is not copied into the error or the access record."""
    raw = await request.body()
    if len(raw) > 32_000:
        return Response(status_code=413)
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return Response(status_code=400)
    events = payload.get("events") if isinstance(payload, dict) else None
    if not isinstance(events, list):
        return Response(status_code=400)
    record_events(events, country_from_headers(request.headers))
    return Response(status_code=204)


@app.get("/usage/summary.json", include_in_schema=False)
def usage_summary():
    return summary_for()


@app.get("/usage/events.jsonl", include_in_schema=False)
def usage_events():
    path = log_path()
    if not path.is_file():
        return Response(status_code=404)
    return FileResponse(path, media_type="text/plain; charset=utf-8")


@app.get("/usage", include_in_schema=False)
def usage_page():
    return FileResponse(STATIC / "usage.html")


def simapi_schemas() -> dict:
    return {
        "SimSpec": simapi.SimSpec.model_json_schema(),
        "RankRequest": simapi.RankRequest.model_json_schema(),
        "SweepRequest": simapi.SweepRequest.model_json_schema(),
    }
