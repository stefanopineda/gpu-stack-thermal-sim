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
- Anchor A (gaps, no shroud, stock curve) is the bench point at about 86 °C. Anchor B (four cards, no gaps, stock curve) throttles at a 90 °C cutoff.
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
uv run gpusim sweep --build meshify2xl-stefano --mc 200 --out results --plots plots
uv run gpusim run --build meshify2xl-stefano --spacing gap1 --pressure standard --shroud on --leakage leaky
uv run gpusim run --spacing stacked --rear-duct passive
uv run gpusim optimize --cards 4 --case meshify2xl
uv run gpusim schematic --build meshify2xl-stefano --out plots/schematic.png
uv run gpusim calibrate --log examples/nvidia_smi.csv
uv run gpusim ui
```

`gpusim ui` serves a local 3D side view (three.js) with the solver behind it.
Quick start loads Stefano's Meshify or the 9000D illustrative mock and shows a
die temperature immediately. Click a mount to add or flip a fan; the fan list
is filtered by 120 / 140 / 170 mm. Drag a fan onto another mount or a card onto
another slot. Compare, Demo (arrow keys), and Presentation hide the controls
for an OBS window. The footer repeats the accuracy line and the water-block limit.

Demo script: [DEMO.md](DEMO.md). What to measure next: [HYPOTHESIS.md](HYPOTHESIS.md).
Fit notes: [docs/CALIBRATION.md](docs/CALIBRATION.md).

## Sweep on Stefano's build

16 cells (spacing × pressure × shroud × leakage) plus the stock row. Ranked by
throttled hottest die, then unthrottled hottest die, then mean die. Lower is
better. `sh` is the shroud, `l` is leakage, `p` is pressure.

| Rank | Config | Hottest °C | Unthrottled °C | Mean °C | Case Pa | Throttle |
|---|---|---:|---:|---:|---:|---|
| 1 | gap1, standard, shroud on, leaky | 84.3 | 84.3 | 83.7 | −8.0 | no |
| 2 | gap1, standard, shroud on, sealed | 84.4 | 84.4 | 83.8 | −14.0 | no |
| 3 | gap1, high, shroud on, leaky | 84.9 | 84.9 | 84.2 | +11.0 | no |
| 4 | gap1, high, shroud on, sealed | 85.8 | 85.8 | 85.1 | +17.8 | no |
| 5 | gap1, standard, shroud off, sealed | 86.5 | 86.5 | 85.8 | −12.5 | no |
| 6 | gap1, standard, shroud off, leaky (anchor A) | 86.5 | 86.5 | 85.9 | −5.0 | no |
| 7 | gap1, high, shroud off, leaky | 86.7 | 86.7 | 86.1 | +10.4 | no |
| 8 | gap1, high, shroud off, sealed | 88.6 | 88.6 | 87.9 | +18.6 | yes |
| 9–17 | every stacked cell, including stock | 90.1–90.2 | 134–142 | | | yes |

Open air, one card, stock curve: **82.8 °C**. The same card on the aggressive
curve: **73.4 °C**.

Winner, per card (top horizontal, middle, lower, vertical): 84.1, 84.3, 82.2, 84.1 °C,
about 26 CFM each. Stock (stacked, shroud off): the middle horizontal card is
the one that runs away, about 140 °C unthrottled and 8 CFM, while the cards
with an open inlet stay in the mid-80s and the throttled equilibrium is 90 °C.

Full table, per-card columns and Monte Carlo bands: `results/meshify2xl-stefano/`.
Plots: `plots/meshify2xl-stefano/` (die temperature with 5th–95th bars, flow,
case pressure, schematic, stock tornado). Bounds check: all nominal anchors pass.

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
Slot gap state is derived from the slot map: open slot, blocked slot (cover or
cables), or no slot (card against the next backplate).

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
