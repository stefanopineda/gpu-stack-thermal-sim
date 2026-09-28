"""Agent-facing API: one full PC spec in, per-card temperatures out.

The HTTP routes in gpusim/ui/app.py and the `gpusim simulate / rank / sweep`
CLI commands are thin wrappers around these functions, so the same JSON works
over HTTP, on the command line, and in Python.

A spec is a `BuildCfg` (case id, mounts, GPUs and slots, seals, CPU, shroud,
curves) plus optional inline fans and cards that are not in `presets/`.
"""

from __future__ import annotations

import copy
import itertools
from dataclasses import replace
from typing import Any, Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator

from gpusim.calib import CARD, SEAL_NAMES, SEAL_OPEN_FRACTION
from gpusim.factors import LEAKAGE_SEALS, apply_leakage, apply_pressure, layout_slots
from gpusim.layout import is_vertical, slot_number
from gpusim.library import Library, get_library
from gpusim.models import BuildCfg, CardModel, FanModel, canonical_curve
from gpusim.physics import quadratic_curve
from gpusim.solve import solve, solve_monte_carlo

API_VERSION = "1"
SPEC_REVISION = 4
ACCURACY = (
    "Typical accuracy ±5–10 °C absolute; better for ranking configurations than for "
    "absolute temperatures. Compact flow + thermal network, not CFD."
)
SCOPE = "Air-cooled GPUs only. GPU water blocks are out of scope. Units are Celsius."
MAX_VARIANTS = 64
MAX_CELLS = 256


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FanSpec(_Strict):
    """A fan that is not in presets/fans. Give P–Q points, or the two intercepts."""

    id: str
    name: str | None = None
    size_mm: int = Field(description="120, 140, 170 …")
    rpm_max: float
    rpm_min: float = 0.0
    airflow_cfm: float | None = Field(None, description="Free-air flow at rpm_max")
    static_pressure_mmh2o: float | None = Field(None, description="Dead-head pressure at rpm_max")
    pq_points_m3h_mmh2o: list[list[float]] | None = Field(
        None, description="[[m³/h, mmH₂O], …] at rpm_max. Overrides the intercepts."
    )

    @model_validator(mode="after")
    def _curve_given(self):
        if self.pq_points_m3h_mmh2o is None and (self.airflow_cfm is None or self.static_pressure_mmh2o is None):
            raise ValueError("fan needs pq_points_m3h_mmh2o or both airflow_cfm and static_pressure_mmh2o")
        return self

    def to_model(self) -> FanModel:
        if self.pq_points_m3h_mmh2o:
            points = sorted(self.pq_points_m3h_mmh2o)
            qmax = max(p[0] for p in points)
            pmax = max(p[1] for p in points)
            approximate = False
        else:
            qmax = float(self.airflow_cfm) * 1.69901
            pmax = float(self.static_pressure_mmh2o)
            points = quadratic_curve(qmax, pmax, n=9)
            approximate = True
        return FanModel(
            id=self.id,
            name=self.name or self.id,
            size_mm=self.size_mm,
            rpm_min=self.rpm_min,
            rpm_max=self.rpm_max,
            airflow_m3h=qmax,
            airflow_cfm=qmax / 1.69901,
            static_pressure_mmh2o=pmax,
            pq_m3h=[p[0] for p in points],
            pq_mmh2o=[p[1] for p in points],
            approximate=approximate,
            notes="Inline API fan." + (" Generic quadratic curve between the intercepts." if approximate else ""),
        )


class CardSpec(_Strict):
    """A card that is not in presets/cards. It borrows a calibrated cooler."""

    id: str
    name: str | None = None
    calibration_from: str = Field(
        description="Existing card id whose cooler physics to reuse, e.g. rtx-5090-fe or rtx-pro-6000-blackwell-maxq"
    )
    tbp_w: float | None = None
    slots: int | None = None
    length_mm: float | None = None
    height_mm: float | None = None
    thickness_mm: float | None = None
    throttle_c: float | None = None
    cutoff_c: float | None = None
    stock_curve: list[list[float]] | None = Field(None, description="[[°C, duty 0–1], …]")
    tuning_overrides: dict[str, float] = Field(
        default_factory=dict,
        description="Override calibration numbers, e.g. {'qmax_m3s': 0.05, 'r_tim': 0.04}",
    )


class SimOptions(_Strict):
    throttle: bool = Field(True, description="Solve the throttled equilibrium as well as the unthrottled one")
    mc: int = Field(0, ge=0, le=400, description="Monte Carlo samples for 5th–95th bands (0 = nominal only)")
    seed: int = 12345
    detail: Literal["summary", "full"] = Field(
        "summary", description="full adds the flow network, node temperatures and per-card thermal breakdown"
    )


class SimSpec(_Strict):
    build: BuildCfg
    extra_fans: list[FanSpec] = Field(default_factory=list)
    extra_cards: list[CardSpec] = Field(default_factory=list)
    options: SimOptions = Field(default_factory=SimOptions)


class Variant(_Strict):
    name: str
    patch: dict[str, Any] = Field(
        default_factory=dict,
        description="JSON merge patch (RFC 7396) on the base build. Lists replace whole lists.",
    )
    set: dict[str, Any] = Field(
        default_factory=dict,
        description="Dotted-path or macro settings, same keys as /sweep factors (e.g. {'spacing': 'gap1', 'gpus.*.fan_curve': 'custom_accelerated'})",
    )


class RankRequest(_Strict):
    base: SimSpec
    variants: list[Variant] = Field(min_length=1, max_length=MAX_VARIANTS)
    include_base: bool = True


class SweepRequest(_Strict):
    base: SimSpec
    factors: dict[str, list[Any]] = Field(
        description=(
            "Factor → levels. Macros: spacing (stacked|gap1|gap2|gap3), pressure (standard|high), "
            "shroud (off|on|passive), leakage (sealed|leaky), fan_curve (stock|custom_accelerated), "
            "cpu_cooling (air|water), obstruction (low|medium|high), cables (clean|cluttered). "
            "Anything else is a dotted path into the build, e.g. shroud.count, gpus.*.power_limit_w, ambient_c."
        )
    )


# ---------------------------------------------------------------- library


def library_with(spec: SimSpec, base: Library | None = None) -> Library:
    """The preset library plus the spec's inline fans and cards."""
    lib = base or get_library()
    if not spec.extra_fans and not spec.extra_cards:
        return lib
    fans = dict(lib.fans)
    cards = dict(lib.cards)
    for fan in spec.extra_fans:
        fans[fan.id] = fan.to_model()
    for extra in spec.extra_cards:
        if extra.calibration_from not in cards or extra.calibration_from not in CARD:
            raise ValueError(
                f"card {extra.id}: calibration_from '{extra.calibration_from}' is not a calibrated card. "
                f"Use one of {sorted(CARD)}"
            )
        parent = cards[extra.calibration_from]
        data = parent.model_dump()
        data.update(
            {
                "id": extra.id,
                "name": extra.name or extra.id,
                "template": False,
                "calibration_from": extra.calibration_from,
                "tuning_overrides": dict(extra.tuning_overrides),
                "notes": f"Inline API card, cooler physics from {extra.calibration_from}.",
            }
        )
        for key in ("tbp_w", "slots", "length_mm", "height_mm", "thickness_mm", "throttle_c", "cutoff_c"):
            value = getattr(extra, key)
            if value is not None:
                data[key] = value
        if extra.stock_curve:
            data["fan_curves"] = {**data["fan_curves"], "stock": extra.stock_curve}
        cards[extra.id] = CardModel.model_validate(data)
    return replace(lib, fans=fans, cards=cards)


def validate_refs(build: BuildCfg, lib: Library) -> list[str]:
    """Human-readable problems with ids in a build. Empty when it can be solved."""
    problems = []
    if not build.open_air and build.case not in lib.cases:
        problems.append(f"unknown case '{build.case}'. Known: {', '.join(sorted(lib.cases))}")
    for gpu in build.gpus:
        if gpu.card not in lib.cards:
            problems.append(f"{gpu.id}: unknown card '{gpu.card}'. Known: {', '.join(sorted(lib.cards))}")
    for mount in build.mounts:
        if mount.state == "fan" and mount.fan and mount.fan not in lib.fans:
            problems.append(f"mount {mount.id}: unknown fan '{mount.fan}'")
    if build.radiator.model and build.radiator.model not in lib.radiators:
        problems.append(f"unknown radiator '{build.radiator.model}'")
    if build.shroud.mode == "on" and build.shroud.fan not in lib.fans:
        problems.append(f"unknown shroud fan '{build.shroud.fan}'")
    case = lib.cases.get(build.case)
    if case is not None:
        valid = {str(s) for s in range(1, case.horizontal_slots + 1)} | {v.id for v in case.vertical_positions}
        seen: dict[int, str] = {}
        for gpu in build.gpus:
            if str(gpu.slot) not in valid:
                problems.append(f"{gpu.id}: slot '{gpu.slot}' is not on {case.id} ({case.horizontal_slots} horizontal)")
                continue
            if is_vertical(gpu.slot) or gpu.card not in lib.cards:
                continue
            start = slot_number(gpu.slot)
            width = lib.cards[gpu.card].slots
            if start + width - 1 > case.horizontal_slots:
                problems.append(f"{gpu.id}: a {width}-slot card in slot {start} runs past slot {case.horizontal_slots}")
            for s in range(start, start + width):
                if s in seen:
                    problems.append(f"{gpu.id} overlaps {seen[s]} at slot {s}")
                seen[s] = gpu.id
    return problems


# ---------------------------------------------------------------- one spec


def _card_row(card) -> dict:
    return {
        "id": card.id,
        "slot": card.slot,
        "card": card.card,
        "cooler": card.cooler,
        "fan_curve": card.fan_curve,
        "t_die_c": round(card.t_die_c, 2),
        "t_die_unthrottled_c": round(card.t_die_unthrottled_c, 2),
        "t_mem_c": round(card.t_mem_c, 2),
        "t_inlet_c": round(card.t_in_c, 2),
        "t_exhaust_c": round(card.t_exh_c, 2),
        "flow_cfm": round(card.flow_cfm, 2),
        "fan_duty": round(card.duty, 3),
        "power_w": round(card.power_w, 1),
        "power_unthrottled_w": round(card.power_unthrottled_w, 1),
        "throttle": card.throttle,
        "inlet_gap_mm": round(card.gap_mm, 2),
        "inlet_gap_state": card.gap_state,
    }


def _summary(sol) -> dict:
    return {
        "hottest_die_c": round(sol.hottest_die, 2),
        "hottest_unthrottled_c": round(sol.hottest_unthrottled, 2),
        "mean_die_c": round(sol.mean_die, 2),
        "any_throttle": any(c.throttle for c in sol.cards),
        "case_pressure_pa": round(sol.case_pressure_pa, 2),
        "gpu_zone_pressure_pa": round(sol.gpu_pressure_pa, 2),
        "heat_w": round(sol.heat_w, 1),
        "energy_balance_error": sol.energy_error,
        "mass_residual_kg_s": sol.residual_kg_s,
        "solve_time_s": round(sol.solve_time_s, 4),
    }


def _mc(build: BuildCfg, lib: Library, n: int, seed: int) -> dict | None:
    if not n:
        return None
    draws = solve_monte_carlo(build, n=n, seed=seed, library=lib)
    hottest = np.array([d.hottest_unthrottled for d in draws])
    per_card = []
    for i, card in enumerate(draws[0].cards):
        temps = [d.cards[i].t_die_unthrottled_c for d in draws]
        per_card.append(
            {"id": card.id, "p05_c": float(np.percentile(temps, 5)), "p95_c": float(np.percentile(temps, 95))}
        )
    return {
        "n": n,
        "seed": seed,
        "hottest_unthrottled_p05_c": float(np.percentile(hottest, 5)),
        "hottest_unthrottled_p95_c": float(np.percentile(hottest, 95)),
        "per_card": per_card,
        "note": "Bands are on the unthrottled die. Distributions: docs/CALIBRATION.md.",
    }


def simulate_build(build: BuildCfg, lib: Library, options: SimOptions | None = None) -> dict:
    options = options or SimOptions()
    problems = validate_refs(build, lib)
    if problems:
        raise ValueError("; ".join(problems))
    sol = solve(build, lib, do_throttle=options.throttle)
    out = {
        "api_version": API_VERSION,
        "spec_revision": SPEC_REVISION,
        "build_id": build.id,
        "build_name": build.name,
        "illustrative_mock": build.illustrative_mock,
        "summary": _summary(sol),
        "cards": [_card_row(c) for c in sol.cards],
        "plume": sol.plume,
        "notes": sol.notes,
        "accuracy": ACCURACY,
        "scope": SCOPE,
    }
    if options.detail == "full":
        out["thermal"] = [{"id": c.id, **(c.thermal or {})} for c in sol.cards]
        out["network"] = {
            "branches": sol.branches,
            "pressures_pa": sol.pressures,
            "node_temp_c": sol.node_temp,
            "node_mass_residual_kg_s": sol.node_residual,
        }
    mc = _mc(build, lib, options.mc, options.seed)
    if mc:
        out["monte_carlo"] = mc
    return out


def simulate(spec: SimSpec) -> dict:
    lib = library_with(spec)
    return simulate_build(spec.build, lib, spec.options)


# ---------------------------------------------------------------- variants


def merge_patch(target: Any, patch: Any) -> Any:
    """RFC 7396 JSON merge patch."""
    if not isinstance(patch, dict):
        return copy.deepcopy(patch)
    out = dict(target) if isinstance(target, dict) else {}
    for key, value in patch.items():
        if value is None:
            out.pop(key, None)
        else:
            out[key] = merge_patch(out.get(key), value)
    return out


def _set_path(data: dict, path: str, value: Any) -> None:
    parts = path.split(".")

    def walk(node, i):
        key = parts[i]
        last = i == len(parts) - 1
        if isinstance(node, list):
            targets = range(len(node)) if key == "*" else [int(key)]
            for index in targets:
                if last:
                    node[index] = copy.deepcopy(value)
                else:
                    walk(node[index], i + 1)
            return
        if not isinstance(node, dict):
            raise ValueError(f"path '{path}' does not reach a field")
        if last:
            node[key] = copy.deepcopy(value)
        else:
            if key not in node or node[key] is None:
                node[key] = {}
            walk(node[key], i + 1)

    walk(data, 0)


MACROS = ("spacing", "pressure", "shroud", "leakage", "fan_curve", "cpu_cooling", "obstruction", "cables")


def _respace(build: BuildCfg, spacing: str, lib: Library) -> None:
    gaps = {"stacked": 0, "gap1": 1, "gap2": 2, "gap3": 3}
    if spacing not in gaps:
        raise ValueError(f"spacing must be one of {sorted(gaps)}")
    case = lib.cases[build.case]
    horizontal = [g for g in build.gpus if not is_vertical(g.slot)]
    horizontal.sort(key=lambda g: slot_number(g.slot))
    cursor = 1
    for gpu in horizontal:
        width = lib.cards[gpu.card].slots
        if cursor + width - 1 > case.horizontal_slots:
            raise ValueError(f"{spacing}: {len(horizontal)} cards do not fit in {case.horizontal_slots} slots")
        gpu.slot = str(cursor)
        cursor += width + gaps[spacing]


def apply_settings(build: BuildCfg, settings: dict[str, Any], lib: Library) -> BuildCfg:
    """Apply macro factors first (spacing needs card widths), then dotted paths."""
    out = build.model_copy(deep=True)
    paths = {}
    for key, value in settings.items():
        if key == "spacing":
            _respace(out, value, lib)
        elif key == "pressure":
            apply_pressure(out, value)
        elif key == "shroud":
            if value not in ("off", "on", "passive"):
                raise ValueError("shroud must be off, on or passive")
            out.shroud.mode = value
        elif key == "leakage":
            if value not in LEAKAGE_SEALS:
                raise ValueError(f"leakage must be one of {sorted(LEAKAGE_SEALS)}")
            apply_leakage(out, value)
        elif key == "fan_curve":
            for gpu in out.gpus:
                gpu.fan_curve = canonical_curve(value)
        elif key == "cpu_cooling":
            out.cpu.cooling = value
        elif key in ("obstruction", "cables"):
            setattr(out, key, value)
        else:
            paths[key] = value
    if paths:
        data = out.model_dump()
        for path, value in paths.items():
            _set_path(data, path, value)
        out = BuildCfg.model_validate(data)
    return out


def _ranked(rows: list[dict]) -> list[dict]:
    good = [r for r in rows if "error" not in r]
    bad = [r for r in rows if "error" in r]
    good.sort(
        key=lambda r: (
            r["summary"]["hottest_die_c"],
            r["summary"]["hottest_unthrottled_c"],
            r["summary"]["mean_die_c"],
            r["name"],
        )
    )
    for rank, row in enumerate(good, start=1):
        row["rank"] = rank
    return good + bad


def _row(name: str, build: BuildCfg, lib: Library, options: SimOptions, settings: dict | None = None) -> dict:
    try:
        result = simulate_build(build, lib, options)
    except Exception as exc:  # one bad variant must not sink the batch
        return {"name": name, "settings": settings or {}, "error": str(exc)}
    row = {"name": name, "settings": settings or {}, **result}
    return row


def rank(request: RankRequest) -> dict:
    lib = library_with(request.base)
    base = request.base.build
    options = request.base.options
    rows = []
    if request.include_base:
        rows.append(_row("base", base, lib, options))
    for variant in request.variants:
        try:
            patched = BuildCfg.model_validate(merge_patch(base.model_dump(), variant.patch)) if variant.patch else base
            patched = apply_settings(patched, variant.set, lib) if variant.set else patched
        except Exception as exc:
            rows.append({"name": variant.name, "error": f"could not apply variant: {exc}"})
            continue
        rows.append(_row(variant.name, patched, lib, options, {**variant.set, **({"patch": variant.patch} if variant.patch else {})}))
    return {
        "api_version": API_VERSION,
        "ranking": "hottest throttled die, then hottest unthrottled die, then mean die; lower is better",
        "results": _ranked(rows),
        "accuracy": ACCURACY,
        "scope": SCOPE,
    }


def sweep(request: SweepRequest) -> dict:
    lib = library_with(request.base)
    keys = list(request.factors)
    levels = [request.factors[k] for k in keys]
    if not keys or any(not v for v in levels):
        raise ValueError("factors must name at least one factor with at least one level")
    total = int(np.prod([len(v) for v in levels]))
    if total > MAX_CELLS:
        raise ValueError(f"{total} cells requested; the limit is {MAX_CELLS}")
    rows = []
    for combo in itertools.product(*levels):
        settings = dict(zip(keys, combo))
        name = ", ".join(f"{k}={v}" for k, v in settings.items())
        try:
            build = apply_settings(request.base.build, settings, lib)
        except Exception as exc:
            rows.append({"name": name, "settings": settings, "error": f"could not apply: {exc}"})
            continue
        rows.append(_row(name, build, lib, request.base.options, settings))
    return {
        "api_version": API_VERSION,
        "cells": total,
        "factors": request.factors,
        "ranking": "hottest throttled die, then hottest unthrottled die, then mean die; lower is better",
        "results": _ranked(rows),
        "accuracy": ACCURACY,
        "scope": SCOPE,
    }


def seal_table() -> list[dict]:
    return [
        {"level": level, "name": SEAL_NAMES[level], "open_fraction": SEAL_OPEN_FRACTION[level]}
        for level in sorted(SEAL_NAMES)
    ]
