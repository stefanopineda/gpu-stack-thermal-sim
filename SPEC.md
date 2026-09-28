# SPEC — gpu-stack-thermal-sim (revision 3)

An open-source Python tool that simulates airflow and temperatures inside multi-GPU AI workstations using a
**coupled flow-resistance network + thermal-resistance network** (compact model / thermal–electrical
analogy). It is **not CFD**. It has two jobs:

1. **Hypothesis generator** — a ranked, uncertainty-bounded 16-cell factorial sweep (plus stock baseline)
   so real-world airflow testing on Stefano's PC is spent on the most promising configurations.
2. **Live visualizer** (primary deliverable) — an interactive, stream-ready (OBS) 3D UI to build a case
   configuration, place/flip fans and move cards, and watch airflow, pressure and temperatures update live,
   to compare configurations, find an optimal air-cooled build, and demonstrate the physics to creators.

**Audience/scope:** airflow-first, **air-cooled** multi-GPU builders who will not put cards on water blocks.
**GPU water cooling (water blocks) is out of scope** — state this in the UI and README. Tuned for large
multi-GPU cases (full towers); ITX/SFF get basic support only.

**Units:** Celsius everywhere in the model, data files, outputs and UI. Fahrenheit only as a back-end
conversion / optional UI display toggle. Default ambient **25 °C**.

The PC is already built and in hand (Stefano's own machine). Implement everything below. Commit and push to
`origin main` as you go (small, meaningful commits). If earlier code exists in the repo, refactor it freely.

---

## 0. Terminology (use consistently in code, UI and docs)

| Term | Meaning |
|---|---|
| **blower card** | GPU with a radial (blower) fan that pulls air in at the card's fan inlet (top/side of the shroud, facing the neighbouring slot) and exhausts through the **rear I/O bracket** |
| **rear exhaust shroud** | a shroud fitted over the rear PCIe/I/O bracket area outside the case, forming a **shared exhaust plenum** over every GPU bracket outlet, with its own fans (count/model configurable) pulling suction across all outlets. Stefano's real build has one with 2x Noctua NF-A14 industrialPPC-3000 PWM. Selectable on every case preset |
| **passive rear duct** | the same shroud without fans (collects/routes exhaust, adds a small resistance, prevents re-ingestion). Kept as an option, not a sweep factor |
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

**GPU fan (blower) curve presets** — a per-card user input that affects the whole picture:
- `stock`: duty rises with die temperature but **caps around ~70 % duty even near 88–90 °C** (the behaviour
  Stefano observes);
- `maxq_aggressive`: reaches **100 % duty at 70 °C**; in good airflow it should keep a card **under ~75 °C**;
- `custom`: user-editable (temp → duty points).
Blower P–Q scales with duty (RPM) via affinity laws (Q ∝ N, P ∝ N²); the solver iterates duty ⇄ die temp.

**Adjustable initial conditions (labelled "approximation" in the UI):** power limit (W), memory clock offset,
undervolt (mV or % V), CUDA core clock offset. Map to heat load with simple documented approximations, e.g.
dynamic power `P_dyn ∝ f · V²` plus a static/leakage share and a memory-power share scaling with memory
clock; clamp to the power limit. Document the formulas and that they are rough.

Also include a generic **`custom-blower-300w`** card template (clearly labelled as a template) so users can add
other blower cards. No other named card models are required.

### 1.2 Stefano's own build (default configuration; resolved with Stefano, see §14)
- Case: **Fractal Design Meshify 2 XL** — 9 horizontal expansion slots + 3 vertical slots off to the side.
  **All slot brackets/covers removed (open)**; straight front-to-GPU airflow; very low internal resistance.
- Case fans: **Noctua 140 mm redux-1700** (140 mm, 1700 RPM) in the front/other case mounts.
- CPU cooler: **Arctic 360 mm AIO radiator** with the **three Arctic 120 mm (P12-class) fans it came with**;
  default **top-mounted, exhaust (push)** — a default assumption, flippable in the UI; thickness default
  38 mm (approximate).
- GPUs: 4x RTX PRO 6000 Blackwell Max-Q: **3 horizontal cards + 1 card vertically mounted** in the Meshify's
  vertical slots (provide presets for each of the 3 vertical slot positions).
- **Rear exhaust shroud**: custom shroud covering all PCIe output slots with **two Noctua NF-A14
  industrialPPC-3000 PWM** (140 mm) fans pulling suction across every GPU output slot.
- Ambient 25 °C. GPU fan curve `stock` by default.
- The **16-cell factorial sweep + stock baseline runs on this default configuration** (build id e.g.
  `meshify2xl-stefano`).

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
   Phanteks preset, verify from phanteks.com, and keep the slot count a data field (confirmed by Stefano, §14).
5. **"Mike Bradley powerhouse" (demo mock)** — a 9000D-style maximum-airflow multi-GPU build. Must be
   labelled everywhere (file, UI, docs) as **"Illustrative mock — not a measurement or claim about anyone's
   real build."**

### 2.2 Fan library
Each fan: size (mm), RPM (min/max), airflow (CFM and m³/h), static pressure (mmH₂O and Pa), P–Q curve points
or parametric curve (if the manufacturer publishes only max flow and max pressure, use a documented generic
curve shape and flag `approximate: true`), noise, source. Fans scale with RPM by affinity laws
(Q ∝ N, P ∝ N²). Required entries:
Required entries (the UI's "top ~10" list per size is drawn from these):
- **Noctua 140mm redux-1700** (Stefano's case fans): base on the published **NF-P14s redux-1500 PWM**
  (140×140×25, 1500 RPM, 133.7 m³/h = 78.7 CFM, 1.91 mmH₂O; noctua.at) scaled to 1700 RPM by affinity laws
  (≈151.5 m³/h ≈ 89.2 CFM, ≈2.45 mmH₂O) — flag `approximate: true` (scaled). Also include the unscaled
  NF-P14s redux-1500 PWM and NF-P12 redux-1700 PWM (120 mm, published specs).
- **Noctua NF-A14 industrialPPC-3000 PWM** (shroud fans): 140×140×25, 3000 RPM, 269.3 m³/h (158.5 CFM),
  0.55 A, 6.6 W @ 12 V. Static pressure: Noctua's datasheet PDF lists **10.52 mmH₂O** with P–Q points
  (269.3 m³/h, 0), (208.2, 2.6), (139.3, 3.98), (65.7, 7.67), (0, 10.52 mmH₂O), while the current web spec page
  lists 6.58 mmH₂O. Use the datasheet curve, note the discrepancy, and cover it in the Monte Carlo range.
- **Arctic P12 (PWM PST)** 120 mm — also used as the **three Arctic 120 mm radiator fans**.
- **Corsair** AF120/AF140 (Elite), LL120/LL140, RS120/RS140 — verify published specs.
- **Generic 120 mm, generic 140 mm, generic 170 mm** case fans (170 mm less common, still supported; no
  Noctua 170 mm entry is used in Stefano's build).
- Rule: case-fan mounts default to 140 mm (170 mm where the case allows); **radiator fans are the exception**
  (3×120 mm for a 360 mm radiator).

### 2.3 Radiators
Radiator = airflow resistance (quadratic k scaled by core thickness and fin density, FPI) + heat source into
the air stream (CPU package power, configurable, default e.g. 150 W under GPU load). Default:
**Arctic 360 mm, 38 mm thick** (thickness approximate) with 3x Arctic P12-class fans, **top, exhaust (push)**
by default. Position front/top and direction intake/exhaust are user-flippable.

---

## 3. Factorial sweep: 2^4 = 16 cells + stock baseline (on Stefano's default build)

| Factor | Level A | Level B |
|---|---|---|
| **spacing** | `stacked`: the 3 horizontal cards in adjacent dual-slot positions, no free slot between them (the blower fan face points down at the next card; the lowest card's fan face points at the PSU-shroud clearance) | `gap1`: one empty slot between each pair of horizontal cards (the Meshify 2 XL has 9 horizontal slots) |
| **pressure** | `high` (positive): all case fans intake, case interfaces sealed (foil tape), radiator as intake, the **only** exhaust path is through the GPU blowers (rear brackets, plus the shroud when on) | `standard`: front intake, Arctic 360 radiator top exhaust plus rear exhaust fan (if mounted) |
| **shroud** | rear exhaust shroud `off` | rear exhaust shroud `on` with its fans (default 2x NF-A14 industrialPPC-3000) |
| **leakage** | `sealed` (seal level 1–2 on panels and rear slot openings) | `leaky` (realistic stock: seal level 3–4) |

Because all slot brackets are removed in Stefano's build, the open rear slot area is a real interface: it
is a leakage/recirculation path when the shroud is off, and it is covered by the shroud plenum when the
shroud is on.

The 4th card stays in its vertical-slot position in all cells (it is off to the side of the horizontal
stack). The passive rear duct is not a sweep factor but must be runnable via `gpusim run`.

**Stock baseline** (reported as its own row labelled `stock`, even though it coincides with one cell):
`stacked`, `standard` pressure, shroud `off`, `leaky`, stock GPU fan curve, Stefano's default fan
directions (front intake, radiator top exhaust).

Also run a **single card in open air** reference (1 card, no case, 25 °C ambient) for calibration.

---

## 4. Flow network

Nodes (pressures): ambient (reference, P = 0), case main volume, GPU zone sub-volume, each card's blower
inlet region (the gap next to it), each card's blower exhaust / rear bracket, rear exhaust shroud plenum (when
on, active or passive), radiator, each fan mount, PSU chamber (if shrouded), leakage interfaces.
- Branches are sign-aware quadratic resistances `dP = k * Q * |Q|` (reverse flow and recirculation
  representable). k derived from geometry (loss coefficients, free-area ratio, orifice equations) with
  documented assumptions (Idelchik-style loss coefficients).
- Fans and blowers are pressure sources with P–Q curves scaled by RPM (affinity laws); a fan on an empty
  mount becomes an open orifice; a blanked mount is closed (or seal level 1).
- Solve nonlinear mass conservation at every internal node with `scipy.optimize.root` or a damped Newton
  solver with analytic Jacobian; robust initial guess; report residuals; fail loudly on non-convergence.
- **Rear exhaust shroud**: a shared exhaust plenum node connected to every GPU bracket outlet (one branch per
  card, in parallel); the shroud fans are pressure sources from plenum → ambient, i.e. **in series with the
  blower outlets**; also model plenum leakage to ambient and back toward the case. Passive duct = same without
  fans.
- **Recirculation**: blower exhaust partially re-ingested (through rear leakage/slot covers/nearby intakes)
  when case pressure is negative and there is no shroud/duct — modelled as a pressure-dependent recirculation branch
  and mixing fraction.
- **Adjacent-card preheating**: in a tower the blower fan face points down, toward the floor. Card N's
  main inlet therefore sees the gap below it (card N+1's backplate, or the PSU-shroud clearance when
  nothing is below). A smaller backplate-side / end opening, when the card preset says the inlet is
  split, sees the gap above (card N-1, or the CPU-area clearance on the top card). When `stacked` the
  downward gap is only a few millimetres (see §6), so intake resistance rises. Card numbering: card 1 =
  closest to the CPU (top slot), card 4 = lowest. Document this.
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

- **Explicit slot map**: which expansion slots (horizontal and vertical) hold which card, and whether each
  slot bracket/cover is present or removed. The blower fan face points down. The solver derives the gap
  on each inlet face from that map, for every card the same way: the fan side sees the card below, empty
  slots, or the PSU-shroud clearance when nothing is below; the backplate / end side sees the card above
  or the CPU-area clearance. Also card-to-side-panel clearance and card-to-bottom fan distance. The
  lowest card is not a special bypass.
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
- **GPU fan curve** (stock / maxq_aggressive / custom, §1.1) is part of the flow ⇄ thermal iteration.
- **Throttle** model: die ≥ throttle threshold (~87–90 °C, default 88 °C) → `throttle = True`; hard cutoff
  90 °C; reduce power to find the throttled equilibrium; report both the unthrottled prediction and the
  throttled result.

## 9. Outputs per configuration/cell

Per-card die temperature, memory temperature, exhaust temperature, mass and volumetric flow (CFM), case
pressure relative to ambient (Pa), throttle flag, solver residuals, energy balance error. **Ranked
recommendation**: sort by hottest die (ascending), tie-break by mean die temperature.

## 10. Calibration & honesty (enforced in code and tests)

- **Single card in open air at 300 W: die 75–85 °C** (target ~83 °C). Tune only global/per-card physical
  parameters (never per-cell). Document in `docs/CALIBRATION.md`.
- **4 cards close-packed (all four horizontal, no gaps), stock GPU fan curve, no shroud: middle cards
  hottest and hottest die > ~85 °C.**
- **Calibration anchors — Stefano's real measurements** (pytest checks with tolerance, e.g. ±3 °C for A; and
  report the fit/residuals in `docs/CALIBRATION.md` and the bounds check):
  - **A)** Meshify 2 XL, 3 horizontal cards stacked **with gaps** + 1 vertical card off to the side, no
    booster/shroud fans, stock GPU fan curve → peaked ~86 °C, **stable ~86 °C** (hottest die).
  - **B)** 4 cards **close-packed (no gaps)**, stock curve → **thermal throttling, hit the 90 °C cutoff**
    (unthrottled prediction ≥ 90 °C, `throttle = True`).
  Fit only global/per-card physical parameters to single-card open air + A + B simultaneously; never per-cell.
- Every sweep run evaluates these bounds and writes `bounds_check.json` / `.md` (pass/fail + numbers);
  violations are flagged loudly.
- **pytest** (`tests/`): calibration bounds; middle cards hottest in stacked stock; energy balance
  (heat in == enthalpy out within 1–2 %); mass conservation at every node; preset/schema validation for all
  data files; convergence for all 16 cells + stock and for every case preset; solve time < 0.5 s per
  configuration (no MC); calibration anchors A and B; `maxq_aggressive` curve keeps a single card < ~75 °C in
  good airflow; shroud raises per-card flow vs shroud off; API/UI smoke test.
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
- **Rendering**: **3D side-view** case rendering in the browser (e.g. three.js; solver stays in Python behind
  a local API). Colour-coded, stream-readable: distinct colours for **intake** fans, **exhaust** fans, and
  **blanked/empty** mounts (e.g. blue / red / grey), GPUs coloured by die temperature.
- **Onboarding**: start screen with **Quick start** (templates: Corsair 9000D plain sample, Meshify 2 XL —
  Stefano's build) vs **Build from scratch**. The Mike Bradley 9000D build is a separate button, labelled
  as an illustrative mock. Quick start reaches a first thermal number in **under one minute**.
- **Fan placement**: click any mount (front/top/rear/bottom/side) to place a fan; **one-click flip
  intake/exhaust**; "Add fan" defaults to a generic case fan of the mount's size, then a dropdown of the top
  ~10 common fans **filtered by size (120/140/170 mm)** showing static pressure, RPM and CFM.
- **Configuration controls** (very easy, visual): pick case; radiator model/position/direction; rear exhaust
  shroud on/off/passive with fan model and count (any case); GPU slot map (horizontal + vertical slots),
  bracket present/removed and slot gap states; per-card GPU fan curve (stock / maxq_aggressive / custom);
  per-card initial conditions (power limit, memory clock, undervolt, core offset — labelled approximations);
  seal level per interface; obstruction level, cable management, PSU, drive cages, filters, side panel,
  ambient (°C), altitude.
- **Drag/move** fans and cards (snapping to valid mounts/slots) and see results update live (debounced;
  solver < ~0.5 s per solve without MC).
- **Optimal air-cooled build** mode: for a given card count (and optionally a case), search fan placement and
  direction, shroud, spacing and GPU fan curve (coarse grid or heuristic search on the fast solver) and
  recommend the best configuration with predicted per-card temps and MC uncertainty; also available as
  `gpusim optimize --cards 4 [--case meshify2xl]`.
- **Overlay**: live resistor network drawn on the side view (each resistance labelled with k, flow, ΔP); airflow arrows scaled/coloured by magnitude and
  direction (reverse flow visible); colour map of air temperature by zone; per-card die/memory temps;
  throttle warnings; case pressure (+/−, Pa); hover/labels showing each resistance's k, flow and ΔP.
- **Stream theme**: dark, clean, large fonts, 1920×1080 layout, no clutter, suitable for OBS browser-source or
  window capture; presenter-friendly (hide-controls toggle / "presentation mode").
- **Compare mode**: two configurations side by side with Δ per card.
- **Demo mode**: scripted stepping through saved scenarios (keyboard next/prev + optional auto-advance):
  1. Stefano's build — Meshify 2 XL + Noctua 140mm redux-1700 fans + Arctic 360 top exhaust + 3 horizontal
     + 1 vertical RTX PRO 6000 Blackwell Max-Q, all brackets removed, rear exhaust shroud with 2x NF-A14
     industrialPPC-3000: walk through close-packed (anchor B, throttling) → gaps + vertical, no shroud
     (anchor A, ~86 °C) → shroud on → high pressure → `maxq_aggressive` fan curve → optimal.
  2. "Mike Bradley powerhouse" 9000D-style **illustrative mock** for comparison.
- **DEMO.md**: run-of-show with talking points per step (what changes physically and why the temps move).

## 12. Other deliverables

- Package `gpusim/`, `pyproject.toml` (Python ≥ 3.10; numpy, scipy, pandas, matplotlib, pyyaml, pydantic,
  click/typer, plus the UI stack; optional graphviz). `uv venv && uv pip install -e ".[dev]"`.
- CLI:
  - `gpusim sweep [--build meshify2xl-stefano] [--mc 200] [--out results/]` — 16 cells + stock + open-air
    reference → `results/<build>/results.csv`, `results.md` (ranked table), `bounds_check.json/.md`, plots
    in `plots/<build>/`.
  - `gpusim run --build ... --spacing stacked --pressure high --shroud on --leakage sealed [--rear-duct passive] [--fan-curve maxq_aggressive]`
  - `gpusim optimize --cards 4 [--case ...]`
  - `gpusim schematic --build ...` — network schematic PNG (graphviz if available, else matplotlib).
  - `gpusim calibrate --log nvidia_smi.csv` — least-squares fit of h/TIM from nvidia-smi logs
    (power.draw, temperature.gpu, fan.speed, optional memory temp) with an example log in `examples/`.
  - `gpusim ui` — visualizer.
- Plots (PNG): die temp vs config with MC error bars (per card and hottest), flow vs config, case pressure vs
  config, network schematic.
- **HYPOTHESIS.md**: 3–5 cells worth testing physically on Stefano's PC, each with predicted ΔT vs stock
  (with MC range), confidence, reasoning, and recommended test order (cheapest/most informative first).
- **README.md**: what/why, scope (air-cooled only; water blocks out of scope; large cases first), method +
  citations, install, usage (CLI + UI), real example output table,
  accuracy statement, and **How to extend**: add a card/case/fan/radiator/build, and calibrate from nvidia-smi
  logs (`nvidia-smi --query-gpu=timestamp,index,power.draw,temperature.gpu,temperature.memory,fan.speed,clocks.sm --format=csv -l 1`).
- Run the sweep for Stefano's default build (and optionally the 9000D mock build) and commit `results/`
  and `plots/`. Everything passes `pytest -q`. Push to GitHub.

## 13. Engineering notes

- Physically plausible, documented parameters; transparency over curve-fit magic.
- Rankings must emerge from physics (flow split, recirculation, preheating, starvation), never hard-coded
  per-configuration offsets.
- Deterministic by default (fixed seeds). Sweep with MC in a few minutes on a laptop.

## 14. Resolved questions (answered by Stefano; record in README "Build assumptions")

- **Case fans:** Noctua **140 mm redux at 1700 RPM** → library entry "Noctua 140mm redux-1700" (NF-P14s
  redux curve scaled to 1700 RPM, approximate). No 170 mm Noctua in his build (generic 170 mm stays in the
  library).
- **Radiator:** Arctic 360 mm with its three 120 mm Arctic (P12-class) fans; default **top, exhaust (push)**
  — a default assumption, flippable in the UI.
- **Phanteks case:** **Enthoo Elite Server (12 slots)** confirmed.
- **Meshify 2 XL slots:** 9 horizontal + 3 vertical off to the side; **all slot brackets removed (open)**;
  straight front-to-GPU airflow, very low internal resistance. Current layout: 3 horizontal + 1 vertical.
- **Rear exhaust shroud:** custom shroud over all PCIe output slots with **two Noctua NF-A14
  industrialPPC-3000 PWM** fans pulling suction across every GPU output slot (shared plenum, §4). It replaces
  the passive duct as the sweep factor; a passive-duct option remains.
- **Ambient:** 25 °C; Celsius throughout.
- **Measured anchors:** A) 3 horizontal with gaps + 1 vertical, no booster/shroud fans, stock GPU curve →
  ~86 °C stable; B) 4 close-packed, stock curve → throttled at 90 °C cutoff.
- Remaining unknowns (approximate, covered by Monte Carlo): radiator thickness/FPI, exact stock GPU fan curve
  points, shroud leakage, NF-A14 iPPC-3000 static pressure (datasheet vs web page).
