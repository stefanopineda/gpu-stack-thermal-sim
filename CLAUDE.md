# gpu-stack-thermal-sim

Compact airflow + thermal network for air-cooled multi-GPU workstations. Not CFD.
GPU water blocks are out of scope (a water-cooled CPU is supported). Units are Celsius. Default ambient 25 °C.

## What matters

- `SPEC.md` is **revision 4.1** (§16 = rev 4.1 review changes, §16.2 = assumption audit: slot covers don't block the inter-card gap, they close the rear openings; PSU fan up is a real exhaust branch; rear-slot re-ingestion only below room pressure) (Stefano's 16-item rev 4 brief; plan in `docs/REV4_PLAN.md`, item map in SPEC §15). Implement that, don't renegotiate it.
- Default build id: `meshify2xl-stefano` (Meshify 2 XL, 3×140 Noctua redux-1700 front intake + one top intake at the front + one bottom intake at the front (confirmed by Stefano), 1× rear exhaust, Arctic 360 top exhaust slid to the rear (`radiator.offset: rear`), CPU water 150 W, shroud fans drawn side by side, 4× RTX PRO 6000 Blackwell Max-Q, slots 1/4/7 + vertical v2, shroud on with 2× NF-A14 iPPC-3000, leaky, stock GPU curve).
- The factorial **stock** cell is stacked, shroud off, standard, leaky. It is reported as its own row even though it matches one cell.
- **Seal levels are reversed in rev 4: 1 = fully open (100 %) … 5 = sealed (0 %, no branch, R = ∞)**; 2 = 70 %, 3 = 45 %, 4 = 5 %. Default side = 5. Leaky = front 3, top 3, bottom 4, side 5, seams 4, rear_slots 3. Sealed = 4/4/5/5/5/5.
- Fan curves: `stock` (per card YAML) and `custom_accelerated` (global in `calib.GLOBAL_FAN_CURVES`: 0 % @ 25 °C → 100 % @ 70 °C). `maxq_aggressive` is an alias. No blower RPM floor.
- Cards: Max-Q blower (primary, anchors), `custom-blower-300w` template, and flow-through `rtx-pro-6000-blackwell-workstation`, `rtx-5090-fe`, `rtx-3090-fe` (cited; per-type blocks in `calib.CARD` set only to one open-air review temperature, never used to move the Max-Q anchors).
- **Plume ingestion** (item 12): flow-through exhaust goes `cex → case` via an `upexit-*` branch; the card above draws a share of that jet **derived from the solved flows** (jet speed, zone crossflow, entrainment α = 0.08; SPEC §16.1 — no fixed φ(g) any more), rerouted in `thermal.plume_transfers` / `_streams` with a displaced-zone-air stream so nodes still balance. Don't route up-exit into the GPU zone (it recirculates ~1 kW onto itself).
- CPU: `BuildCfg.cpu {power_w, cooling: air|water, cooler_fan…}`. Air adds `cpu-cooler`/`cpu-exit` branches and the rear mount pulls from `cpu`. Water with no radiator raises. Rev 3 builds migrate from `radiator.cpu_power_w`.
- Obstruction / cables are k multipliers on internal branches (1 / 2.5 / 6; 1 / 2; cables ×1.35 on card inlets).
- Anchors (rev 4): open air 82.81; A 86.58; B unthrottled 100.8 / 109.0 / 108.8 / 87.2 (middle hottest, throttle at 90); Custom Accelerated open air 73.44. Flow-through open air: 5090 FE 75.9, PRO 6000 WS 76.4, 3090 FE 68.0. Deltas vs rev 3 are in `docs/CALIBRATION.md`.
- Ranking (sweep, CLI, API): non-throttling configs first by hottest die, then throttling configs by **unthrottled** hottest (`sweep.rank_key`).
- The blower fan face points **down**. Gaps come from the slot map for every card. No lowest-card bypass branch.
- Tuned knobs are global / per card type in `gpusim/calib.py`. Never per sweep cell. Presets are YAML; every number needs a source or `approximate` plus an assumption (`gpusim/cite.py`).
- `gpusim sweep` writes `results/<build>/hypothesis_auto.md`. The root `HYPOTHESIS.md` is curated; do not point the sweep at it.
- Corsair 9000D ships with **no fans** (Corsair spec page); the template fills the 8×120 front (4 high × 2 wide) with AF120 RGB ELITE.
- `mike-bradley-dengen-x-station` is now Mike Bradley's real published build, named **"Dengen X Station"** (Stefano's spelling, 2026-09-29; the Grok lookup of his post on 2026-09-28 read "Degen X Station"), used with his permission per Stefano. Layout confirmed by Stefano from his photos: 8×120 front intake, 4×120 top exhaust in a 2×2 square pushed to the rear (9000D top pattern `8x120`, 2 wide × 4 deep; the front four top mounts are cover plates), 2×120 rear exhaust stacked above the cards beside the CPU cooler (9000D rear pattern `2x120`), no side fans, no shroud, no radiator, CPU tower blowing up with its top fan only (`cpu.cooler_fans: top`, `cooler_airflow: up`). It is **anchor C** (`bounds.anchor_c_checks`): top 78.1 / 69.4 °C vs his 79 / 69 at 80 / 100 % fans. `/?demo=mike-bradley`.
- Touching flow-through cards are coupled by a series duct `stack-*` (`stack_cd = 0.25`, `stack_length_mm = 8`) — without it they run away. Those two were fit so the top card matches his published ~79 °C at ~80% fans and ~69 °C at 100%. The middle-card temperatures are the duct's interpolation, not measurements he published. Faces can have fan patterns (`MountLayout.pattern`, `BuildCfg.patterns`).
- X is not reachable with WebFetch (402/451). Use Grok Build headless: `~/.grok/bin/grok -p "…"` (read-only prompt) for X lookups.
- His public 4× build (looked up 2026-09-28) is **not** that mock. It is four RTX PRO 6000 Blackwell **Workstation** flow-through cards, close-packed, 275 W cap, unified GPU fans, Corsair 9000D with Noctua 120s and an air-cooled Threadripper PRO 7965WX, PSU a SilverStone HELA 2500Rz (1650 W on 120 V). He published only the ends of the stack: at ~80% fans, bottom 49 °C and top 79 °C; at 100% fans, bottom 49 °C and top 69 °C. A same-day reply said 47 °C / 77 °C. Temps rise bottom to top. Middle-card numbers and the promised thermal study were not posted as of 2026-09-28 00:43 UTC. Do not treat the mock's Max-Q middle-hot result as his measurement. Sources: x.com/MikeBradleyAI/status/2104206814577295513, replies 2104213812274409748 and 2104370605890097235, YouTube `O_Gk9oatDhI` for the earlier 2× spaced burn (~90 °C at 600 W).

## Agent API (item 14)

`gpusim/api.py` (pure functions) + routes in `gpusim/ui/app.py`: `POST /api/v1/simulate` (SimSpec), `/api/v1/rank` (variants: merge patch and/or `set`), `/api/v1/sweep` (factors: macros or dotted paths, ≤ 256 cells), `GET /api/v1/presets|builds/{id}|schema`. CLI twins `gpusim simulate|rank|schema`. `docs/openapi.json` and `docs/simspec.schema.json` are exported by `gpusim schema` and a test compares them to the live app — rerun `uv run gpusim schema` after changing any request model or route.

## UI

Modules in `gpusim/ui/static/`: `app.js` (state, left face bar, panels, readout, inset, demo/compare/optimize), `scene.js` (three.js case, PBR-lit with a vendored `RoomEnvironment.js`), `parts.js` (procedural realistic parts: bladed fans; GPUs modelled on NVIDIA's product photos — Max-Q = glossy black blower, polished hub, champagne ring, full-length gold fin window on the top edge; Workstation 600 W = rounded matte-black double flow-through with the X face, grooved fin zones, gold NVIDIA / RTX PRO 6000 marks, recessed 12V-2x6 on the top edge; text decals are pre-mirrored because the scene root has scale.x = −1; WRX90E board, tower cooler, AIO hoses, PSU, perforated steel, glass; colour only as cues — a lit ring per fan, blue intake / red exhaust / amber internal, and a die-temperature light bar per GPU; unused side mounts are not drawn), `network.js` (SVG airflow + thermal layers), `tips.js` (all tooltip text). three.js r160 ES module vendored (no CDN). Static served `no-cache`. If `/api/build/<id>` 404s (a `gpusim ui` process older than the page), `loadBuild` shows a restart banner instead of drawing nothing. `window.gpusim` is a scripting handle for headless checks. URL params: `?start=meshify|9000`, `?template=<id>`, `?demo=mike-bradley|stefano`, `?net=split|full`, `?face=…`, `?view=…`, `?present=1`.

Headless screenshot check: Chrome `--screenshot` hangs on the render loop; drive it over CDP with a separate `--user-data-dir` (e.g. `uv run --no-project --with websocket-client python cdp_shot.py URL out.png`). Never touch the review server on 127.0.0.1:8000; test on 8010.

## Commands

```bash
uv venv && uv pip install -e ".[dev]"
uv run pytest -q
uv run gpusim sweep --build meshify2xl-stefano --mc 200
uv run gpusim ui
uv run gpusim schema
```

Latest sweep (rev 4.1, confirmed layout, mc 200, seed 12345): best cells gap1 / standard / shroud on, sealed 83.9 / leaky 84.0 °C (a tie, MC 76–98). Stock unthrottled hottest 108.2 °C (100.2, 108.2, 86.6, 86.0), throttled ~89.5 °C (MC 94–126). Anchor A 86.25, B 99.9/108.0/107.9/86.3. Optimizer: gap + vertical, shroud on, sealed, Custom Accelerated, 75.3 °C. `pressure=standard` keeps the build's own fan directions. Bounds check overall PASS.

## Worth it? (2026-09-29)

`gpusim/worth.py` (+ `POST /api/worth`, `gpusim worth`, UI panel): single changes to the current build ranked by the drop in the hottest unthrottled die, paired-MC band, effort tag, "inside the noise" = band crosses zero or gain < 3 °C (SPEC §16.3). On `meshify2xl-stefano` the shroud is worth 2.2 °C (84.0 with, 86.2 without; band 1.4–2.5), inside the noise; this is the prediction for Stefano's launch-stream shroud test (DEMO.md top section). The build rides in the URL fragment (`#b=` + deflate-raw base64url); Copy link shares it.

## Public site (gpuism.com)

The public app is https://github.com/stefanopineda/gpuism (GitHub Pages, legacy branch build from `main`). **Deploys are automatic:** `.github/workflows/ci.yml` runs pytest on every push; on `main` it then runs `scripts/build_public_site.py` and pushes `site/` to `stefanopineda/gpuism` with the deploy key in the `GPUISM_DEPLOY_KEY` secret (write deploy key on the gpuism repo). Do not hand-edit the gpuism repo. The build stamps every relative JS import and the bundle with `?v=<sha>-<hash>` (Pages caches 10 min) and writes presets and saved builds to `static/api/*.json` so the page draws before Pyodide loads. `uv run python scripts/build_public_site.py` writes gitignored `site/`: the UI plus a Pyodide bundle of the solver (`gpusim/browser_api.py`, `static/browser-engine.js`). Visitors run the model in the browser; the page does not upload a build. Local `gpusim ui` is still the Python server and its `index.html` does not load the browser engine.

Namecheap stays on BasicDNS (`dns1`/`dns2.registrar-servers.com`). Apex A/AAAA are the four GitHub Pages addresses. `www` is a CNAME to `stefanopineda.github.io`. Email forwarding (the SPF TXT and the eforward MX records) was left in place. The cert was re-requested on 2026-09-29 (custom domain removed and re-added); approved the same day (expires 2026-12-28, GitHub renews it) and "Enforce HTTPS" is on.

Phone layout is the same `index.html` / `style.css` / `app.js`, at max-width 800px. Tabs are PC, Customize, Resistor, and Split. GPU temperatures stay on screen under the header. Desktop keeps the view switch, Case/Split/Network, Optimize, °F, Compare, Demo, and Present.
