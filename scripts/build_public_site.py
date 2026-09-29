#!/usr/bin/env python3
"""Write site/ for gpuism.com.

The directory is a static host: the UI, plus the Python package the page runs
in Pyodide. It is not served by `gpusim ui`.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
PKG = ROOT / "gpusim"
PRESETS = ROOT / "presets"

# These import matplotlib, pandas, typer, or FastAPI. The browser path does not load them.
SKIP_PY = {
    "gpusim/cli.py",
    "gpusim/sweep.py",
    "gpusim/plots.py",
    "gpusim/schematic.py",
    "gpusim/calibrate.py",
    "gpusim/ui/app.py",
}


def main() -> None:
    if SITE.exists():
        shutil.rmtree(SITE)
    shutil.copytree(PKG / "ui" / "static", SITE / "static")
    index = (PKG / "ui" / "static" / "index.html").read_text()
    index = index.replace(
        "<title>gpusim — air-cooled multi-GPU</title>",
        "<title>gpuism — air-cooled multi-GPU</title>",
    )
    index = index.replace(">GPUSIM</button>", ">gpuism</button>")
    index = index.replace('href="/static/style.css"', 'href="static/style.css"')
    index = index.replace(
        "Agents: <a href=\"/docs\">/docs</a>.",
        "This page runs the model in your browser.",
    )
    index = index.replace(
        '<script type="module" src="/static/app.js"></script>',
        '<script type="module" src="static/browser-engine.js"></script>\n  <script type="module" src="static/app.js"></script>',
    )
    (SITE / "index.html").write_text(index)
    files: dict[str, str] = {}
    for path in PKG.rglob("*.py"):
        rel = path.relative_to(ROOT).as_posix()
        if rel in SKIP_PY or "/__pycache__/" in f"/{rel}":
            continue
        files[rel] = path.read_text()
    for path in PRESETS.rglob("*.yaml"):
        files[path.relative_to(ROOT).as_posix()] = path.read_text()
    bundle = SITE / "py-bundle.json"
    bundle.write_text(json.dumps({"files": files}, ensure_ascii=False))
    (SITE / "CNAME").write_text("gpuism.com\n")
    (SITE / ".nojekyll").write_text("")
    (SITE / "README.md").write_text(
        "Built site for https://gpuism.com\n\n"
        "The thermal model runs in the visitor's browser. "
        "Regenerate this directory with `uv run python scripts/build_public_site.py` "
        "from the gpu-stack-thermal-sim repo.\n"
    )
    _static_api()
    stamp = _stamp(bundle)
    _version_assets(stamp)
    print(f"wrote {SITE} ({len(files)} source files, bundle {bundle.stat().st_size} bytes, assets ?v={stamp})")


def _static_api() -> None:
    """Presets and saved builds as plain JSON, so the start screen and the 3D
    case appear before the in-browser Python has finished loading."""
    import sys

    sys.path.insert(0, str(ROOT))
    from gpusim.browser_api import build_payload, presets_payload

    api = SITE / "static" / "api"
    (api / "build").mkdir(parents=True, exist_ok=True)
    presets = presets_payload()
    (api / "presets.json").write_text(json.dumps(presets, ensure_ascii=False))
    for build in presets["builds"]:
        (api / "build" / f"{build['id']}.json").write_text(json.dumps(build_payload(build["id"]), ensure_ascii=False))


def _stamp(bundle: Path) -> str:
    """Commit id when there is one, else a hash of what was built."""
    sha = os.environ.get("GITHUB_SHA", "")
    if not sha:
        try:
            sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
        except (OSError, subprocess.CalledProcessError):
            sha = ""
    sha = sha.strip()[:10]
    digest = hashlib.sha256(bundle.read_bytes())
    for path in sorted((SITE / "static").rglob("*")):
        if path.is_file():
            digest.update(path.read_bytes())
    return f"{sha}-{digest.hexdigest()[:8]}" if sha else digest.hexdigest()[:12]


# Every relative module import gets the same ?v= stamp, so a returning visitor
# never mixes a cached module with a new one (GitHub Pages caches 10 minutes).
# The vendored three.js is stamped too, from every importer alike, so it is
# still one module instance.
_IMPORT = re.compile(r"""((?:from|import)\s*\(?\s*)(["'])(\.{1,2}/[^"'?]+\.js)\2""")


def _version_assets(stamp: str) -> None:
    for path in (SITE / "static").rglob("*.js"):
        text = path.read_text()
        text = _IMPORT.sub(lambda m: f"{m.group(1)}{m.group(2)}{m.group(3)}?v={stamp}{m.group(2)}", text)
        text = text.replace('new URL("./browser-worker.js", import.meta.url)', f'new URL("./browser-worker.js?v={stamp}", import.meta.url)')
        text = text.replace('new URL("../py-bundle.json", self.location.href)', f'new URL("../py-bundle.json?v={stamp}", self.location.href)')
        path.write_text(text)
    index = SITE / "index.html"
    html = index.read_text()
    html = re.sub(r'((?:src|href)="static/[^"?]+\.(?:js|css))"', lambda m: f'{m.group(1)}?v={stamp}"', html)
    index.write_text(html)


if __name__ == "__main__":
    main()
