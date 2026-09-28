# gpusim

A compact airflow and temperature model for air-cooled multi-GPU workstations.
It is a coupled flow-resistance network and a thermal-resistance network. It is
not CFD. It has two jobs: rank case configurations before you spend a weekend
moving fans, and show that ranking live, including on an OBS browser source.

GPU water blocks are out of scope. The audience is people who will keep the
stock blower on the card. Large towers are the point; ITX and SFF only get a
generic case and the same solver. Temperatures are Celsius everywhere. Fahrenheit
is a display toggle in the UI. Default ambient is 25 °C.

Typical accuracy is about **±5–10 °C absolute**. Trust the ranking more than
the number. A Monte Carlo band that overlaps a neighbour means the model cannot
tell those two cells apart.

## Build assumptions

Resolved with Stefano (SPEC rev 3):

- Case fans are Noctua **140 mm redux at 1700 RPM**. The library entry scales the published NF-P14s redux-1500 PWM curve by the fan laws and is marked approximate. There is no 170 mm Noctua in this build; a generic 170 mm fan stays in the library.
- CPU cooler is an Arctic 360 mm radiator with its three Arctic P12-class fans, **top exhaust, push**. That direction is the default and can be flipped.
- The Phanteks multi-GPU preset is the **Enthoo Elite Server, 12 slots**. Phanteks lists the dimensions as `582 × 261 × 721 mm` without axis labels; this model reads them as height × width × depth, because 261 mm cannot be the height of a 12-slot chassis.
- Meshify 2 XL has 9 horizontal slots and 3 vertical slots off to the side. Stefano runs with **all slot brackets removed**.
- The rear exhaust shroud covers the bracket plane and is pulled by **two NF-A14 industrialPPC-3000 PWM** fans. A passive duct (same shroud, fans off) is still runnable. It is not a sweep factor.
- GPUs are 4× RTX PRO 6000 Blackwell Max-Q, 300 W, dual-slot blowers. The saved build places three horizontal cards in slots 1, 4 and 7 (one empty slot between them) and the fourth in vertical slot `v2`. That placement is an assumption; anchor A is this layout with the shroud off.
- A rear 140 mm redux exhaust is installed. The case has the mount; only the front trio was stated explicitly.
- Anchor A (gaps, no shroud, stock curve) is the bench point at 86.5 °C. Anchor B (four horizontal cards, no gaps, stock curve) throttles at a 90 °C cutoff, with the middle cards hottest (unthrottled peak 108.9 °C).
- Radiator thickness is the published 38 mm. FPI is not published; 18 FPI is assumed. Blower P–Q, fin geometry and TIM are not published; they are the global fit in `gpusim/calib.py`. The NF-A14 iPPC datasheet says 10.52 mmH₂O and the current web page says 6.58; the curve used is the datasheet, and Monte Carlo spans both.

`stock` in the sweep table is the factorial baseline (stacked, standard pressure, shroud off, leaky). It is the same configuration as one of the 16 cells and is repeated as its own row.

## Method

Nodes are ambient, the case volume, the GPU zone, each blower inlet and outlet,
and (when fitted) a rear plume or a shroud plenum. Branches are quadratic
orifices, `ΔP = k Q|Q|`, plus fans whose pressure-flow curve scales by the
affinity laws `Q ∝ N`, `P ∝ N²`. Mass is conserved. The nonlinear system is a
damped Newton solve with an analytic Jacobian; it raises if it does not converge.

Each card then has a die, a memory node, a heatsink and an airstream.
Heatsink-to-air uses `Nu = C Re^m Pr^(1/3)` and an ε-NTU effectiveness. The
blower duty is a function of die temperature (stock caps near 70%; aggressive
hits 100% at 70 °C) and is iterated with the flow. At or above the throttle
threshold (default 88 °C) the card is flagged; above the 90 °C cutoff, power is
reduced to the throttled equilibrium. Both temperatures are reported.

The blower fan face points down, toward the floor. A card preset sets
`inlet_faces` (`floor`, `cpu`, or `both`) and `inlet_split` (fraction of the
eye on the fan face). The Max-Q uses `both` and 0.75, an assumption: the rest
is a smaller backplate-side / end opening. Each face takes its gap from the
slot map (card below, PSU-shroud clearance, CPU-area clearance, or card above).

Clock offsets, undervolt and memory offset change the heat load with a rough
split (dynamic power ∝ f·V², a static share, a memory share). They clamp to the
power limit. The UI labels them as approximations.

The method is the standard compact / thermal-electrical analogy and flow-network
approach for electronics cooling:

- G. N. Ellison, *Thermal Computations for Electronics* (CRC Press).
- I. E. Idelchik, *Handbook of Hydraulic Resistance*.
- Flow network modelling articles in *Electronics Cooling* magazine.

No page numbers are cited, because none were looked up for a quotation.

## Hardware sources

| Part | What was used | Source |
|---|---|---|
| RTX PRO 6000 Blackwell Max-Q | 300 W, dual slot, 4.4 in × 10.5 in, active cooler | [NVIDIA datasheet](https://www.nvidia.com/content/dam/en-zz/Solutions/products/workstations/professional-desktop-gpus/rtx-pro-6000-max-q/workstation-datasheet-blackwell-rtx-pro-6000-max-q-nvidia-us-5349650-web.pdf), [product page](https://www.nvidia.com/en-us/products/workstations/professional-desktop-gpus/rtx-pro-6000-max-q/) |
| Board size 266.7 × 111.15 × 37 mm | ELSA drawing, bracket excluded | [ELSA datasheet](https://www.elsa-jp.co.jp/wp-content/uploads/2025/03/Datasheet_NVIDIA_RTX_PRO_6000_Blackwell_Max-Q_Workstation_Edition.pdf) |
| Blower, rear exhaust | Retailer description. NVIDIA only says "Active". P–Q is approximate | [Central Computer](https://www.centralcomputer.com/blog/post/understanding-the-nvidia-rtx-6000-pro-blackwell-lineup-workstation-max-q-and-server-editions) |
| Meshify 2 XL | 600 × 240 × 566 mm (L×W×H), 9+3 slots, fan and radiator mounts | [Fractal](https://www.fractal-design.com/products/cases/meshify-series/meshify-2-xl/meshify-2-xl-black-light-tg/), [product sheet](https://www.fractal-design.com/app/uploads/2020/10/Meshify-2-XL-_Product-Sheet_EN.pdf) |
| 9000D RGB AIRFLOW | 307 × 698 × 698 mm, 8 horizontal + 2 vertical | [Corsair](https://www.corsair.com/us/en/p/pc-cases/cc-9011273-ww/icue-link-9000d-rgb-airflow-pc-case-black%2520CC-9011273-WW) |
| Enthoo Elite Server | 12 slots, PH-ES916E_BK02 | [Phanteks](https://phanteks.com/product/enthoo-elite-server-black/) |
| NF-P14s redux-1500 / NF-P12 redux-1700 | Published P–Q points | [P14s](https://www.noctua.at/en/products/nf-p14s-redux-1500-pwm/specifications), [P12](https://www.noctua.at/en/products/nf-p12-redux-1700-pwm/specifications) |
| NF-A14 iPPC-3000 | 269.3 m³/h, datasheet 10.52 mmH₂O vs web 6.58 | [Datasheet PDF](https://www.mikrocontroller.net/attachment/361299/noctua_nf_a14_industrialPPC_3000_pwm_specs_en.pdf), [web spec](https://www.noctua.at/en/products/nf-a14-industrialppc-3000-pwm/specifications) |
| Arctic P12 PWM PST | 56.3 CFM, 2.2 mmH₂O, 1800 RPM | [Datasheet](https://asset.conrad.com/media10/add/160267/c1/-/gl/815136458DS00/datenblatt-2841621-arctic-p12-pwm-pst-gehaeuseluefter-120-mm.pdf) |
| Liquid Freezer III 360 | 398 × 120 × 38 mm, 3× P12 | [Arctic](https://www.arctic.de/en/Liquid-Freezer-III-360/ACFRE00136A) |
| Corsair AF Elite, LL, RS | See `presets/fans/` | Comptoir du Hardware, Hardwareluxx, TechPowerUp, [Corsair RS ARGB](https://www.corsair.com/us/en/explorer/diy-builder/fans/corsair-rs-argb-fans-everything-you-need-to-know/) |

Every other number in `presets/` is either sourced the same way or marked approximate with an assumption. The loader rejects a bare number that has neither.

## Install

Python 3.10 or newer.

```bash
uv venv
uv pip install -e ".[dev]"
```

## Usage

```bash
uv run gpusim sweep --build meshify2xl-stefano --mc 200 --out results
uv run gpusim run --build meshify2xl-stefano --spacing gap1 --pressure standard --shroud on --leakage leaky
uv run gpusim run --spacing stacked --rear-duct passive
uv run gpusim optimize --cards 4 --case meshify2xl
uv run gpusim schematic --build meshify2xl-stefano --out plots/schematic.png
uv run gpusim calibrate --log examples/nvidia_smi.csv
uv run gpusim ui
```

`gpusim ui` prints `gpusim ui at http://127.0.0.1:8000` and serves a local 3D
side view. three.js r160 is vendored under `gpusim/ui/static/vendor` (the ES
module, so the page does not fetch unpkg and does not load `three.min.js`).
If port 8000 is busy the server says so and binds the next free port.
Quick start loads Stefano's Meshify or the plain Corsair 9000D sample
(`corsair-9000d-sample`). The Mike Bradley 9000D button is a separate
illustrative mock, labelled as such. Click a mount to add or flip a fan; the
fan list is filtered by 120 / 140 / 170 mm. Drag a fan onto another mount or a
card onto another slot. Compare, Demo (arrow keys), and Presentation hide the
controls for an OBS window. The 3D view frames the whole case, including the
top radiator, rear shroud and PSU shroud, and draws the case outline plus an
intake / exhaust / blanked legend. The footer repeats the accuracy line and
the water-block limit.

Demo script: [DEMO.md](DEMO.md). What to measure next: [HYPOTHESIS.md](HYPOTHESIS.md).
Fit notes: [docs/CALIBRATION.md](docs/CALIBRATION.md).

## Agent API

For people whose agents spec out their own rigs. The same JSON works over HTTP,
on the command line, and in Python. Interactive docs are at `/docs` (FastAPI);
the exported contract is [`docs/openapi.json`](docs/openapi.json) and the request
schemas are [`docs/simspec.schema.json`](docs/simspec.schema.json)
(`uv run gpusim schema` regenerates both).

| Endpoint | Body | Returns |
|---|---|---|
| `POST /api/v1/simulate` | `SimSpec`: `build` + optional `extra_fans`, `extra_cards`, `options` | per-card die / memory / inlet / exhaust °C, CFM, fan duty, power, throttle, case Pa; `options.detail = "full"` adds the flow network and each card's thermal chain |
| `POST /api/v1/rank` | `base` spec + `variants` (merge patch and/or `set`) | variants ranked by hottest die; a broken variant reports its error in place |
| `POST /api/v1/sweep` | `base` spec + `factors` | full factorial (≤ 256 cells), ranked |
| `GET /api/v1/presets` | — | case / card / fan / radiator / build ids, slot counts, mount ids, seal levels, curves |
| `GET /api/v1/builds/{id}` | — | a saved build to edit and post back |
| `GET /api/v1/schema` | — | JSON Schemas for the three bodies |

A `build` names a case, lists mounts (fan id, `intake`/`exhaust`, or
`blanked`/`empty`), GPUs with slots (`"1"`…, `"v2"` for a vertical slot), card
id, `fan_curve` (`stock`, `custom_accelerated`, or `custom` with points), seal
levels 1–5, filters, `cpu` (`power_w`, `cooling: air|water`), radiator,
shroud, obstruction and cables. Fans or cards that are not in `presets/` can be
sent inline: a fan with its two intercepts or P–Q points, a card with
`calibration_from` an existing card type (it borrows that cooler's calibrated
physics). Sweep and `set` accept macros (`spacing`, `pressure`, `shroud`,
`leakage`, `fan_curve`, `cpu_cooling`, `obstruction`, `cables`) and dotted
paths such as `gpus.*.power_limit_w` or `shroud.count`.

```bash
uv run gpusim ui --no-open-browser --port 8010 &
curl -s -X POST localhost:8010/api/v1/simulate \
  -H 'content-type: application/json' \
  -d @examples/api/simulate_custom_rig.json | jq '.summary, .cards'
curl -s -X POST localhost:8010/api/v1/rank \
  -H 'content-type: application/json' \
  -d @examples/api/rank_meshify_variants.json | jq '.results[] | {rank, name, hottest: .summary.hottest_die_c}'
```

```python
import json, urllib.request
spec = json.load(open("examples/api/simulate_custom_rig.json"))
req = urllib.request.Request("http://127.0.0.1:8010/api/v1/simulate",
                             data=json.dumps(spec).encode(),
                             headers={"content-type": "application/json"})
result = json.load(urllib.request.urlopen(req))
print(result["summary"]["hottest_die_c"], [c["t_die_c"] for c in result["cards"]])

# No server: the same call in-process.
from gpusim import api
result = api.simulate(api.SimSpec.model_validate(spec))
```

Offline CLI twins: `uv run gpusim simulate examples/api/simulate_custom_rig.json`
and `uv run gpusim rank examples/api/sweep_5090_spacing.json` (a file with
`factors` runs as a sweep). A fuller client is `examples/api_client.py`.
Every response carries the accuracy line and the scope: air-cooled only,
Celsius, ±5–10 °C absolute.

## Sweep on Stefano's build

16 cells (spacing × pressure × shroud × leakage) plus the stock row. Ranked by
throttled hottest die, then unthrottled hottest die, then mean die. Lower is
better. `sh` is the shroud, `l` is leakage, `p` is pressure. Per-card columns
are unthrottled dies, top to bottom. On gapped and stacked rows the fourth card
is the vertical one. Stock matches the stacked / standard / shroud-off / leaky cell.

| Rank | Config | Hottest | Unthrottled | gpu1 | gpu2 | gpu3 | gpu4 | Case Pa | Throttle |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | gap1, standard, shroud on, leaky | 84.3 | 84.3 | 84.3 | 84.3 | 84.2 | 84.2 | −7.8 | no |
| 2 | gap1, standard, shroud on, sealed | 84.3 | 84.3 | 84.3 | 84.3 | 84.2 | 84.3 | −13.8 | no |
| 3 | gap1, high, shroud on, leaky | 84.8 | 84.8 | 84.8 | 84.8 | 84.7 | 84.7 | +11.2 | no |
| 4 | gap1, high, shroud on, sealed | 85.7 | 85.7 | 85.7 | 85.7 | 85.6 | 85.7 | +18.0 | no |
| 5 | gap1, standard, shroud off, sealed | 86.4 | 86.4 | 86.4 | 86.4 | 86.3 | 86.3 | −12.3 | no |
| 6 | gap1, standard, shroud off, leaky (anchor A) | 86.5 | 86.5 | 86.5 | 86.5 | 86.4 | 86.4 | −4.9 | no |
| 7 | gap1, high, shroud off, leaky | 86.7 | 86.7 | 86.7 | 86.7 | 86.6 | 86.6 | +10.5 | no |
| 8 | gap1, high, shroud off, sealed | 88.6 | 88.6 | 88.6 | 88.6 | 88.5 | 88.5 | +18.8 | yes |
| 9 | stacked, standard, shroud on, leaky | 90.0 | 104.2 | 96.8 | 104.2 | 84.4 | 83.8 | −6.6 | yes |
| 10 | stacked, standard, shroud on, sealed | 90.0 | 104.3 | 96.8 | 104.3 | 84.4 | 83.8 | −12.0 | yes |
| 11 | stacked, standard, shroud off, sealed | 90.1 | 108.7 | 100.6 | 108.7 | 86.9 | 86.2 | −10.5 | yes |
| 12 | stacked, high, shroud on, leaky | 90.1 | 104.6 | 97.2 | 104.6 | 84.9 | 84.3 | +12.3 | yes |
| 13 | stacked, standard, shroud off, leaky | 90.1 | 108.8 | 100.8 | 108.8 | 87.1 | 86.4 | −4.0 | yes |
| 14 | stock (same as 13) | 90.1 | 108.8 | 100.8 | 108.8 | 87.1 | 86.4 | −4.0 | yes |
| 15 | stacked, high, shroud off, leaky | 90.1 | 108.6 | 100.7 | 108.6 | 87.2 | 86.6 | +11.6 | yes |
| 16 | stacked, high, shroud on, sealed | 90.1 | 105.9 | 98.6 | 105.9 | 86.3 | 85.7 | +19.0 | yes |
| 17 | stacked, high, shroud off, sealed | 90.2 | 111.3 | 103.4 | 111.3 | 89.9 | 89.2 | +19.6 | yes |

Open air, one card, stock curve: **82.8 °C**. The same card on the aggressive
curve: **73.4 °C**.

Anchor B (four horizontal cards, no vertical, not a factorial row): unthrottled
100.7, 108.9, 108.7, 87.1 °C. The middle two are hottest. Throttle flags on the
three cards that cross 90 °C.

Winner of the factorial, per card: 84.3, 84.3, 84.2, 84.2 °C, about 26.5 CFM.
Stock unthrottled flow on the hot middle card is about 14.5 CFM. Its fan faces
the next card across 3.6 mm. The lowest horizontal card sees the 40 mm
PSU-shroud clearance and stays near 87 °C. Monte Carlo bands (5th–95th hottest
die): stock 94–129 °C, best gapped cell 74–101 °C. The tails overlap.

Full table and the generated hypothesis: `results/meshify2xl-stefano/`
(`hypothesis_auto.md`; the root `HYPOTHESIS.md` is hand-written). With the
default `--out results`, plots stay in `plots/meshify2xl-stefano/`. Any other
`--out` puts plots under `<out>/plots`. Charts: die temperature with 5th–95th
bars, flow, case pressure, schematic, stock tornado. Bounds check: all nominal
anchors pass.

The best air-cooled search result (`gpusim optimize --cards 4 --case meshify2xl`)
is gaps plus a vertical card, shroud on, standard case-fan direction, leaky,
aggressive GPU curve: **75.5 °C**.

## Other factors the model actually uses

Obstruction (low / medium / high), cable management (clean / cluttered), PSU
under a shroud or open and fan up or down, drive cage, dust-filter density,
radiator thickness and FPI, rear bracket open area, altitude (air density),
per-card power limit, side panel (glass, mesh, or removed), a small buoyancy
term (off by default), and an optional room re-ingestion offset for a case
against a wall. Seal level is a five-step open-area fraction on every interface.
Slot gap state is derived from the slot map for each inlet face: open slot,
blocked slot (cover or cables), or no slot (fan face against the next card,
about 3.6 mm).

## How to extend

**A fan.** Add `presets/fans/<id>.yaml`. Give a `_source` URL or set
`_approximate: true` with an `_assumption`. Include size, RPM, airflow in m³/h
and CFM, static pressure in mmH₂O, and `pq_points_m3h_mmh2o`. If the vendor
only published the two intercepts, put a quadratic curve under an assumption
that says so. The UI lists the top fans of each size from this directory.

**A card.** Copy `presets/cards/custom-blower-300w.yaml` (it is marked
`template: true`) or add a real card next to the Max-Q file. Add a matching
block in `gpusim/calib.py` `CARD` for the blower and the thermal resistances.
That block is per card type, shared by every slot. Do not add a fudge that
depends on which sweep cell is running. Refit open air and both anchors
together, and write the result in `docs/CALIBRATION.md`.

**A case.** Add `presets/cases/<id>.yaml` with outside dimensions, slot count,
mounts (id, panel, size, schematic x/y/z), leak areas, and radiator support.
Set `airflow_layout` to `direct_front_to_gpu` when the front fans blow straight
at the cards, or `mixed` when they blow into a general volume first. Then add
a build under `presets/builds/` so `gpusim run --build <id>` has something to load.

**A radiator.** `presets/radiators/<id>.yaml`: size, thickness, FPI, fan count,
default fan id. Thickness and FPI scale the air-side loss. If FPI is unpublished,
mark it approximate.

**A full build.** `presets/builds/<id>.yaml` points at a case, lists GPU slots,
mounts (fan id, intake or exhaust, or blanked), the radiator, the shroud, seal
levels and filters.

**Calibrate from a log.**

```bash
nvidia-smi --query-gpu=timestamp,index,power.draw,temperature.gpu,temperature.memory,fan.speed,clocks.sm --format=csv -l 1
uv run gpusim calibrate --log your_log.csv
```

The fit returns a Nusselt coefficient and a TIM resistance. It does not edit
`calib.py` for you. After you paste them in, re-check both anchors. An example
file is `examples/nvidia_smi.csv`.

## Tests

```bash
uv run pytest -q
```

Covers preset citations, open air 75–85 °C, anchor A within 3 °C of 86, anchor B
throttling with the middle cards hottest, the aggressive curve under ~75 °C,
shroud flow versus shroud off, mass conservation, energy balance within 2%,
convergence on all 16 cells and every case preset, solve time under 0.5 s,
and a UI smoke test that loads both demo scenarios.
