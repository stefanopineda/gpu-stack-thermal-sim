"""JSON routes the visualizer uses, with no web framework.

The FastAPI app and the in-browser Pyodide build both call these functions,
so a slider on gpuism.com runs the same solver as `gpusim ui`.
"""

from __future__ import annotations

import json

from gpusim import api as simapi
from gpusim.calib import CABLE_K, GLOBAL, GLOBAL_FAN_CURVES, OBSTRUCTION_K
from gpusim.factors import apply_scenario_step
from gpusim.library import get_library
from gpusim.models import BuildCfg
from gpusim.solve import solve


class ApiError(Exception):
    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status = status
        self.detail = detail


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


def presets_payload() -> dict:
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
        "plume": {
            "entrainment": GLOBAL["plume_entrainment"],
            "stack_cd": GLOBAL["stack_cd"],
            "stack_length_mm": GLOBAL["stack_length_mm"],
        },
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
                "steps": [{"id": st.id, "title": st.title, "talking_points": st.talking_points} for st in s.steps],
            }
            for s in lib.scenarios.values()
        ],
    }


def build_payload(build_id: str) -> dict:
    lib = get_library()
    if build_id not in lib.builds:
        raise ApiError(404, f"Unknown build {build_id}")
    return lib.builds[build_id].model_dump(mode="json")


def solve_payload(data: dict) -> dict:
    build = data if isinstance(data, BuildCfg) else BuildCfg.model_validate(data)
    lib = get_library()
    if not build.open_air and build.case not in lib.cases:
        raise ApiError(400, f"Unknown case {build.case}")
    try:
        return solve(build, lib).to_dict()
    except ApiError:
        raise
    except Exception as exc:
        raise ApiError(400, str(exc)) from exc


def optimize_payload(data: dict) -> dict:
    from gpusim.optimize import optimize

    try:
        return optimize(
            cards=int(data.get("cards", 4)),
            case_id=str(data.get("case", "meshify2xl")),
            mc=int(data.get("mc", 40)),
        )
    except ApiError:
        raise
    except Exception as exc:
        raise ApiError(400, str(exc)) from exc


def scenario_payload(data: dict) -> dict:
    lib = get_library()
    scenario_id = data.get("scenario_id")
    if scenario_id not in lib.scenarios:
        raise ApiError(404, "Unknown scenario")
    scenario = lib.scenarios[scenario_id]
    step_index = int(data.get("step", 0))
    if step_index < 0 or step_index >= len(scenario.steps):
        raise ApiError(400, "Step out of range")
    step = scenario.steps[step_index]
    base = lib.builds[scenario.base_build]
    if step.layout == "optimal":
        result = optimize_payload({"cards": 4, "case": base.case, "mc": 24})
        return {
            "scenario": scenario.model_dump(mode="json"),
            "step_index": step_index,
            "step": step.model_dump(mode="json"),
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
        "step_index": step_index,
        "step": step.model_dump(mode="json"),
        "build": configured.model_dump(mode="json"),
        "solution": sol.to_dict(),
        "optimal": None,
    }


def dispatch(method: str, path: str, body: str | None = None) -> tuple[int, str]:
    """Return an HTTP status and a JSON body. Used by the Pyodide worker."""
    method = (method or "GET").upper()
    path = (path or "/").split("?", 1)[0].rstrip("/") or "/"
    try:
        if method == "GET" and path == "/api/health":
            payload = {"ok": True, "units": "C", "water_blocks": False, "engine": "browser"}
        elif method == "GET" and path == "/api/presets":
            payload = presets_payload()
        elif method == "GET" and path.startswith("/api/build/"):
            payload = build_payload(path.rsplit("/", 1)[-1])
        elif method == "POST" and path == "/api/solve":
            payload = solve_payload(json.loads(body or "{}"))
        elif method == "POST" and path == "/api/optimize":
            payload = optimize_payload(json.loads(body or "{}"))
        elif method == "POST" and path == "/api/scenario":
            payload = scenario_payload(json.loads(body or "{}"))
        else:
            raise ApiError(404, f"No browser route for {method} {path}")
        return 200, json.dumps(payload)
    except ApiError as exc:
        return exc.status, json.dumps({"detail": exc.detail})
    except Exception as exc:
        return 400, json.dumps({"detail": str(exc)})
