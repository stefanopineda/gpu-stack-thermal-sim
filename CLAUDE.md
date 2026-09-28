# gpu-stack-thermal-sim

Compact airflow + thermal network for air-cooled multi-GPU workstations. Not CFD.
GPU water blocks are out of scope (a water-cooled CPU is supported). Units are Celsius. Default ambient 25 °C.

## What matters

- `SPEC.md` is **revision 4** (Stefano's 16-item rev 4 brief; plan in `docs/REV4_PLAN.md`, item map in SPEC §15). Implement that, don't renegotiate it.
- Default build id: `meshify2xl-stefano` (Meshify 2 XL, 3×140 Noctua redux-1700 front intake, 1× rear exhaust assumed, Arctic 360 top exhaust, CPU water 150 W, 4× RTX PRO 6000 Blackwell Max-Q, slots 1/4/7 + vertical v2, shroud on with 2× NF-A14 iPPC-3000, leaky, stock GPU curve).
- The factorial **stock** cell is stacked, shroud off, standard, leaky. It is reported as its own row even though it matches one cell.
- **Seal levels are reversed in rev 4: 1 = fully open (100 %) … 5 = sealed (0 %, no branch, R = ∞)**; 2 = 70 %, 3 = 45 %, 4 = 5 %. Default side = 5. Leaky = front 3, top 3, bottom 4, side 5, seams 4, rear_slots 3. Sealed = 4/4/5/5/5/5.
- Fan curves: `stock` (per card YAML) and `custom_accelerated` (global in `calib.GLOBAL_FAN_CURVES`: 0 % @ 25 °C → 100 % @ 70 °C). `maxq_aggressive` is an alias. No blower RPM floor.
- Cards: Max-Q blower (primary, anchors), `custom-blower-300w` template, and flow-through `rtx-pro-6000-blackwell-workstation`, `rtx-5090-fe`, `rtx-3090-fe` (cited; per-type blocks in `calib.CARD` set only to one open-air review temperature, never used to move the Max-Q anchors).
- **Plume ingestion** (item 12): flow-through exhaust goes `cex → case` via an `upexit-*` branch; the card above draws `φ(g) = 0.85·exp(−g/40 mm)` of its fan-side intake from that jet, rerouted in `thermal.plume_transfers` / `_streams` with a displaced-zone-air stream so nodes still balance. Don't route up-exit into the GPU zone (it recirculates ~1 kW onto itself).
- CPU: `BuildCfg.cpu {power_w, cooling: air|water, cooler_fan…}`. Air adds `cpu-cooler`/`cpu-exit` branches and the rear mount pulls from `cpu`. Water with no radiator raises. Rev 3 builds migrate from `radiator.cpu_power_w`.
- Obstruction / cables are k multipliers on internal branches (1 / 2.5 / 6; 1 / 2; cables ×1.35 on card inlets).
- Anchors (rev 4): open air 82.81; A 86.58; B unthrottled 100.8 / 109.0 / 108.8 / 87.2 (middle hottest, throttle at 90); Custom Accelerated open air 73.44. Flow-through open air: 5090 FE 75.9, PRO 6000 WS 76.4, 3090 FE 68.0. Deltas vs rev 3 are in `docs/CALIBRATION.md`.
- Ranking (sweep, CLI, API): non-throttling configs first by hottest die, then throttling configs by **unthrottled** hottest (`sweep.rank_key`).
- The blower fan face points **down**. Gaps come from the slot map for every card. No lowest-card bypass branch.
- Tuned knobs are global / per card type in `gpusim/calib.py`. Never per sweep cell. Presets are YAML; every number needs a source or `approximate` plus an assumption (`gpusim/cite.py`).
- `gpusim sweep` writes `results/<build>/hypothesis_auto.md`. The root `HYPOTHESIS.md` is curated; do not point the sweep at it.
- Corsair 9000D ships with **no fans** (Corsair spec page); the template fills the 8×120 front (4 high × 2 wide) with AF120 RGB ELITE. Mike Bradley mock = `/?demo=mike-bradley`, always labelled "Illustrative mock — not a measurement or claim about anyone's real build."

## Agent API (item 14)

`gpusim/api.py` (pure functions) + routes in `gpusim/ui/app.py`: `POST /api/v1/simulate` (SimSpec), `/api/v1/rank` (variants: merge patch and/or `set`), `/api/v1/sweep` (factors: macros or dotted paths, ≤ 256 cells), `GET /api/v1/presets|builds/{id}|schema`. CLI twins `gpusim simulate|rank|schema`. `docs/openapi.json` and `docs/simspec.schema.json` are exported by `gpusim schema` and a test compares them to the live app — rerun `uv run gpusim schema` after changing any request model or route.

## UI

Modules in `gpusim/ui/static/`: `app.js` (state, left face bar, panels, readout, inset, demo/compare/optimize), `scene.js` (three.js case; fans are discs in their face plane), `network.js` (SVG airflow + thermal layers), `tips.js` (all tooltip text). three.js r160 ES module vendored (no CDN). Static served `no-cache`. `window.gpusim` is a scripting handle for headless checks. URL params: `?start=meshify|9000`, `?template=<id>`, `?demo=mike-bradley|stefano`, `?net=split|full`, `?face=…`, `?view=…`, `?present=1`.

Headless screenshot check: Chrome `--screenshot` hangs on the render loop; drive it over CDP with a separate `--user-data-dir` (e.g. `uv run --no-project --with websocket-client python cdp_shot.py URL out.png`). Never touch the review server on 127.0.0.1:8000; test on 8010.

## Commands

```bash
uv venv && uv pip install -e ".[dev]"
uv run pytest -q
uv run gpusim sweep --build meshify2xl-stefano --mc 200
uv run gpusim ui
uv run gpusim schema
```

Latest sweep (rev 4, mc 200, seed 12345): best cell gap1 / standard / shroud on / leaky, 84.2 °C all four cards (MC 76–98). Stock unthrottled hottest 108.8 °C (100.8, 108.8, 87.2, 86.5), throttled ~89.5 °C (MC 96–127). Optimizer: gap + vertical, shroud on, Custom Accelerated, 75.4 °C. Bounds check overall PASS. Spacing is still the large effect; a 2 °C shroud delta is inside the noise.
