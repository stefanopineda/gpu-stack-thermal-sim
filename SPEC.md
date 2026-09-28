# SPEC — gpu-stack-thermal-sim

An open-source Python tool that simulates airflow and temperatures in multi-GPU AI workstations using a
**coupled flow-resistance network + thermal-resistance network** (compact model / thermal–electrical
analogy). It is **not CFD**. Its purpose is to **generate ranked, uncertainty-bounded hypotheses before a
physical case-airflow parameter sweep**, so the real-world test time is spent on the most promising cells.

Implement everything below. Commit and push to `origin main` as you go (small, meaningful commits).

---

## 1. Target hardware (presets are config, not code)

Presets live in `presets/` as YAML (or TOML) and must be easy to add to. Split into composable pieces:
`cards/*.yaml`, `cases/*.yaml`, `fans/*.yaml`, and rig presets `rigs/*.yaml` that reference them.

Required rig presets:

1. **`rtx6000ada-4x`** — 4x NVIDIA RTX 6000 Ada Generation, blower-style, dual-slot, **300 W TBP each**,
   exhausting out the rear I/O bracket. Workstation tower case with front intake fans, a top/back exhaust fan,
   and an AIO CPU radiator (position configurable: intake or exhaust).
2. **`rtxpro6000-bw-maxq-4x`** — 4x NVIDIA RTX PRO 6000 Blackwell **Max-Q** Workstation Edition (300 W,
   blower, dual-slot, rear exhaust) — this is for a Delaware shipment. Same case unless noted.

Each card definition: power (W), slot width, blower P–Q curve parameters (max static pressure, max flow,
curve shape), blower fan-speed range, heatsink geometry proxies (fin area, hydraulic diameter, fin-channel
flow resistance k), TIM resistance, die→heatsink and memory→heatsink resistances, memory power share,
throttle temperature, backplate/shroud surface area for adjacent-card preheating. Each value gets a
`source:` / `assumption:` note (datasheet, review measurement, or engineering estimate).

## 2. Experimental factors: 2^4 = 16 cells + stock baseline

| Factor | Level A | Level B |
|---|---|---|
| **spacing** | `stacked` (cards in adjacent dual-slot positions, 0 free slots between; intake of card N partly blocked by card N-1 backplate) | `gap1` (one empty slot between each card) |
| **pressure** | `high`: all case fans are intake, case sealed with foil tape, radiator mounted as intake, the **only** exhaust is through the GPU blowers (rear brackets) | `standard`: radiator as exhaust + top/back exhaust fan running |
| **duct** | `off` | `on`: turbo exhaust duct over the rear brackets (collects blower exhaust and ducts it away; adds a small resistance but prevents exhaust recirculation back into the case/front intake) |
| **leakage** | `sealed` (small leakage area) | `leaky` (realistic unsealed case: PCIe slot covers, gaps, mesh panels) |

**Stock baseline** (explicit, reported separately and also flagged in the table): `stacked`, `standard`
pressure, duct `off`, `leaky`. (Note it coincides with one of the 16 cells; still report it as its own
labeled row named `stock`.)

Also run a **single card in open air** reference case (1 card, no case, ambient 25 °C) used for calibration.

## 3. Flow network

Nodes (pressures): ambient (reference, P=0), case volume, each card's intake plenum/gap region, each
card's blower exhaust/rear bracket, duct plenum (when on), radiator, top/back exhaust, leakage paths.

- Branches are quadratic resistances: `dP = k * Q * |Q|` (sign-aware so reverse flow / recirculation is
  representable). k derived from geometry (loss coefficients / free area) with documented assumptions.
- Fans and blowers are pressure sources with parameterized P–Q curves (e.g. `dP = Pmax * (1 - (Q/Qmax)^n)`
  or polynomial), scaled by fan speed via fan affinity laws. Note sources/assumptions for each curve.
- Solve nonlinear mass conservation at every internal node with `scipy.optimize.root` (hybr/lm) or Newton,
  with a robust initial guess and convergence checks. Report residuals.
- **Recirculation**: a fraction of blower exhaust re-enters the case (rear exhaust can be pulled back through
  leakage/front intake when the case is negative-pressure and there is no duct). Model this as a
  pressure-dependent recirculation branch/mixing fraction.
- **Adjacent-card preheating**: card N's intake air is a mix of case air and air heated by card N-1's
  backplate/shroud; when `stacked`, card N's intake is also partly blocked (higher intake resistance). Card
  ordering: card 1 is nearest the CPU (top), card 4 lowest (nearest PSU/bottom), document the convention.
- Air density is temperature-dependent (ideal gas); mass flow is conserved, not volumetric flow.

## 4. Thermal network (per card)

Nodes: die (GPU junction), memory (GDDR), heatsink, air stream (inlet → outlet).
- Die→heatsink: TIM conduction resistance + spreading.
- Memory→heatsink (or memory→baseplate) resistance; memory has its own power share.
- Heatsink→air: convection with velocity-dependent `h` from a Nusselt correlation form
  (e.g. `Nu = C * Re^m * Pr^(1/3)` for fin channels), using the blower's operating-point flow through the
  fin stack. Use effectiveness–NTU or log-mean formulation for the air-stream temperature rise.
- Air enthalpy rise: `Q_heat = m_dot * cp * (T_out - T_in)`.
- Small radiation term from shroud/backplate to case walls (linearized).
- Backplate heat into the neighbouring card's intake (links to §3 preheating).
- **Iterate flow ⇄ thermal to convergence** (density vs temperature; fan-ramp changes blower speed which
  changes the flow operating point).
- Optional **buoyancy** term (stack effect in the case), off by default.
- Optional **fan-ramp** model (blower speed rises with die temp between configurable thresholds) and
  **throttle** model: if die ≥ throttle threshold (~87–90 °C, configurable per card; default 88 °C) flag
  `throttle=True` and optionally reduce power to find the throttled equilibrium; report both the
  unthrottled prediction and the flag.

## 5. Outputs per cell

Per-card die temperature, memory temperature, exhaust temperature, per-card mass/volumetric flow
(CFM), case pressure relative to ambient (Pa), throttle flag, solver residuals. Plus a **ranked
recommendation**: rank by hottest die (ascending), tie-break by mean die temperature.

## 6. Calibration & honesty checks (must be implemented in code and in tests)

- **Single card in open air at 300 W** must land at **75–85 °C** die (target ~83 °C, a commonly reported
  value for RTX 6000 Ada under sustained load). Tune free parameters (e.g. heatsink h constant/TIM) to this;
  document the tuning in `docs/CALIBRATION.md`.
- **4 cards stacked, stock baseline (no exhaust help)**: the **middle cards (2 and 3) must be the hottest**
  and hottest die **> ~85 °C**.
- The code must evaluate these bounds on every sweep run and print/write a `bounds_check` section
  (pass/fail + numbers) into the results; violations are flagged loudly (not silently).
- **pytest tests** (in `tests/`):
  - calibration bounds (single card open air 75–85 °C);
  - middle cards hottest in stacked stock;
  - energy balance: total heat in == total enthalpy out of the case (within tolerance, e.g. 1–2 %);
  - mass conservation at every node (residual below tolerance);
  - preset loading / schema validation; solver convergence for all 16 cells + stock.
- **Monte Carlo / sensitivity**: sample uncertain parameters (branch resistances, fan/blower curves,
  h coefficient, TIM resistance, ambient temperature, leakage area) with documented distributions;
  N configurable (default e.g. 200, fixed seed). Report per cell the 5th–95th percentile of hottest die and
  per-card die temps. Also provide a one-at-a-time (tornado) sensitivity summary for the stock case.
- State clearly in README and outputs: **typical accuracy ±5–10 °C absolute; the model is better for
  ranking configurations than for absolute temperatures.**
- Cite the method: compact thermal models / thermal–electrical analogy and flow network modeling, e.g.
  D. S. Steinberg / **G. N. Ellison, "Thermal Computations for Electronics: Conductive, Radiative, and
  Convective Air Cooling"** (CRC Press), and flow network modeling literature (e.g. Belady / Kelkar &
  Patankar / "Flow Network Modeling for electronics cooling" in Electronics Cooling magazine; Idelchik,
  "Handbook of Hydraulic Resistance" for loss coefficients). Keep citations honest (no fabricated page numbers).

## 7. Deliverables

- Python package `gpusim/` (src layout OK), `pyproject.toml` (Python ≥3.10; deps: numpy, scipy, pandas,
  matplotlib, pyyaml, click or typer; optional graphviz). Installable with `uv pip install -e .` or `pip install -e .`.
- **CLI** `gpusim`:
  - `gpusim sweep --preset rtx6000ada-4x [--mc 200] [--out results/]` — runs 16 cells + stock (+ single-card
    reference), writes `results/<preset>/results.csv`, `results/<preset>/results.md` (Markdown ranked table),
    `results/<preset>/bounds_check.json` (and .md), plots.
  - `gpusim run --preset ... --spacing stacked --pressure high --duct on --leakage sealed` — single cell.
  - `gpusim schematic --preset ...` — network schematic.
  - `gpusim calibrate --log nvidia_smi.csv` — fit h/TIM from an nvidia-smi log (power.draw, temperature.gpu,
    fan.speed, optionally memory temp) — at minimum a working least-squares fit on the open-air/single-card
    model with an example log in `examples/`.
- **Plots (PNG)** per preset in `plots/<preset>/`: die temp vs config with MC error bars (per card and hottest),
  flow vs config, case pressure vs config; plus a network schematic (graphviz if available, else matplotlib).
- **HYPOTHESIS.md**: 3–5 cells worth testing physically, each with predicted ΔT vs stock (with MC range),
  confidence level and reasoning, and a recommended physical test order (cheapest/most informative first).
  Include the Blackwell Max-Q preset notes.
- **README.md**: what/why, method summary + citations, install, usage, example output (paste real
  generated table), accuracy statement, and **"How to extend"**: add your own card/case/fans, and calibrate
  from nvidia-smi logs (`nvidia-smi --query-gpu=timestamp,index,power.draw,temperature.gpu,fan.speed,clocks.sm --format=csv -l 1`).
- **Run the sweep for both presets** and commit `results/` and `plots/`.
- Everything passes `pytest -q`. Push to GitHub.

## 8. Engineering notes

- Keep parameters physically plausible and documented; prefer transparency over curve-fit magic.
- The model must genuinely produce the ranking from physics (flow split, recirculation, preheating),
  not from hard-coded per-config offsets.
- Deterministic by default (fixed seeds). Sweep with MC should run in a few minutes at most on a laptop.
- If you tune calibration, never tune per-cell; only global/per-card physical parameters.
