"""FastAPI visualizer. The solver stays in Python; the browser only draws."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from gpusim.factors import apply_scenario_step
from gpusim.library import get_library
from gpusim.models import BuildCfg
from gpusim.solve import solve

STATIC = Path(__file__).resolve().parent / "static"
app = FastAPI(title="gpusim", version="0.3.0")
app.mount("/static", StaticFiles(directory=STATIC), name="static")


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
        "notes": case.notes,
        "dimension_note": case.dimension_note,
    }


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/health")
def health():
    return {"ok": True, "units": "C", "water_blocks": False}


@app.get("/api/presets")
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
                "fan_curves": list(c.fan_curves),
                "notes": c.notes,
            }
            for c in lib.cards.values()
        ],
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


@app.get("/api/build/{build_id}")
def get_build(build_id: str):
    lib = get_library()
    if build_id not in lib.builds:
        raise HTTPException(404, f"Unknown build {build_id}")
    return lib.builds[build_id].model_dump()


@app.post("/api/solve")
def api_solve(build: BuildCfg):
    lib = get_library()
    if not build.open_air and build.case not in lib.cases:
        raise HTTPException(400, f"Unknown case {build.case}")
    try:
        sol = solve(build, lib)
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc
    return sol.to_dict()


@app.post("/api/optimize")
def api_optimize(body: OptimizeRequest):
    from gpusim.optimize import optimize

    try:
        return optimize(cards=body.cards, case_id=body.case, mc=body.mc)
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/api/scenario")
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
