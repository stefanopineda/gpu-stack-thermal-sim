"""FastAPI app: the visualizer plus the agent API (/api/v1, docs at /docs).

The solver stays in Python; the browser only draws.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from gpusim import __version__
from gpusim import api as simapi
from gpusim.calib import CABLE_K, GLOBAL, GLOBAL_FAN_CURVES, OBSTRUCTION_K
from gpusim.factors import apply_scenario_step
from gpusim.library import get_library
from gpusim.models import BuildCfg
from gpusim.solve import solve

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
    if request.url.path == "/" or request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-cache"
    return response


class OptimizeRequest(BaseModel):
    cards: int = 4
    case: str = "meshify2xl"
    mc: int = 40


class ScenarioRequest(BaseModel):
    scenario_id: str
    step: int = 0


def _fan_public(fan) -> dict:
    return {
        "id": fan.id,
        "name": fan.name,
        "size_mm": fan.size_mm,
        "rpm_max": fan.rpm_max,
        "airflow_cfm": fan.airflow_cfm,
        "static_pressure_mmh2o": fan.static_pressure_mmh2o,
        "approximate": fan.approximate,
        "notes": fan.notes,
    }


def _case_public(case) -> dict:
    return {
        "id": case.id,
        "name": case.name,
        "width_mm": case.width_mm,
        "height_mm": case.height_mm,
        "depth_mm": case.depth_mm,
        "horizontal_slots": case.horizontal_slots,
        "vertical_slots": case.vertical_slots,
        "slot_pitch_mm": case.slot_pitch_mm,
        "top_slot_y_mm": case.top_slot_y_mm,
        "vertical_positions": [v.model_dump() for v in case.vertical_positions],
        "mounts": [m.model_dump() for m in case.mounts],
        "motherboards": case.motherboards,
        "fan_support": case.fan_support,
        "radiator_support": case.radiator_support,
        "side_panel": case.side_panel,
        "psu_shroud": case.psu_shroud,
        "psu_shroud_clearance_mm": case.psu_shroud_clearance_mm,
        "airflow_layout": case.airflow_layout,
        "notes": case.notes,
        "dimension_note": case.dimension_note,
    }


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/health", tags=["visualizer"])
def health():
    return {"ok": True, "units": "C", "water_blocks": False}


@app.get("/api/presets", tags=["visualizer"])
def presets():
    lib = get_library()
    return {
        "accuracy": "Typical accuracy ±5–10 °C absolute; better for ranking configurations than for absolute temperatures.",
        "scope": "Air-cooled only. GPU water blocks are out of scope.",
        "fans": [_fan_public(f) for f in lib.fans.values()],
        "cards": [
            {
                "id": c.id,
                "name": c.name,
                "template": c.template,
                "tbp_w": c.tbp_w,
                "slots": c.slots,
                "length_mm": c.length_mm,
                "height_mm": c.height_mm,
                "thickness_mm": c.thickness_mm,
                "fan_curves": list(c.fan_curves) + [k for k in GLOBAL_FAN_CURVES if k not in c.fan_curves],
                "stock_curve": c.fan_curves.get("stock"),
                "cooler": c.cooler,
                "inlet_faces": c.inlet_faces,
                "inlet_split": c.inlet_split,
                "throttle_c": c.throttle_c,
                "cutoff_c": c.cutoff_c,
                "notes": c.notes,
            }
            for c in lib.cards.values()
        ],
        "global_fan_curves": GLOBAL_FAN_CURVES,
        "seal_levels": simapi.seal_table(),
        "obstruction_k": OBSTRUCTION_K,
        "cable_k": CABLE_K,
        "plume": {"entrainment": GLOBAL["plume_entrainment"], "stack_cd": GLOBAL["stack_cd"], "stack_length_mm": GLOBAL["stack_length_mm"]},
        "radiators": [r.model_dump() for r in lib.radiators.values()],
        "cases": [_case_public(c) for c in lib.cases.values()],
        "builds": [
            {
                "id": b.id,
                "name": b.name,
                "case": b.case,
                "illustrative_mock": b.illustrative_mock,
                "notes": b.notes,
            }
            for b in lib.builds.values()
        ],
        "scenarios": [
            {
                "id": s.id,
                "title": s.title,
                "illustrative_mock": s.illustrative_mock,
                "disclaimer": s.disclaimer,
                "base_build": s.base_build,
                "steps": [
                    {"id": st.id, "title": st.title, "talking_points": st.talking_points}
                    for st in s.steps
                ],
            }
            for s in lib.scenarios.values()
        ],
    }


@app.get("/api/build/{build_id}", tags=["visualizer"])
def get_build(build_id: str):
    lib = get_library()
    if build_id not in lib.builds:
        raise HTTPException(404, f"Unknown build {build_id}")
    return lib.builds[build_id].model_dump()


@app.post("/api/solve", tags=["visualizer"])
def api_solve(build: BuildCfg):
    lib = get_library()
    if not build.open_air and build.case not in lib.cases:
        raise HTTPException(400, f"Unknown case {build.case}")
    try:
        sol = solve(build, lib)
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc
    return sol.to_dict()


@app.post("/api/optimize", tags=["visualizer"])
def api_optimize(body: OptimizeRequest):
    from gpusim.optimize import optimize

    try:
        return optimize(cards=body.cards, case_id=body.case, mc=body.mc)
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/api/scenario", tags=["visualizer"])
def api_scenario(body: ScenarioRequest):
    lib = get_library()
    if body.scenario_id not in lib.scenarios:
        raise HTTPException(404, "Unknown scenario")
    scenario = lib.scenarios[body.scenario_id]
    if body.step < 0 or body.step >= len(scenario.steps):
        raise HTTPException(400, "Step out of range")
    step = scenario.steps[body.step]
    base = lib.builds[scenario.base_build]
    if step.layout == "optimal":
        from gpusim.optimize import optimize

        result = optimize(cards=4, case_id=base.case, mc=24)
        return {
            "scenario": scenario.model_dump(),
            "step_index": body.step,
            "step": step.model_dump(),
            "build": result["build"],
            "solution": None,
            "optimal": result,
        }
    configured = apply_scenario_step(base, step, lib)
    sol = solve(configured, lib)
    return {
        "scenario": {
            "id": scenario.id,
            "title": scenario.title,
            "illustrative_mock": scenario.illustrative_mock,
            "disclaimer": scenario.disclaimer,
        },
        "step_index": body.step,
        "step": step.model_dump(),
        "build": configured.model_dump(),
        "solution": sol.to_dict(),
        "optimal": None,
    }


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


def simapi_schemas() -> dict:
    return {
        "SimSpec": simapi.SimSpec.model_json_schema(),
        "RankRequest": simapi.RankRequest.model_json_schema(),
        "SweepRequest": simapi.SweepRequest.model_json_schema(),
    }
