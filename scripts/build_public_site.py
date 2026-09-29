#!/usr/bin/env python3
"""Write site/ for gpuism.com.

The directory is a static host: the UI, plus the Python package the page runs
in Pyodide. It is not served by `gpusim ui`.
"""

from __future__ import annotations

import json
import shutil
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
    print(f"wrote {SITE} ({len(files)} source files, bundle {bundle.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
