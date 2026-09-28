"""Every preset number must be sourced or explicitly approximate.

File-level `_source` / `_approximate` + `_assumption` inherit downward.
A mapping that holds `value` is a single cited quantity. Bare numbers use the
inherited context. Booleans and strings are not measurements.
"""

from __future__ import annotations

from typing import Any


_QUANTITY_KEYS = {"value", "source", "approximate", "assumption", "unit", "notes"}


class CitationError(ValueError):
    pass


def validate_citations(node: Any, path: str = "root") -> None:
    errors: list[str] = []
    _walk(node, source=None, approximate=False, assumption=None, path=path, errors=errors)
    if errors:
        raise CitationError("; ".join(errors[:12]))


def _walk(node, source, approximate, assumption, path, errors) -> None:
    if isinstance(node, dict):
        source = node.get("_source", source)
        if "_approximate" in node:
            approximate = bool(node["_approximate"])
        if "_assumption" in node:
            assumption = node["_assumption"]
        data_keys = [k for k in node if not str(k).startswith("_")]
        if "value" in node and set(data_keys) <= _QUANTITY_KEYS:
            _check_quantity(node, source, approximate, assumption, path, errors)
            return
        for key in data_keys:
            _walk(node[key], source, approximate, assumption, f"{path}.{key}", errors)
        return
    if isinstance(node, list):
        for i, item in enumerate(node):
            _walk(item, source, approximate, assumption, f"{path}[{i}]", errors)
        return
    if isinstance(node, bool) or node is None or isinstance(node, str):
        return
    if isinstance(node, (int, float)):
        _require(source, approximate, assumption, path, errors)


def _check_quantity(node, source, approximate, assumption, path, errors) -> None:
    approx = bool(node.get("approximate", approximate))
    src = node.get("source", source)
    assum = node.get("assumption", assumption)
    _require(src, approx, assum, path, errors)


def _require(source, approximate, assumption, path, errors) -> None:
    if approximate:
        if not assumption:
            errors.append(f"{path}: approximate number is missing an assumption")
    elif not source:
        errors.append(f"{path}: number is missing a source")


def normalize(node: Any) -> Any:
    """Drop citation metadata and unwrap {value: ...} quantities."""
    if isinstance(node, dict):
        data_keys = [k for k in node if not str(k).startswith("_")]
        if "value" in node and set(data_keys) <= _QUANTITY_KEYS:
            return normalize(node["value"])
        return {k: normalize(node[k]) for k in data_keys}
    if isinstance(node, list):
        return [normalize(item) for item in node]
    return node
