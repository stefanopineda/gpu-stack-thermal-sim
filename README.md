# gpusim

A compact airflow and temperature model for air-cooled multi-GPU workstations.
It is a coupled flow-resistance network and a thermal-resistance network. It is
not CFD. It has three jobs: rank case configurations before you spend a weekend
moving fans, show that ranking live (including on an OBS browser source), and
answer the same questions for an agent over a JSON API.

GPU water blocks are out of scope. The audience is people who keep the stock
cooler on the card: blowers (RTX PRO 6000 Max-Q) and flow-through cards (RTX
PRO 6000 Workstation, RTX 5090 FE, RTX 3090 FE). A water-cooled CPU is
supported because its radiator changes the case airflow. Large towers are the
point; ITX and SFF only get a generic case and the same solver. Temperatures
are Celsius everywhere. Fahrenheit is a display toggle in the UI. Default
ambient is 25 °C.

Typical accuracy is about **±5–10 °C absolute**. Trust the ranking more than
the number. A Monte Carlo band that overlaps a neighbour means the model cannot
tell those two cells apart.

This is revision 4 of the spec ([SPEC.md](SPEC.md)); the rev 4 plan is
[docs/REV4_PLAN.md](docs/REV4_PLAN.md).

## Build assumptions

Resolved with Stefano (SPEC rev 3), unchanged in rev 4:

- Case fans are Noctua **140 mm redux at 1700 RPM**. The library entry scales the published NF-P14s redux-1500 PWM curve by the fan laws and is marked approximate.
- CPU cooler is an Arctic 360 mm radiator with its three Arctic P12-class fans, **top exhaust, push**, carrying 150 W of CPU heat (approximate). The CPU is **water-cooled** in this build.
- The Phanteks multi-GPU preset is the **Enthoo Elite Server, 12 slots** (dimensions read as H × W × D).
- Meshify 2 XL has 9 horizontal slots and 3 vertical slots off to the side. Stefano runs with **all slot brackets removed**.
- The rear exhaust shroud covers the bracket plane and is pulled by **two NF-A14 industrialPPC-3000 PWM** fans. A passive duct is still runnable.
- GPUs are 4× RTX PRO 6000 Blackwell Max-Q, 300 W, dual-slot blowers, in slots 1, 4 and 7 plus vertical slot `v2` (assumption). A rear 140 mm redux exhaust is assumed.
- Anchor A (gaps, no shroud, stock curve) is the bench point at 86 °C. Anchor B (four horizontal cards, no gaps, stock curve) throttles at a 90 °C cutoff, middle cards hottest.

Rev 4 decisions (all documented as assumptions in the presets and SPEC §14):

- **Seal levels run 1 = fully open (100 %) to 5 = sealed (0 %)**, the reverse of rev 3: 2 = 70 % (open grille, missing covers), 3 = 45 % (typical mesh + filter), 4 = 5 % (seams, small gaps). The default side panel is 5 (solid glass or metal): no branch, infinite resistance.
- The **Corsair 9000D RGB AIRFLOW ships with no fans** (Corsair: "Included Fans: No Fans Included"). The 9000D template fills its published 8×120 front array (4 high × 2 wide) with Corsair AF120 RGB ELITE intakes.
- **Custom Accelerated** GPU fan curve: 0 % at 25 °C, linear to 100 % at 70 °C. It replaces rev 3's `maxq_aggressive`, which still works as an alias.
- **Plume ingestion**: a flow-through card's exhaust jet points at the fan face of the card above, which draws `φ(gap) = 0.85 · exp(−gap / 40 mm)` of its fan-side intake from that jet.
- Obstruction and cable management are k multipliers on the internal branches (obstruction 1.0 / 2.5 / 6.0, cables 1.0 / 2.0).

`stock` in the sweep table is the factorial baseline (stacked, standard pressure, shroud off, leaky). It is the same configuration as one of the 16 cells and is repeated as its own row.

## Method

Two coupled solves.

**Airflow network** (pressure is voltage, volumetric flow is current). Nodes are
ambient, the main case volume, the GPU zone, each card's inlet and exhaust, the
CPU cooler outlet (air-cooled CPU), and a rear plume or a shroud plenum. Every
branch obeys `ΔP = k Q|Q|`, orifice `k = ρ / (2 Cd² A²)`, plus fans whose
pressure-flow curve scales by the affinity laws `Q ∝ N`, `P ∝ N²`. Mass is
conserved at every node. The nonlinear system is a damped Newton solve with an
analytic Jacobian; it raises if it does not converge.

**Thermal network** (temperature is voltage, heat is current). Each card has a
die, a memory node, a heatsink and an airstream. Heatsink-to-air is
`R_conv = 1 / (ε ṁ c_p)` with ε-NTU and `Nu = C Re^m Pr^(1/3)`, fed by the mass
flow from the airflow solve; a parallel `R_ext` runs through the shroud and
backplate. Air temperatures come from an advection balance on the solved flow.
Then `T_die = T_in + Q_channel · R_conv + P_die · R_tim`. The fan duty follows
the card's curve and air density follows temperature, so the two solves iterate
until both settle. At the throttle flag (88 °C default) the card is flagged;
above the cutoff (90 °C, 93 °C for the 3090) power is reduced to the throttled
equilibrium. Both temperatures are reported.

The fan face of every card points down, toward the floor. Blowers exhaust out
the rear bracket. **Flow-through cards** exhaust up through the backplate into
the gap above; that air rises into the main case volume, except the share the
card above swallows (the plume term). That share is an explicit coupling term,
not a resistor, because a resistor network would mix the jet with all the zone
air: it reroutes `ṁ_ing = min(φ · ṁ_upper intake, 0.98 · ṁ_jet)` from the lower
card's exhaust to the upper card's inlet and moves the displaced zone air the
other way, so every node still balances and energy in equals enthalpy out.

Two 5090 FE cards in the Meshify, stock curve, unthrottled:

| Empty slots between them | Gap | Upper | Lower | Upper − lower | Without the plume term |
|---|---:|---:|---:|---:|---:|
| 1 | 21.0 mm | 90.2 | 82.3 | +7.9 | +0.8 |
| 2 | 41.3 mm | 83.8 | 78.9 | +4.9 | +0.7 |
| 3 | 61.6 mm | 81.5 | 77.9 | +3.6 | +0.5 |

A **CPU** is air- or water-cooled. Water: its heat rides the radiator's air
stream. Air: a tower cooler branch (fan plus fin stack) pulls case air through
the heatsink and adds the CPU heat to the case, and the rear fan pulls from the
cooler outlet.

Clock offsets, undervolt and memory offset change the heat load with a rough
split (dynamic power ∝ f·V², a static share, a memory share), clamped to the
power limit. The UI labels them as approximations.

The method is the standard compact / thermal-electrical analogy and
flow-network approach for electronics cooling:

- G. N. Ellison, *Thermal Computations for Electronics* (CRC Press).
- I. E. Idelchik, *Handbook of Hydraulic Resistance*.
- Flow network modelling articles in *Electronics Cooling* magazine.

No page numbers are cited, because none were looked up for a quotation.

## Hardware sources

| Part | What was used | Source |
|---|---|---|
| RTX PRO 6000 Blackwell Max-Q | 300 W, dual slot, 4.4 in × 10.5 in, active cooler | [NVIDIA datasheet](https://www.nvidia.com/content/dam/en-zz/Solutions/products/workstations/professional-desktop-gpus/rtx-pro-6000-max-q/workstation-datasheet-blackwell-rtx-pro-6000-max-q-nvidia-us-5349650-web.pdf), [product page](https://www.nvidia.com/en-us/products/workstations/professional-desktop-gpus/rtx-pro-6000-max-q/) |
| Board size 266.7 × 111.15 × 37 mm | ELSA drawing, bracket excluded | [ELSA datasheet](https://www.elsa-jp.co.jp/wp-content/uploads/2025/03/Datasheet_NVIDIA_RTX_PRO_6000_Blackwell_Max-Q_Workstation_Edition.pdf) |
| Blower, rear exhaust | Retailer description. P–Q is approximate | [Central Computer](https://www.centralcomputer.com/blog/post/understanding-the-nvidia-rtx-6000-pro-blackwell-lineup-workstation-max-q-and-server-editions) |
| RTX PRO 6000 Blackwell Workstation Edition | 600 W, 5.4" × 12", dual slot, "Double-flow-through" | [NVIDIA datasheet](https://www.nvidia.com/content/dam/en-zz/Solutions/data-center/rtx-pro-6000-blackwell-workstation-edition/workstation-blackwell-rtx-pro-6000-workstation-edition-nvidia-us-3519208-web.pdf), [StorageReview](https://www.storagereview.com/review/nvidia-rtx-pro-6000-workstation-gpu-review-blackwell-architecture-and-96-gb-for-pro-workflows) (304 × 137 × 40 mm), [Puget](https://www.pugetsystems.com/labs/articles/nvidia-rtx-pro-6000-blackwell-workstation-content-creation-review/), [AEC Magazine](https://aecmag.com/workstations/review-nvidia-rtx-pro-blackwell-series-gpus/) |
| RTX 5090 Founders Edition | 575 W, 304 × 137 mm, 2-slot, double flow-through, 90 °C max | [NVIDIA](https://www.nvidia.com/en-us/geforce/graphics-cards/50-series/rtx-5090/), [Gamers Nexus](https://gamersnexus.net/gpus/nvidia-geforce-rtx-5090-founders-edition-review-benchmarks-gaming-thermals-power), [Tom's Hardware](https://www.tomshardware.com/pc-components/gpus/nvidia-geforce-rtx-5090-review/8) |
| RTX 3090 Founders Edition | 350 W, 313 × 138 mm, 3-slot, one push fan out the bracket + one pull-through fan, 93 °C max | [NVIDIA](https://www.nvidia.com/en-us/geforce/graphics-cards/30-series/rtx-3090-3090ti/), [Tom's Hardware cooler](https://www.tomshardware.com/news/a-closer-look-at-the-geforce-rtx-3080-rtx-3090-founders-edition-coolers), [review](https://www.tomshardware.com/reviews/nvidia-geforce-rtx-3090-review/6), [Legit Reviews](https://www.legitreviews.com/nvidia-geforce-rtx-3090-founders-edition-review_222243/14) |
| Meshify 2 XL | 600 × 240 × 566 mm (L×W×H), 9+3 slots, fan and radiator mounts | [Fractal](https://www.fractal-design.com/products/cases/meshify-series/meshify-2-xl/meshify-2-xl-black-light-tg/), [product sheet](https://www.fractal-design.com/app/uploads/2020/10/Meshify-2-XL-_Product-Sheet_EN.pdf) |
| 9000D RGB AIRFLOW | 307 × 698 × 698 mm, 8 horizontal + 2 vertical, front 8×120 / 3×140 / 2×200, no fans included | [Corsair](https://www.corsair.com/us/en/p/pc-cases/cc-9011273-ww/9000d-rgb-airflow-super-full-tower-pc-case-cc-9011273-ww), [press release](https://www.corsair.com/newsroom/press-release/corsair-announces-the-availability-of-the-icue-link-9000d-rgb-airflow-super-tower-pc-case) |
| AF120 RGB ELITE | 65.57 CFM, 2.68 mmH₂O, 2100 RPM | [Corsair](https://www.corsair.com/us/en/p/case-fans/co-9050153-ww/icue-af120-rgb-elite-120mm-pwm-fan-co-9050153-ww) |
| Enthoo Elite Server | 12 slots, PH-ES916E_BK02 | [Phanteks](https://phanteks.com/product/enthoo-elite-server-black/) |
| NF-P14s redux-1500 / NF-P12 redux-1700 | Published P–Q points | [P14s](https://www.noctua.at/en/products/nf-p14s-redux-1500-pwm/specifications), [P12](https://www.noctua.at/en/products/nf-p12-redux-1700-pwm/specifications) |
| NF-A14 iPPC-3000 | 269.3 m³/h, datasheet 10.52 mmH₂O vs web 6.58 | [Datasheet PDF](https://www.mikrocontroller.net/attachment/361299/noctua_nf_a14_industrialPPC_3000_pwm_specs_en.pdf), [web spec](https://www.noctua.at/en/products/nf-a14-industrialppc-3000-pwm/specifications) |
| Arctic P12 PWM PST | 56.3 CFM, 2.2 mmH₂O, 1800 RPM | [Datasheet](https://asset.conrad.com/media10/add/160267/c1/-/gl/815136458DS00/datenblatt-2841621-arctic-p12-pwm-pst-gehaeuseluefter-120-mm.pdf) |
| Liquid Freezer III 360 | 398 × 120 × 38 mm, 3× P12 | [Arctic](https://www.arctic.de/en/Liquid-Freezer-III-360/ACFRE00136A) |
| Corsair AF Elite, LL, RS | See `presets/fans/` | Comptoir du Hardware, Hardwareluxx, TechPowerUp, [Corsair RS ARGB](https://www.corsair.com/us/en/explorer/diy-builder/fans/corsair-rs-argb-fans-everything-you-need-to-know/) |

Every other number in `presets/` is either sourced the same way or marked approximate with an assumption. The loader rejects a bare number that has neither. No fan curve, fin geometry or TIM is published for any of the GPU coolers; those numbers are in `gpusim/calib.py` and are explained in [docs/CALIBRATION.md](docs/CALIBRATION.md).

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
uv run gpusim run --spacing stacked --rear-duct passive --fan-curve custom_accelerated
uv run gpusim optimize --cards 4 --case meshify2xl
uv run gpusim schematic --build meshify2xl-stefano --out plots/schematic.png
uv run gpusim calibrate --log examples/nvidia_smi.csv
uv run gpusim simulate examples/api/simulate_custom_rig.json
uv run gpusim rank examples/api/rank_meshify_variants.json
uv run gpusim schema
uv run gpusim ui
```

### The visualizer

`gpusim ui` prints `gpusim ui at http://127.0.0.1:8000` and serves the app. If
8000 is busy it says so and binds the next free port. three.js r160 is vendored
under `gpusim/ui/static/vendor` (the ES module, no CDN). Static files are served
`no-cache`, so a restarted server is never stale in the browser.

- **Start screen.** Quick start (Stefano's Meshify 2 XL, Corsair 9000D Airflow),
  **start from a template** (9000D Airflow, Meshify 2 XL, generic ATX, mATX,
  E-ATX, Phanteks Enthoo Elite Server), or build from scratch in any case.
- **Left bar.** Front, Top, Rear, Bottom, Side, Internals, GPUs. One panel at a
  time: a face shows its mounts (fan, direction, speed, "Set all"), seal level
  with its meaning, dust filter, radiator (front, top or bottom), and on the
  rear the brackets and the shroud. Internals holds the case, the CPU (watts,
  air or water, tower fan), obstruction, cables, drive cage, PSU, seams and the
  environment. GPUs holds card model (blower or flow-through), slot, power
  limit, **Stock / Custom Accelerated / Custom** fan curve, clock and voltage
  approximations, and spacing buttons.
- **3D case.** Fans lie flat on their face, so the ¾ camera shows them as ovals
  on the front, top, rear, bottom or glass side (blue intake, red exhaust, grey
  blanked). Cards sit at the rear wall, coloured by die temperature, with their
  own fans on the fan face and a plume cone on flow-through cards. The PSU is
  bottom-rear under its shroud; the radiator sits against its panel with its
  fans on it; the shroud hangs off the rear. Camera: ¾ front, side, ¾ rear.
  Identical fans on one face collapse to one label. A face inset draws the
  selected face head-on, scaled so every fan is visible.
- **Network view** (Split or Network). Layer 1 is the airflow network with
  labelled seal resistances (∞ for glass or metal), fan impedances, inter-card
  slot resistances, fin channels, brackets and plume branches, plus node
  pressures and temperatures. Layer 2 is each card's thermal chain, with
  `T_die = T_in + Q_ch·R_conv + P_die·R_tim` written out in numbers.
- **Tooltips.** Hover any input, legend entry or network element for the
  assumption behind it.
- Compare, Demo (arrow keys, auto), Present (hides controls for OBS),
  Optimize, °F.
- **Shareable demo:** `/?demo=mike-bradley` opens the Mike Bradley 9000D build.
  It is labelled everywhere: *Illustrative mock — not a measurement or claim
  about anyone's real build.* Other URL parameters: `?template=<build id>`,
  `?start=meshify|9000`, `?demo=stefano`, `?net=split|full`,
  `?view=front34|side|rear34`, `?present=1`.

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

16 cells (spacing × pressure × shroud × leakage) plus the stock row, Monte Carlo
200, seed 12345. Lower is better. Configurations that do not throttle come
first, by hottest die; configurations that throttle follow, by unthrottled
hottest die, because their throttled dies all sit on the cutoff. Per-card
columns are unthrottled dies, top to bottom; the fourth card is the vertical
one. MC is the 5th–95th percentile of the hottest unthrottled die.

| Rank | Config | Hottest | Unthrottled | gpu1 | gpu2 | gpu3 | gpu4 | MC 5–95 % | Case Pa | Throttle |
|---|---|---:|---:|---:|---:|---:|---:|---|---:|---|
| 1 | gap1, standard, shroud on, leaky | 84.2 | 84.2 | 84.2 | 84.2 | 84.1 | 84.1 | 76–98 | −6.4 | no |
| 2 | gap1, standard, shroud on, sealed | 84.3 | 84.3 | 84.3 | 84.3 | 84.2 | 84.2 | 76–98 | −12.9 | no |
| 3 | gap1, high, shroud on, leaky | 84.7 | 84.7 | 84.7 | 84.7 | 84.6 | 84.7 | 77–98 | +9.5 | no |
| 4 | gap1, high, shroud on, sealed | 85.5 | 85.5 | 85.5 | 85.5 | 85.4 | 85.5 | 77–99 | +17.6 | no |
| 5 | gap1, standard, shroud off, sealed | 86.4 | 86.4 | 86.4 | 86.4 | 86.3 | 86.3 | 78–100 | −11.6 | no |
| 6 | gap1, standard, shroud off, leaky (anchor A) | 86.6 | 86.6 | 86.6 | 86.6 | 86.5 | 86.5 | 78–100 | −3.7 | no |
| 7 | gap1, high, shroud off, leaky | 86.6 | 86.6 | 86.6 | 86.6 | 86.5 | 86.5 | 78–100 | +8.3 | no |
| 8 | gap1, high, shroud off, sealed | 88.3 | 88.3 | 88.3 | 88.3 | 88.2 | 88.2 | 79–102 | +18.3 | yes |
| 9 | stacked, standard, shroud on, leaky | 89.5 | 104.2 | 96.7 | 104.2 | 84.3 | 83.7 | 92–121 | −5.4 | yes |
| 10 | stacked, standard, shroud on, sealed | 89.5 | 104.2 | 96.7 | 104.2 | 84.3 | 83.7 | 92–121 | −11.1 | yes |
| 11 | stacked, high, shroud on, leaky | 89.6 | 104.6 | 97.2 | 104.6 | 84.9 | 84.3 | 93–122 | +10.6 | yes |
| 12 | stacked, high, shroud on, sealed | 89.6 | 105.7 | 98.3 | 105.7 | 86.0 | 85.4 | 94–123 | +18.6 | yes |
| 13 | stacked, high, shroud off, leaky | 89.5 | 108.5 | 100.6 | 108.5 | 87.1 | 86.4 | 95–126 | +9.2 | yes |
| 14 | stacked, standard, shroud off, sealed | 89.5 | 108.6 | 100.6 | 108.6 | 86.9 | 86.2 | 95–127 | −9.9 | yes |
| 15 | stacked, standard, shroud off, leaky | 89.5 | 108.8 | 100.8 | 108.8 | 87.2 | 86.5 | 96–127 | −3.1 | yes |
| 16 | stock (same as the stacked, standard, shroud off, leaky row) | 89.5 | 108.8 | 100.8 | 108.8 | 87.2 | 86.5 | 96–127 | −3.1 | yes |
| 17 | stacked, high, shroud off, sealed | 89.6 | 110.8 | 102.9 | 110.8 | 89.5 | 88.8 | 97–129 | +19.2 | yes |

Open air, one Max-Q, stock curve: **82.8 °C**. Custom Accelerated: **73.4 °C**.

Anchor B (four horizontal cards, no vertical, not a factorial row):
unthrottled 100.8, 109.0, 108.8, 87.2 °C. The middle two are hottest; three
cards throttle to the cutoff.

The winner is 84.2 °C on every card at about 26.5 CFM. The stock row's middle
card runs about 14.9 CFM: its fan faces the next card across 3.6 mm. Stock and
the best gapped cell overlap only between about 96 and 98 °C in their Monte
Carlo tails. The gapped layouts differ from each other by less than the noise.

`gpusim optimize --cards 4 --case meshify2xl` (48 candidates) picks gaps plus a
vertical card, shroud on, standard fan directions, leaky, Custom Accelerated:
**75.4 °C** (MC 68–88 °C).

Full table and the generated hypothesis: `results/meshify2xl-stefano/`
(`hypothesis_auto.md`; the root `HYPOTHESIS.md` is hand-written). With the
default `--out results`, plots stay in `plots/meshify2xl-stefano/`. Any other
`--out` puts plots under `<out>/plots`. Bounds check: all pass, including the
three flow-through open-air checks.

### What if the cards were flow-through?

Same Meshify slots (1, 4, 7, v2), shroud on, stock curve, 4× RTX PRO 6000
Workstation at 600 W: unthrottled 95.0, 93.1, 83.1 °C top to bottom and 83.3 °C
on the vertical card; the top two throttle. Each upper card breathes half of
the exhaust of the card below it (one empty slot, 21 mm). With Custom
Accelerated the top card still throttles (92.8 °C unthrottled). The fix for a
flow-through stack is spacing, not a shroud: two empty slots take the upper
card from +8 °C to +5 °C over the lower one.

## Other factors the model uses

Seal level per interface (1 open … 5 sealed; §5 of the spec has the table),
dust-filter density, obstruction (low / medium / high, k ×1 / 2.5 / 6) and cable
management (clean / cluttered, k ×1 / 2, plus ×1.35 on card inlets), CPU air or
water, PSU under a shroud or open and its fan up or down, drive cage, radiator
thickness, FPI and position, rear bracket open area, altitude (air density),
per-card power limit, side panel (glass, mesh, or removed), a small buoyancy
term (off by default), and an optional room re-ingestion offset for a case
against a wall. Slot gap state is derived from the slot map for each inlet face:
open slot, blocked slot (cover or cables), or no slot (fan face against the
next card).

## How to extend

**A fan.** Add `presets/fans/<id>.yaml`. Give a `_source` URL or set
`_approximate: true` with an `_assumption`. Include size, RPM, airflow in m³/h
and CFM, static pressure in mmH₂O, and `pq_points_m3h_mmh2o`. If the vendor
only published the two intercepts, put a quadratic curve under an assumption
that says so. An agent can instead send the fan inline in `extra_fans`.

**A card.** Copy `presets/cards/custom-blower-300w.yaml` (a blower template) or
one of the flow-through cards. Set `cooler: blower` or `cooler: flow_through`.
Add a block in `gpusim/calib.py` `CARD`, per card type, shared by every slot;
flow-through blocks also need `exit_width_m` and `exit_area_m2`. Do not add a
fudge that depends on the sweep cell. Set it against one open-air temperature
you can cite and record it in `docs/CALIBRATION.md`. Through the API, a card
can borrow a calibrated block with `calibration_from`.

**A case.** Add `presets/cases/<id>.yaml` with outside dimensions, slot count,
mounts (id, panel, size, x/y/z on that face), leak areas, and radiator support.
Mounts on one face should not overlap. Set `airflow_layout` to
`direct_front_to_gpu` when the front fans blow straight at the cards, or
`mixed` when they blow into a general volume first. Then add a build under
`presets/builds/` so it shows up as a template.

**A radiator.** `presets/radiators/<id>.yaml`: size, thickness, FPI, fan count,
default fan id. If FPI is unpublished, mark it approximate.

**A full build.** `presets/builds/<id>.yaml` points at a case, lists GPUs with
slots, mounts (fan id, intake or exhaust, or blanked), the radiator, the CPU
(`power_w`, `cooling`), the shroud, seal levels (1 open … 5 sealed) and filters.
Rev 3 builds without a `cpu` block still load: the CPU load is taken from the
radiator.

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

Covers preset citations and the required cards, fans and cases; open air
75–85 °C; anchor A within 3 °C of 86; anchor B throttling with the middle cards
hottest; Custom Accelerated under ~75 °C and linear from 25 to 70 °C, with the
`maxq_aggressive` alias; the flow-through open-air targets; the plume term
(upper card hotter, the gap closing with spacing, the jet cap, node and energy
balance, no plume on blowers); the seal scale and infinite level 5; CPU air and
water; obstruction multipliers; shroud flow versus shroud off; mass
conservation; energy balance within 2 %; convergence on all 16 cells and every
case preset; solve time under 0.5 s; the agent API (simulate, rank, sweep,
inline fans and cards, 422s, exported schema); and a UI smoke test.
