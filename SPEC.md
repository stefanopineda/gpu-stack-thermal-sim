# SPEC — gpu-stack-thermal-sim (revision 2)

An open-source Python tool that simulates airflow and temperatures inside multi-GPU AI workstations using a
**coupled flow-resistance network + thermal-resistance network** (compact model / thermal–electrical
analogy). It is **not CFD**. It has two jobs:

1. **Hypothesis generator** — a ranked, uncertainty-bounded 16-cell factorial sweep (plus stock baseline)
   so real-world airflow testing on Stefano's PC is spent on the most promising configurations.
2. **Live visualizer** (primary deliverable) — an interactive, stream-ready (OBS) UI to build a case
   configuration, move fans and cards, and watch airflow, pressure and temperatures update live, to
   compare configurations and demonstrate the physics to creators.

The PC is already built and in hand (Stefano's own machine). Implement everything below. Commit and push to
`origin main` as you go (small, meaningful commits). If earlier code exists in the repo, refactor it freely.

---

## 0. Terminology (use consistently in code, UI and docs)

| Term | Meaning |
|---|---|
| **blower card** | GPU with a radial (blower) fan that pulls air in at the card's fan inlet (top/side of the shroud, facing the neighbouring slot) and exhausts through the **rear I/O bracket** |
| **rear exhaust duct** | a shroud/duct fitted over the rear I/O brackets outside the case that collects blower exhaust and routes it away from the case (prevents exhaust being re-ingested). Two levels: `off` / `on` |
| **case pressure** | static pressure of the case interior relative to ambient: positive (more intake than exhaust) or negative |
| **mount** | a fan/radiator position on a case panel (front, top, rear, bottom, side) |
| **interface** | any opening between the case interior and ambient (panel mesh, filter, PCIe slot covers, gaps, rear bracket vents) |
| **seal level** | 5-step porosity setting of an interface (see §5) |
| **slot gap state** | what occupies the space next to a card's blower inlet (see §6) |
| **stock** | the baseline configuration defined in §3 |

---

## 1. Hardware

### 1.1 GPUs (primary)
**4x NVIDIA RTX PRO 6000 Blackwell Max-Q Workstation Edition**: 300 W TBP each (configurable power limit per
card), dual-slot, blower-style, exhausting out the rear I/O bracket. This is the **default and primary card**.
Verify published specs (TBP, dimensions, slot width) from NVIDIA/partner pages and cite them.

Card definition fields: power (W) and power-limit, slot width, blower P–Q curve (max static pressure, max flow,
curve shape, RPM range, fan-ramp curve), heatsink proxies (fin area, hydraulic diameter, fin-channel loss k),
TIM resistance, die→heatsink and memory→heatsink resistances, memory power share, throttle temperature
(default 88 °C, configurable ~87–90 °C), shroud/backplate area for adjacent-card preheating, fan inlet area
and position. Each value carries a `source:` or `assumption:` note.

Also include a generic **`custom-blower-300w`** card template (clearly labelled as a template) so users can add
other blower cards. No other named card models are required.

### 1.2 Stefano's own build (default configuration)
- Case: **Fractal Design Meshify 2 XL**
- Case fans: **Noctua redux, 1700 RPM class** (see open question Q1 on exact model/size)
- CPU cooler: **Arctic 360 mm AIO radiator (Liquid Freezer class)** with 3x Arctic P12-class 120 mm fans;
  radiator thickness parameter default 38 mm (see open question Q2)
- GPUs: 4x RTX PRO 6000 Blackwell Max-Q
- The **16-cell factorial sweep + stock baseline runs on this default configuration**.

---

## 2. Data files (all presets are data, not code)

Directory `presets/` with YAML (or TOML), validated by a schema (pydantic or equivalent):
- `cards/*.yaml`, `fans/*.yaml`, `radiators/*.yaml`, `cases/*.yaml`, and
- `builds/*.yaml` (a full configuration: case + mounts + fans + radiator + GPU slot map + seal levels +
  obstructions + ambient), and `scenarios/*.yaml` (demo steps, sweep definitions).
Every numeric value has a `source:` URL/citation or `approximate: true` with an `assumption:` note.

### 2.1 Case presets
Each case: external dimensions (W×H×D mm), internal volume estimate, motherboard form factors, expansion slot
count and slot pitch (20.32 mm), slot position relative to case bottom, PSU location/shroud, fan and radiator
mount positions with allowed sizes/counts per panel, stock filter/panel type and porosity, side panel type,
drive cage options. Required:

1. **Fractal Design Meshify 2 XL** (Stefano's case) — use published specs: 240 × 566 × 600 mm (W×H×D),
   9 horizontal + 3 vertical expansion slots; front 3×140 / 4×120 (radiator up to 480/420 mm);
   top 3×140 / 4×120 (radiator up to 480/420 mm); rear 1×120/140 (radiator 120 mm); bottom 2×120/140
   (radiator up to 280/240 mm); dust filters top, front, bottom; mesh front and top; tempered glass side;
   PSU shroud (non-removable). Source: Fractal product sheet
   (https://www.fractal-design.com/app/uploads/2020/10/Meshify-2-XL-_Product-Sheet_EN.pdf). Verify and cite.
2. **Corsair iCUE 9000D RGB Airflow** — verify published dimensions, expansion slot count, and fan/radiator
   mounts from Corsair's spec page; cite.
3. **Generic ATX mid-tower**, **generic mATX**, **generic E-ATX full tower** — standard dimensions and
   typical mounts (label as generic/approximate).
4. **Phanteks multi-GPU case** — the request was "a Phanteks case with 13 expansion slots". Published specs
   checked so far show no current Phanteks case with 13 slots: **Enthoo Elite Server** = 12 PCIe slots
   (582 × 261 × 721 mm, phanteks.com; one Phanteks release text says 11), **Enthoo Pro 2 Server V2** = 11,
   original **Enthoo Elite** = 10. Implement **Phanteks Enthoo Elite Server (12 slots)** as the multi-GPU
   Phanteks preset, verify from phanteks.com, and keep the slot count a data field (see open question Q3).
5. **"Mike Bradley powerhouse" (demo mock)** — a 9000D-style maximum-airflow multi-GPU build. Must be
   labelled everywhere (file, UI, docs) as **"Illustrative mock — not a measurement or claim about anyone's
   real build."**

### 2.2 Fan library
Each fan: size (mm), RPM (min/max), airflow (CFM and m³/h), static pressure (mmH₂O and Pa), P–Q curve points
or parametric curve (if the manufacturer publishes only max flow and max pressure, use a documented generic
curve shape and flag `approximate: true`), noise, source. Fans scale with RPM by affinity laws
(Q ∝ N, P ∝ N²). Required entries:
- **Generic 140 mm** and **generic 170 mm** case fans (170 mm is less common but supported).
- **Corsair** standard fans: AF120/AF140 (Elite), LL120/LL140, RS120/RS140 — verify published specs.
- **Noctua redux**: **NF-P12 redux-1700 PWM** (120 mm, published specs), the **140 mm redux** models
  (e.g. NF-P14s redux-1500 PWM / NF-A14 redux where published; verify names and specs on noctua.at), and a
  **"Noctua redux-class 170 mm @1700 RPM"** entry flagged `approximate: true` (Noctua does not appear to
  publish a 170 mm redux; see Q1).
- **Arctic P12 (PWM PST) class** 120 mm fans for the 360 mm radiator.
- Rule: case-fan mounts default to 140 mm (170 mm optional where the case allows); **radiator fans are the
  exception** and use 120 mm (3×120 for a 360 mm radiator).

### 2.3 Radiators
Radiator = airflow resistance (quadratic k scaled by core thickness and fin density, FPI) + heat source into
the air stream (CPU package power, configurable, default e.g. 150 W under GPU load). Default:
**Arctic Liquid Freezer-class 360 mm, 38 mm thick** (flag approximate; see Q2). Position: front/top,
intake/exhaust.

---

## 3. Factorial sweep: 2^4 = 16 cells + stock baseline (on Stefano's default build)

| Factor | Level A | Level B |
|---|---|---|
| **spacing** | `stacked`: cards in adjacent dual-slot positions, no free slot between cards (card N's blower inlet faces card N-1's backplate) | `gap1`: one empty slot between each pair of cards (requires enough slots; the Meshify 2 XL has 9) |
| **pressure** | `high` (positive): all case fans intake, case interfaces sealed (foil tape), radiator as intake, the **only** exhaust path is through the GPU blowers (rear brackets) | `standard`: radiator as exhaust plus top/rear exhaust fan(s) running, front intake |
| **duct** | rear exhaust duct `off` | rear exhaust duct `on` (collects blower exhaust at the rear brackets, small added resistance, prevents re-ingestion of exhaust) |
| **leakage** | `sealed` (seal level 1–2 on panels/slot covers) | `leaky` (realistic stock: seal level 3–4) |

**Stock baseline** (reported as its own row labelled `stock`, even though it coincides with one cell):
`stacked`, `standard` pressure, duct `off`, `leaky`, with Stefano's stock fan directions.

Also run a **single card in open air** reference (1 card, no case, 25 °C ambient) for calibration.

---

## 4. Flow network

Nodes (pressures): ambient (reference, P = 0), case main volume, GPU zone sub-volume, each card's blower
inlet region (the gap next to it), each card's blower exhaust / rear bracket, rear-exhaust-duct plenum (when
on), radiator, each fan mount, PSU chamber (if shrouded), leakage interfaces.
- Branches are sign-aware quadratic resistances `dP = k * Q * |Q|` (reverse flow and recirculation
  representable). k derived from geometry (loss coefficients, free-area ratio, orifice equations) with
  documented assumptions (Idelchik-style loss coefficients).
- Fans and blowers are pressure sources with P–Q curves scaled by RPM (affinity laws); a fan on an empty
  mount becomes an open orifice; a blanked mount is closed (or seal level 1).
- Solve nonlinear mass conservation at every internal node with `scipy.optimize.root` or a damped Newton
  solver with analytic Jacobian; robust initial guess; report residuals; fail loudly on non-convergence.
- **Recirculation**: blower exhaust partially re-ingested (through rear leakage/slot covers/nearby intakes)
  when case pressure is negative and there is no duct — modelled as a pressure-dependent recirculation branch
  and mixing fraction.
- **Adjacent-card preheating**: card N's inlet air is a mix of GPU-zone air and air heated by card N-1's
  backplate/shroud; when `stacked` the inlet gap is small (see §6), raising intake resistance.
  Card numbering: card 1 = closest to the CPU (top slot), card 4 = lowest. Document this.
- Air density from ideal gas with temperature and **altitude**; conserve mass flow, not volumetric flow.
- Optional buoyancy (stack effect), off by default.

## 5. Interfaces and seal levels

Every case interface (front/top/bottom/side panels and their filters, PCIe slot covers, rear bracket vent
pattern, panel seams/gaps, mount openings) has a **seal level** with 5 steps, each mapped to a documented
effective open-area fraction / orifice discharge coefficient → k:

| Level | Name | Meaning |
|---|---|---|
| 1 | tightly sealed | taped/foam-sealed, near-zero leakage |
| 2 | some air gaps | seams and small gaps only |
| 3 | moderate airflow | typical stock panel/filter |
| 4 | moderate penetration | open mesh, missing covers |
| 5 | wide open | panel removed / fully open |

Dust filter density per intake (none / fine / dense) adds a separate resistance.

## 6. GPU layout and inter-card airflow (critical)

- **Explicit slot map**: which expansion slots hold which card; the solver derives gap geometry around each
  card: card-to-card gap, card-to-PSU-shroud gap (lowest card), card-to-side-panel clearance, card-to-bottom
  fan distance.
- The space next to each card's blower inlet has one of three **slot gap states**:
  1. `open_slot` — empty PCIe slot, low resistance, good flow;
  2. `blocked_slot` — slot cover/blocker or cable obstruction present, reduced flow;
  3. `no_slot` — no space at all (card directly against the next card or the shroud): high resistance, the
     blower intake is **starved** and cannot pull air.
- **Blower intake starvation**: effective inlet area from gap size vs blower demand; model as an inlet
  resistance k(gap) that rises steeply as gap → 0, and a blower operating point that drops accordingly.
- The UI must show what is accounted for at each interface and each internal resistance
  (label with name, k, flow, ΔP).

## 7. Internal obstructions and other factors

Include, document, and expose in both the data files and the UI:
- Obstruction level `low / medium / high` in the GPU zone; cable management `clean` (routed behind the tray)
  vs `cluttered` (cables in the GPU zone).
- PSU placement (bottom under shroud vs open; PSU fan intake orientation up/down), PSU chamber isolation.
- Drive cages present/removed (front intake resistance).
- Dust filter density per intake.
- Radiator thickness, FPI and position (front/top, intake/exhaust), CPU heat load.
- Rear bracket vent pattern (open area) of each card.
- Ambient temperature, altitude/air density.
- GPU power limit per card.
- Side panel type (tempered glass vs mesh; side fan mounts if the case supports them).
- Motherboard/CPU cooler heat load in the case; room exhaust re-ingestion (case near a wall) as an optional
  ambient offset.
Add any other factor with material impact and note it in the spec section of the README.

## 8. Thermal network (per card)

Nodes: die, memory, heatsink, air stream (inlet → outlet).
- Die→heatsink: TIM conduction + spreading resistance. Memory→heatsink resistance with its own power share.
- Heatsink→air: velocity-dependent convection `h` from a Nusselt correlation form (e.g.
  `Nu = C * Re^m * Pr^(1/3)` for fin channels), using the blower operating-point flow; ε-NTU or log-mean
  temperature for the air stream.
- Enthalpy rise `Q = m_dot * cp * (T_out - T_in)`.
- Small linearized radiation term shroud/backplate → case walls; backplate heat into the neighbour's inlet.
- **Iterate flow ⇄ thermal to convergence** (density vs temperature; fan ramp changes blower RPM → flow).
- Optional **fan-ramp** model and **throttle** model: die ≥ throttle threshold (~87–90 °C, default 88 °C)
  → `throttle = True`; optionally reduce power to find the throttled equilibrium; report both.

## 9. Outputs per configuration/cell

Per-card die temperature, memory temperature, exhaust temperature, mass and volumetric flow (CFM), case
pressure relative to ambient (Pa), throttle flag, solver residuals, energy balance error. **Ranked
recommendation**: sort by hottest die (ascending), tie-break by mean die temperature.

## 10. Calibration & honesty (enforced in code and tests)

- **Single card in open air at 300 W: die 75–85 °C** (target ~83 °C). Tune only global/per-card physical
  parameters (never per-cell). Document in `docs/CALIBRATION.md`.
- **4 cards stacked, stock baseline: middle cards (2 and 3) hottest and hottest die > ~85 °C.**
- Every sweep run evaluates these bounds and writes `bounds_check.json` / `.md` (pass/fail + numbers);
  violations are flagged loudly.
- **pytest** (`tests/`): calibration bounds; middle cards hottest in stacked stock; energy balance
  (heat in == enthalpy out within 1–2 %); mass conservation at every node; preset/schema validation for all
  data files; convergence for all 16 cells + stock and for every case preset; solve time < 0.5 s per
  configuration (no MC); API/UI smoke test.
- **Monte Carlo / sensitivity** over uncertain parameters (branch k's, fan/blower curves, h coefficient, TIM,
  ambient, leakage/seal mapping) with documented distributions; default N = 200, fixed seed; report 5th–95th
  percentile per card and hottest die per cell; tornado (one-at-a-time) sensitivity for stock.
- State in README, UI footer, and outputs: **typical accuracy ±5–10 °C absolute; better for ranking
  configurations than for absolute temperatures.**
- Cite the method honestly (no fabricated page numbers): compact thermal models / thermal–electrical analogy
  and flow network modelling — G. N. Ellison, *Thermal Computations for Electronics: Conductive, Radiative,
  and Convective Air Cooling* (CRC Press); I. E. Idelchik, *Handbook of Hydraulic Resistance*; flow network
  modelling for electronics cooling (e.g. Electronics Cooling magazine articles on FNM).

## 11. Visualizer (primary deliverable, designed for OBS live streaming)

- One command: `uv run gpusim ui` (opens a local web app; e.g. FastAPI + lightweight frontend, or
  Streamlit/Panel/Dash — your choice, but interaction must feel live). Uses the same solver.
- **Configuration controls** (very easy, visual): pick case; per mount (front/top/rear/bottom/side) set
  intake / exhaust / empty (open) / blanked, fan model and count; radiator model/position/direction; GPU slot
  map and slot gap states; seal level per interface; obstruction level, cable management, PSU, drive cages,
  filters, side panel, ambient, altitude, power limit.
- **Drag/move** fans and cards on the 2D case side view (snapping to valid mounts/slots) and see results
  update live (debounced; solver < ~0.5 s per solve without MC).
- **Overlay**: resistor network drawn on the 2D side view; airflow arrows scaled/coloured by magnitude and
  direction (reverse flow visible); colour map of air temperature by zone; per-card die/memory temps;
  throttle warnings; case pressure (+/−, Pa); hover/labels showing each resistance's k, flow and ΔP.
- **Stream theme**: dark, clean, large fonts, 1920×1080 layout, no clutter, suitable for OBS browser-source or
  window capture; presenter-friendly (hide-controls toggle / "presentation mode").
- **Compare mode**: two configurations side by side with Δ per card.
- **Demo mode**: scripted stepping through saved scenarios (keyboard next/prev + optional auto-advance):
  1. Stefano's build — Meshify 2 XL + Noctua redux fans + Arctic 360 radiator + 4x RTX PRO 6000 Blackwell
     Max-Q: stock → sealed/high-pressure → spaced (gap1) → rear exhaust duct → best combination.
  2. "Mike Bradley powerhouse" 9000D-style **illustrative mock** for comparison.
- **DEMO.md**: run-of-show with talking points per step (what changes physically and why the temps move).

## 12. Other deliverables

- Package `gpusim/`, `pyproject.toml` (Python ≥ 3.10; numpy, scipy, pandas, matplotlib, pyyaml, pydantic,
  click/typer, plus the UI stack; optional graphviz). `uv venv && uv pip install -e ".[dev]"`.
- CLI:
  - `gpusim sweep [--build meshify2xl-bw-maxq-4x] [--mc 200] [--out results/]` — 16 cells + stock + open-air
    reference → `results/<build>/results.csv`, `results.md` (ranked table), `bounds_check.json/.md`, plots
    in `plots/<build>/`.
  - `gpusim run --build ... --spacing stacked --pressure high --duct on --leakage sealed`
  - `gpusim schematic --build ...` — network schematic PNG (graphviz if available, else matplotlib).
  - `gpusim calibrate --log nvidia_smi.csv` — least-squares fit of h/TIM from nvidia-smi logs
    (power.draw, temperature.gpu, fan.speed, optional memory temp) with an example log in `examples/`.
  - `gpusim ui` — visualizer.
- Plots (PNG): die temp vs config with MC error bars (per card and hottest), flow vs config, case pressure vs
  config, network schematic.
- **HYPOTHESIS.md**: 3–5 cells worth testing physically on Stefano's PC, each with predicted ΔT vs stock
  (with MC range), confidence, reasoning, and recommended test order (cheapest/most informative first).
- **README.md**: what/why, method + citations, install, usage (CLI + UI), real example output table,
  accuracy statement, and **How to extend**: add a card/case/fan/radiator/build, and calibrate from nvidia-smi
  logs (`nvidia-smi --query-gpu=timestamp,index,power.draw,temperature.gpu,temperature.memory,fan.speed,clocks.sm --format=csv -l 1`).
- Run the sweep for Stefano's default build (and optionally the 9000D mock build) and commit `results/`
  and `plots/`. Everything passes `pytest -q`. Push to GitHub.

## 13. Engineering notes

- Physically plausible, documented parameters; transparency over curve-fit magic.
- Rankings must emerge from physics (flow split, recirculation, preheating, starvation), never hard-coded
  per-configuration offsets.
- Deterministic by default (fixed seeds). Sweep with MC in a few minutes on a laptop.

## 14. Open questions for Stefano (keep in README "Open questions" and surface in the report)

- **Q1 — Case fans:** you described Noctua redux 1700 RPM fans as 17 cm. Noctua's redux line appears to be
  published in 120 mm (NF-P12 redux-1700 PWM) and 140 mm (redux-1500) sizes only. Which exact model and size
  are installed? Until confirmed, the build uses 140 mm redux fans in the case mounts, and the 170 mm
  redux-class entry is approximate.
- **Q2 — Radiator:** described as an "Arctic SP5" radiator form factor; modelled as an Arctic Liquid
  Freezer-class 360 mm, 38 mm thick radiator with 3x P12-class fans. Please confirm model, thickness,
  position (front/top) and direction (intake/exhaust).
- **Q3 — Phanteks case:** no current Phanteks case with 13 expansion slots found in published specs
  (Enthoo Elite Server 12, Enthoo Pro 2 Server V2 11, Enthoo Elite 10). The Enthoo Elite Server (12) is used;
  confirm the intended model.
- **Q4 — Slot usage/layout:** which Meshify 2 XL slots currently hold the four cards (stacked from the top
  slot?), and what is in the gaps (slot covers, cables)? This sets the stock slot map.
- **Q5 — Stock fan directions/counts:** confirm current mount usage in the Meshify 2 XL (front/top/rear/bottom,
  intake/exhaust) so `stock` matches the real machine.
