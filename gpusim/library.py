"""Load cited YAML presets into runtime models."""

from __future__ import annotations

import functools
import os
from dataclasses import dataclass
from pathlib import Path

import yaml

from gpusim.cite import normalize, validate_citations
from gpusim.models import (
    BuildCfg,
    CardModel,
    CaseModel,
    FanModel,
    RadiatorModel,
    Scenario,
)

_PACKAGE_ROOT = Path(__file__).resolve().parent.parent


def preset_root() -> Path:
    env = os.environ.get("GPUSIM_PRESETS")
    if env:
        return Path(env)
    cwd = Path.cwd() / "presets"
    if cwd.is_dir():
        return cwd
    return _PACKAGE_ROOT / "presets"


@dataclass
class Library:
    fans: dict[str, FanModel]
    cards: dict[str, CardModel]
    radiators: dict[str, RadiatorModel]
    cases: dict[str, CaseModel]
    builds: dict[str, BuildCfg]
    scenarios: dict[str, Scenario]
    root: Path


def _load_mapping(folder: Path, model):
    found = {}
    if not folder.is_dir():
        raise FileNotFoundError(f"Missing preset directory {folder}")
    for path in sorted(folder.glob("*.yaml")):
        raw = yaml.safe_load(path.read_text())
        validate_citations(raw, str(path))
        data = normalize(raw)
        if model is FanModel:
            points = data.pop("pq_points_m3h_mmh2o")
            data["pq_m3h"] = [row[0] for row in points]
            data["pq_mmh2o"] = [row[1] for row in points]
        obj = model.model_validate(data)
        if obj.id in found:
            raise ValueError(f"Duplicate id {obj.id} in {path}")
        found[obj.id] = obj
    if not found:
        raise FileNotFoundError(f"No YAML presets in {folder}")
    return found


def load_library(root: Path | None = None) -> Library:
    root = root or preset_root()
    return Library(
        fans=_load_mapping(root / "fans", FanModel),
        cards=_load_mapping(root / "cards", CardModel),
        radiators=_load_mapping(root / "radiators", RadiatorModel),
        cases=_load_mapping(root / "cases", CaseModel),
        builds=_load_mapping(root / "builds", BuildCfg),
        scenarios=_load_mapping(root / "scenarios", Scenario),
        root=root,
    )


@functools.lru_cache(maxsize=1)
def get_library() -> Library:
    return load_library()


def clear_library_cache() -> None:
    get_library.cache_clear()
