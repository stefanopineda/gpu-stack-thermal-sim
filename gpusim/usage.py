"""First-party usage log for the visualizer.

`gpusim ui` appends sanitized events to ``usage/events.jsonl`` and serves totals
at ``/usage``. The public site is static GitHub Pages: it cannot accept
``POST /usage/collect``. The browser still records a visit locally and beacons
that same path. Pages does not add a country header the page can read, and this
module does not look up IP addresses.
"""

from __future__ import annotations

import json
import os
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

# Dwell buckets. Phone tabs and the desktop Case / Split / Network switch.
# `worth` on a desktop is counted as well as the open view, so those rows overlap.
# `split` is the phone Split tab. `view_split` is desktop Split.
BUCKETS = ("pc", "customize", "worth", "resistor", "split", "case", "view_split", "network")
TAB_VALUES = frozenset(BUCKETS)
ENTRY_KEYS = ("start", "template", "demo", "net", "face", "view", "present")
COUNT_NAMES = ("tab", "case", "preset", "dropdown", "worth", "view", "unit", "copy_link", "optimize")
PRESET_SOURCES = frozenset({"quick", "template", "preset", "url", "demo"})
WORTH_ACTIONS = frozenset({"apply", "test", "row", "undo"})
VIEWS = frozenset({"front", "side", "rear"})
BANNED_KEYS = frozenset({"__proto__", "constructor", "prototype"})
TOKEN = re.compile(r"^[A-Za-z0-9_|][A-Za-z0-9 _.,:+|-]{0,79}$")
ENTRY_VALUE = re.compile(r"^[A-Za-z0-9-]{1,64}$")
LANG = re.compile(r"^[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})?$")
SID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$", re.I)
COUNTRY = re.compile(r"^[A-Z]{2}$")
COUNTRY_HEADERS = ("cf-ipcountry", "x-country-code", "cloudfront-viewer-country", "x-vercel-ip-country")
SKIP_COUNTRY = frozenset({"XX", "T1"})
MAX_BODY_EVENTS = 40
MAX_LOG_BYTES = 2_000_000
MAX_BUCKET_KEYS = 40
MAX_DWELL_MS = 30 * 60 * 1000

_LOCK = threading.Lock()


def log_path() -> Path:
    override = os.environ.get("GPUSIM_USAGE_LOG")
    if override:
        return Path(override)
    return Path.cwd() / "usage" / "events.jsonl"


def country_from_headers(headers) -> str | None:
    """Two-letter country only when the host already set one. Never from the client body."""
    for name in COUNTRY_HEADERS:
        raw = headers.get(name) if headers is not None else None
        if not raw:
            continue
        code = str(raw).strip().upper()
        if COUNTRY.fullmatch(code) and code not in SKIP_COUNTRY:
            return code
    return None


def _token(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    text = " ".join(value.split())
    if not text or text in BANNED_KEYS or not TOKEN.fullmatch(text):
        return None
    return text


def _referrer(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        return ""
    try:
        url = urlsplit(value.strip())
    except ValueError:
        return ""
    if url.scheme not in {"http", "https"} or not url.hostname or url.username or url.password:
        return ""
    host = url.hostname
    if url.port:
        return f"{url.scheme}://{host}:{url.port}"
    return f"{url.scheme}://{host}"


def _int(value: object, lo: int, hi: int) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    if value < lo or value > hi:
        return None
    return value


def sanitize_event(raw: object, *, trust_country: bool = False) -> dict | None:
    """Return a storable event, or None. Drops emails, query strings, hashes, and unknown fields."""
    if not isinstance(raw, dict):
        return None
    name = raw.get("name")
    sid = raw.get("sid")
    if not isinstance(name, str) or not isinstance(sid, str) or not SID.fullmatch(sid):
        return None
    props_in = raw.get("props") or {}
    if not isinstance(props_in, dict):
        return None
    props: dict = {}
    if name == "page_view":
        props["referrer"] = _referrer(props_in.get("referrer"))
        vw = _int(props_in.get("vw"), 0, 10000)
        vh = _int(props_in.get("vh"), 0, 10000)
        if vw is None or vh is None:
            return None
        props["vw"] = vw
        props["vh"] = vh
        lang = props_in.get("lang")
        if isinstance(lang, str) and LANG.fullmatch(lang):
            props["lang"] = lang
        device = props_in.get("device")
        if device in {"phone", "desktop"}:
            props["device"] = device
        for key in ENTRY_KEYS:
            value = props_in.get(key)
            if isinstance(value, str) and ENTRY_VALUE.fullmatch(value):
                props[key] = value
        if trust_country:
            code = props_in.get("country")
            if isinstance(code, str) and COUNTRY.fullmatch(code) and code not in SKIP_COUNTRY:
                props["country"] = code
    elif name == "dwell":
        ms = _int(props_in.get("ms"), 1, MAX_DWELL_MS)
        if ms is None:
            return None
        props["ms"] = ms
        for key in BUCKETS:
            part = _int(props_in.get(key), 0, MAX_DWELL_MS)
            if part:
                props[key] = part
    elif name == "tab":
        tab = _token(props_in.get("tab"))
        if tab not in TAB_VALUES:
            return None
        props["tab"] = tab
    elif name == "case":
        case = _token(props_in.get("case"))
        if not case:
            return None
        props["case"] = case
    elif name == "preset":
        preset = _token(props_in.get("id"))
        if not preset:
            return None
        props["id"] = preset
        source = props_in.get("source")
        props["source"] = source if source in PRESET_SOURCES else "preset"
    elif name == "dropdown":
        control = _token(props_in.get("control"))
        value = _token(props_in.get("value"))
        if not control or not value:
            return None
        props["control"] = control
        props["value"] = value
    elif name == "worth":
        row = _token(props_in.get("id"))
        action = props_in.get("action")
        if not row or action not in WORTH_ACTIONS:
            return None
        props["id"] = row
        props["action"] = action
    elif name == "view":
        view = props_in.get("view")
        if view not in VIEWS:
            return None
        props["view"] = view
    elif name == "unit":
        unit = props_in.get("unit")
        if unit not in {"F", "C"}:
            return None
        props["unit"] = unit
    elif name == "copy_link":
        props = {}
    elif name == "optimize":
        case = _token(props_in.get("case"))
        cards = _int(props_in.get("cards"), 0, 16)
        if not case or cards is None:
            return None
        props["case"] = case
        props["cards"] = cards
    else:
        return None
    return {"sid": sid.lower(), "name": name, "props": props}


def _bump(bucket: dict, key: str, limit: int = MAX_BUCKET_KEYS) -> None:
    if not key or key in BANNED_KEYS:
        return
    if key in bucket:
        bucket[key] = int(bucket[key]) + 1
    elif len(bucket) < limit:
        bucket[key] = 1


def empty_summary() -> dict:
    return {
        "source": "server",
        "page_views": 0,
        "sessions": 0,
        "dwell_ms": 0,
        "dwell_tabs_ms": {key: 0 for key in BUCKETS},
        "counts": {name: 0 for name in COUNT_NAMES},
        "tabs": {},
        "cases": {},
        "presets": {},
        "dropdowns": {},
        "worth": {},
        "views": {},
        "units": {},
        "referrers": {},
        "devices": {},
        "languages": {},
        "viewports": {},
        "countries": {},
        "entry": {},
    }


def aggregate(events: list[dict]) -> dict:
    summary = empty_summary()
    sids: set[str] = set()
    for event in events:
        sid = event.get("sid")
        if isinstance(sid, str):
            sids.add(sid)
        name = event.get("name")
        props = event.get("props") or {}
        if not isinstance(props, dict):
            continue
        if name == "page_view":
            summary["page_views"] += 1
            _bump(summary["referrers"], props.get("referrer") or "(direct)")
            if props.get("device") in {"phone", "desktop"}:
                _bump(summary["devices"], props["device"])
            if isinstance(props.get("lang"), str):
                _bump(summary["languages"], props["lang"])
            if isinstance(props.get("vw"), int) and isinstance(props.get("vh"), int):
                _bump(summary["viewports"], f"{props['vw']}x{props['vh']}")
            if isinstance(props.get("country"), str):
                _bump(summary["countries"], props["country"])
            for key in ENTRY_KEYS:
                if isinstance(props.get(key), str):
                    summary["entry"].setdefault(key, {})
                    _bump(summary["entry"][key], props[key])
        elif name == "dwell":
            summary["dwell_ms"] += int(props.get("ms") or 0)
            for key in BUCKETS:
                summary["dwell_tabs_ms"][key] += int(props.get(key) or 0)
        elif name in summary["counts"]:
            summary["counts"][name] += 1
            if name == "tab" and isinstance(props.get("tab"), str):
                _bump(summary["tabs"], props["tab"])
            elif name == "case" and isinstance(props.get("case"), str):
                _bump(summary["cases"], props["case"])
            elif name == "preset" and isinstance(props.get("id"), str):
                _bump(summary["presets"], props["id"])
            elif name == "dropdown":
                control = props.get("control")
                value = props.get("value")
                if isinstance(control, str) and isinstance(value, str) and control not in BANNED_KEYS:
                    summary["dropdowns"].setdefault(control, {})
                    _bump(summary["dropdowns"][control], value)
            elif name == "worth" and isinstance(props.get("id"), str):
                _bump(summary["worth"], props["id"])
            elif name == "view" and isinstance(props.get("view"), str):
                _bump(summary["views"], props["view"])
            elif name == "unit" and isinstance(props.get("unit"), str):
                _bump(summary["units"], props["unit"])
    summary["sessions"] = len(sids)
    summary["log"] = _display_path(log_path())
    return summary


def _display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return str(resolved)


def read_events(path: Path | None = None) -> list[dict]:
    path = path or log_path()
    if not path.is_file():
        return []
    events = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError:
            continue
        event = sanitize_event(raw, trust_country=True)
        if event is not None:
            events.append(event)
    return events


def record_events(raw_events: object, country: str | None = None, path: Path | None = None) -> int:
    if not isinstance(raw_events, list):
        return 0
    path = path or log_path()
    now = datetime.now(timezone.utc).isoformat()
    cleaned = []
    for raw in raw_events[:MAX_BODY_EVENTS]:
        event = sanitize_event(raw)
        if event is None:
            continue
        if country and event["name"] == "page_view":
            event["props"]["country"] = country
        event["t"] = now
        cleaned.append(event)
    if not cleaned:
        return 0
    _append(path, cleaned)
    return len(cleaned)


def _append(path: Path, events: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    blob = "".join(json.dumps(event, ensure_ascii=False) + "\n" for event in events)
    with _LOCK:
        if path.exists() and path.stat().st_size > MAX_LOG_BYTES:
            kept = path.read_text(encoding="utf-8").splitlines()[-3000:]
            path.write_text("\n".join(kept) + ("\n" if kept else ""), encoding="utf-8")
        with path.open("a", encoding="utf-8") as handle:
            handle.write(blob)


def summary_for(path: Path | None = None) -> dict:
    path = path or log_path()
    summary = aggregate(read_events(path))
    summary["log"] = _display_path(path)
    summary["source"] = "server"
    return summary
