# Rev 4 plan

Source: Stefano's rev 4 brief (16 items). This maps each item to files and
changes, in the order they are implemented. Calibration rule is unchanged:
only global or per-card-type parameters, never a per-cell offset. Rev 3
reference values (open air 82.81, anchor A 86.52, anchor B unthrottled
100.7 / 108.9 / 108.7 / 87.1, aggressive open air 73.44, best Meshify cell
84.3, aggressive on best cell 75.5) are re-reported as deltas at the end.

## Block 1 — physics and data model

| Item | Change | Files |
|---|---|---|
| 12 Plume ingestion | New cooler type `flow_through` (axial fans, intake on the fan face, exhaust up through the backplate side plus a smaller bracket share). Flow net: `cex-<gpu> → gpu` up-exit branch sized by the gap above, plus the bracket branch. Thermal net: a plume-ingestion overlay reroutes `m_ing = min(φ(g)·ṁ_in,fan(upper), ṁ_up(lower))` from the lower card's exhaust node straight into the upper card's inlet node, and removes the same mass from the zone streams, so every node still balances. `φ(g) = φ_max·exp(−g/L_plume)`, global knobs, Monte Carlo varied. Reported as a virtual `plume-ingest` branch. Tests: upper hotter than lower when stacked; upper−lower shrinks as the gap grows; mass per node and energy balance hold. | `models.py`, `layout.py`, `network.py`, `thermal.py`, `calib.py`, `solve.py`, `tests/test_plume.py` |
| 10 CPU air / water | `BuildCfg.cpu {power_w, cooling: air|water, cooler_fan, cooler_fan_count, cooler_duty, heatsink_k}`. Water: heat rides the radiator branch (as rev 3). Air: new node `cpu`, branch `case → cpu` (cooler fan + tower fin-stack loss, heat tagged), `cpu → case` spill, and the rear mount pulls from `cpu`. Rev 3 `radiator.cpu_power_w` migrates on load. Water with no radiator is a loud error. | `models.py`, `network.py`, `thermal.py`, presets |
| 13 Obstruction / cables | Kept as inputs; redefined as documented k multipliers on internal branches (GPU zone → case spill, CPU cooler exit). low 1.0 / medium 2.5 / high 6.0; clean 1.0 / cluttered 2.0. Anchors use low/clean, so they do not move. | `calib.py`, `network.py`, docs |
| 9 Seal levels reversed | 1 = fully open (100 %), 2 = open grille / missing covers (70 %), 3 = typical mesh + filter (45 %), 4 = restricted, seams and small gaps (8 %), 5 = sealed (0 %, no branch, R = ∞). Default side seal 5 (solid glass / metal). Factorial `leaky` = front 3, top 3, bottom 4, side 5, seams 4, rear_slots 3; `sealed` = 4 / 4 / 5 / 5 / 5 / 5. Every build, scenario, test and doc migrated. | `calib.py`, `factors.py`, `network.py`, all `presets/builds`, tests, docs |
| 11 GPU picker + curves | New cards: RTX PRO 6000 Blackwell Workstation Edition (600 W, dual-slot flow-through), RTX 5090 Founders Edition (575 W, dual-slot flow-through), RTX 3090 Founders Edition (350 W, 3-slot, hybrid flow-through with a bracket share). Specs cited; per-card-type blocks in `calib.py` tuned only to a single-card open-air review temperature. Fan curves are `stock` (per card) and `custom_accelerated` (global: 0 % at 25 °C → 100 % at 70 °C, linear). `maxq_aggressive` is accepted as an alias of `custom_accelerated`. Blower RPM floor removed so 0 % really is off. | `presets/cards/*`, `calib.py`, `physics.py`, `solve.py`, `models.py` |

## Block 2 — API (item 14)

- `POST /api/v1/simulate` — one full spec → per-card temps, flows, case pressure, thermal breakdown, network.
- `POST /api/v1/rank` — a base spec plus named variants (JSON merge patches) → ranked table.
- `POST /api/v1/sweep` — a base spec plus factors (named macros `spacing`, `pressure`, `shroud`, `leakage`, `fan_curve`, `cpu_cooling`, or any dotted path) → factorial, ranked. Capped at 256 cells.
- `GET /api/v1/presets`, `GET /api/v1/schema`. Inline `extra_fans` and `extra_cards` (a card inherits calibration from `calibration_from`).
- FastAPI `/docs`; exported `docs/openapi.json` and `docs/simspec.schema.json` (`gpusim schema` regenerates them). Examples: `examples/api/*.json`, `examples/api_client.py`. README section with curl and Python.
- Files: `gpusim/api.py` (pure functions), `gpusim/ui/app.py` (routes), `gpusim/cli.py`, `tests/test_api.py`.

## Block 3 — UI (items 1–8)

| Item | Change |
|---|---|
| 1 Fans on faces | Fans are flat discs lying in the plane of their panel, drawn from a 3/4 camera so they read as ovals on the front, top, rear, bottom or glass side. Camera presets: 3/4 front, side, 3/4 rear. |
| 2 GPUs to the rear | Cards sit with the bracket at the rear wall, PCB edge off the motherboard tray, spanning their real length forward. |
| 3 PSU | PSU box bottom-rear under the shroud (or open), with fan side shown. |
| 4 Radiator | Radiator slab against its panel; its fans sit directly on its inner face (push) as ovals. Front, top, bottom allowed. |
| 5 9000D | Stock front array as researched and cited; front face mounts laid out as a non-overlapping grid; a face inset auto-scales so every fan is visible. Identical fans on one face collapse to one label ("Front fans ×8: all …"). |
| 6 Network view | Toggle: split or fullscreen SVG. Layer 1 airflow (pressure = voltage, flow = current) with labelled seal, fan, filter, inter-card slot, fin-channel, bracket, plume branches and ∞ for sealed walls. Layer 2 thermal: per card, inlet mixing (zone, plume ingestion, backplate capture) → R_conv = 1/(ε ṁ c_p) → heatsink → R_tim → die, with the numbers. |
| 7 Tooltips | One tooltip layer; every input and every legend item has a `data-tip` with its assumption. |
| 8 Left bar | Front / Top / Rear / Bottom / Side / Internals / GPUs. One panel open at a time, no long scrolling. |

Files: `gpusim/ui/static/index.html`, `app.js` (split into `scene.js`, `network.js`, `tips.js`), `style.css`.

## Block 4 — presets and docs (15, 16)

- Start screen: Quick start (Meshify, 9000D Airflow), Start from template (9000D Airflow, Meshify 2 XL, generic ATX / mATX / E-ATX, Enthoo Elite Server), Build from scratch. Mike Bradley mock via `?demo=mike-bradley`, labelled everywhere.
- Airflow-first: water-cooled CPU kept, no AIO-for-GPU paths.
- SPEC.md → revision 4. README (API, new cards, seal table, plume), DEMO.md, HYPOTHESIS.md, docs/CALIBRATION.md (deltas vs rev 3).
- Final: pytest, `gpusim sweep --build meshify2xl-stefano --mc 200`, headless Chrome 1920×1080 screenshot on a private port, push, summary.
