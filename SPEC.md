# SPEC — gpu-stack-thermal-sim (revision 4.1)

An open-source Python tool that simulates airflow and temperatures inside multi-GPU AI workstations using a
**coupled flow-resistance network + thermal-resistance network** (compact model / thermal–electrical
analogy). It is **not CFD**. It has three jobs:

1. **Hypothesis generator** — a ranked, uncertainty-bounded 16-cell factorial sweep (plus stock baseline)
   so real-world airflow testing on Stefano's PC is spent on the most promising configurations.
2. **Live visualizer** (primary deliverable) — an interactive, stream-ready (OBS) 3D UI to build a case
   configuration face by face, place/flip fans and move cards, and watch airflow, pressure and
   temperatures update live, with a resistor-network view that shows how each number is computed.
3. **Agent API** (new in rev 4) — a versioned JSON API so an agent can post a full PC spec and get back
   per-card temperatures, or post variants / a factorial and get back a ranking.

**Audience/scope:** airflow-first, **air-cooled** multi-GPU builders who will not put cards on water blocks.
**GPU water cooling (water blocks) is out of scope** — stated in the UI, API responses and README. A
water-cooled **CPU** (AIO radiator) stays supported because it changes the case airflow; there are no
GPU-AIO paths. Tuned for large multi-GPU cases (full towers); ITX/SFF get basic support only.

**Units:** Celsius everywhere in the model, data files, outputs, API and UI. Fahrenheit only as a UI display
toggle. Default ambient **25 °C**.

Revision 4 implements Stefano's rev 4 brief (16 items). The item → section map is in §15; the working plan
is `docs/REV4_PLAN.md`. Everything in revision 3 that this revision does not change still holds.

---

## 0. Terminology (use consistently in code, UI and docs)

| Term | Meaning |
|---|---|
| **blower card** | GPU with a radial (blower) fan. Its fan face points down (toward the floor / PSU); air leaves through the **rear I/O bracket** |
| **flow-through card** | GPU with axial fans on the fan face (down) and a fin stack that is open on the backplate side, so air leaves **up** into the gap above the card, plus a smaller share out the bracket. RTX PRO 6000 Blackwell Workstation Edition, RTX 5090 FE, RTX 3090 FE |
| **plume ingestion** | the upper card drawing part of its intake straight from the exhaust jet of a flow-through card below it (§6.3) |
| **rear exhaust shroud** | a shroud over the rear PCIe/I/O bracket area outside the case: a **shared exhaust plenum** over every bracket outlet, with its own fans pulling suction. Stefano's has 2× Noctua NF-A14 industrialPPC-3000 PWM |
| **passive rear duct** | the same shroud without fans. An option, not a sweep factor |
| **case pressure** | static pressure of the case interior relative to ambient |
| **face** | one of Front / Top / Rear / Bottom / Side; the UI's left bar selects one face (or Internals, or GPUs) |
| **mount** | a fan/radiator position on a face |
| **interface** | any opening between the case interior and ambient (panel mesh, filter, slot mouths, seams) |
| **seal level** | 5-step open-area setting of an interface, **1 = fully open … 5 = sealed** (§5; reversed from rev 3) |
| **slot gap state** | what occupies the space next to a card's fan face (§6) |
| **Stock / Custom Accelerated** | the two named GPU fan curves (§1.1) |
| **stock** (sweep row) | the baseline configuration defined in §3 |

---

## 1. Hardware

### 1.1 GPUs

Card definition fields: power (W) and power limit, slot width, dimensions, **cooler type** (`blower` |
`flow_through`), fan P–Q (free-air flow, dead-head pressure, RPM), heatsink proxies (fin area, hydraulic
diameter, fin-channel loss k), TIM, die→heatsink and memory→heatsink resistances, memory power share,
throttle flag (default 88 °C) and cutoff, inlet faces and split, flow-through exhaust geometry (width of the
flow-through region, backplate cutout area), bracket vent area. Each value carries a `source:` or
`approximate: true` + `assumption:`. Per-card-type calibration numbers live in `gpusim/calib.py` `CARD`.

| Card (id) | Cooler | TBP | Slots | L × H × T mm | Sources |
|---|---|---:|---:|---|---|
| RTX PRO 6000 Blackwell **Max-Q** (`rtx-pro-6000-blackwell-maxq`) — primary | blower | 300 W | 2 | 266.7 × 111.15 × 37 | NVIDIA datasheet, ELSA drawing |
| RTX PRO 6000 Blackwell **Workstation Edition** (`rtx-pro-6000-blackwell-workstation`) | flow-through, 2 axial fans ("Double-flow-through") | 600 W | 2 | 304 × 137 × 40 | NVIDIA datasheet; StorageReview (dims); Puget (two-fan, same housing as 5090 FE); AEC Magazine (intake beneath, vent out the top) |
| GeForce **RTX 5090 Founders Edition** (`rtx-5090-fe`) | flow-through ("double flow through") | 575 W | 2 | 304 × 137 × 40 (T approximate) | NVIDIA product page (575 W, 2-slot, 90 °C max); Gamers Nexus (≈72 °C, ≈1570 RPM); Tom's Hardware (≈80 °C) |
| GeForce **RTX 3090 Founders Edition** (`rtx-3090-fe`) | hybrid flow-through: PCB-side fan pushes out the bracket, rear fan pulls up through the fins | 350 W | 3 | 313 × 138 × 58 (T approximate) | NVIDIA product page (350 W, 3-slot, 93 °C max); Tom's Hardware cooler teardown and review (≈65 °C, ≈1100 RPM); Legit Reviews (≈67 °C, ≈1175 RPM) |
| **custom-blower-300w** | blower template | 300 W | 2 | as Max-Q | template, labelled as such |

Flow-through cards were **not** used to move the Max-Q anchors. Their blocks are set only against a
single-card open-air review temperature (§10). PRO 6000 Workstation and 5090 FE share every cooler number
(same housing); no sustained-load PRO 6000 Workstation review temperature was found, so its open-air
result (≈76 °C at 600 W) follows from the 5090 FE fit.

**GPU fan curves** — per card, part of the flow ⇄ thermal iteration. Duty is a fraction of max fan RPM; fan
P–Q scales by affinity laws (Q ∝ N, P ∝ N²). No RPM floor: 0 % duty stops the fan.

- `stock`: per card (card YAML). Max-Q: rises with die temperature but **caps near 70 % duty even at
  88–90 °C** (Stefano's observation). Flow-through cards: approximate curves pinned to the review RPM at the
  review temperature (5090 FE ≈ 52 % of an assumed 3000 RPM near 75 °C; 3090 FE ≈ 38 % near 66 °C).
- `custom_accelerated` ("Custom Accelerated"): **off (0 %) at 25 °C, linear to 100 % at 70 °C**, held at
  100 % above. Global (`calib.GLOBAL_FAN_CURVES`), same for every card. It **replaces rev 3's
  `maxq_aggressive`**, which is accepted as an alias everywhere (YAML, API, CLI). The rev 3 aggressive
  calibration target (one Max-Q in open air < ~75 °C) was re-checked: 73.44 °C, unchanged.
- `custom`: user temperature → duty points.

Adjustable initial conditions (labelled "approximation"): power limit, memory clock offset, undervolt, core
clock offset, mapped to heat by the documented rough split in `gpusim/physics.py` (unchanged from rev 3).

### 1.2 Stefano's own build (default configuration)

Unchanged from rev 3: Fractal Meshify 2 XL (9 horizontal + 3 vertical slots, all brackets removed, low
internal resistance), 3× Noctua 140 mm redux-1700 front intake, 1× redux-1700 rear exhaust (assumed),
Arctic Liquid Freezer III 360 top exhaust with its three P12s, CPU **water-cooled** at 150 W (approximate),
4× RTX PRO 6000 Blackwell Max-Q in slots 1/4/7 + vertical v2, custom rear shroud with 2× NF-A14 iPPC-3000,
stock GPU curve, 25 °C. Build id `meshify2xl-stefano`.

---

## 2. Data files (all presets are data, not code)

`presets/{cards,fans,radiators,cases,builds,scenarios}/*.yaml`, validated by pydantic. Every numeric value
has a `source:` URL/citation or `approximate: true` with an `assumption:`; the loader rejects a bare number.

### 2.1 Case presets

Required cases (rev 3 list) with these rev 4 changes:

- **Corsair 9000D RGB AIRFLOW**: Corsair lists **"Included Fans: No Fans Included"**. The front supports
  8×120 / 3×140 / 2×200; rev 4 models the front as the **8×120 array, 4 high × 2 wide** (Corsair: "dual
  480mm radiators side-by-side"), the top as one row of 4×120, side 3×120, rear 1×140. Mount coordinates
  are a non-overlapping grid. The 9000D **template** populates the front array with 8× Corsair iCUE AF120
  RGB ELITE (65.57 CFM, 2.68 mmH₂O, 2100 RPM, Corsair spec page) as intake — an assumption, stated on the
  build. The two extra vertical slots are, per Corsair, for a secondary motherboard; they are used as
  vertical GPU positions for convenience.
- **Meshify 2 XL**: rear mount moved above the slot area (schematic coordinate).
- **Phanteks Enthoo Elite Server**: 12 slots, 582 × 261 × 721 mm read as H × W × D; one rear 140 modelled
  (only one fits above the 12-slot bracket area in the schematic); midplate fans spread.
- Generic ATX / mATX / E-ATX: rear mounts moved above the slot area.
- **Mike Bradley's Dengen X Station** (rev 4.1; rev 4 had an illustrative 9000D mock here): his published
  build, used with his permission: Corsair 9000D, 4× RTX PRO 6000 Workstation touching at 275 W, 8×120 front
  intake, 4×120 top and 2×120 rear exhaust, air-cooled Threadripper PRO (top cooler fan only), no side fans,
  no shroud, no radiator. Calibration anchor C (§16).

### 2.2 Fan library

Rev 3 list plus **Corsair iCUE AF120 RGB ELITE** (Corsair spec page; curve between the published
intercepts is the generic quadratic, flagged approximate).

### 2.3 Radiators

Radiator = quadratic core loss scaled by thickness/38 mm and FPI/18, fans in series, allowed on the
**front, top or bottom** face (legacy rear/side builds still load). Front radiator breathes the front
intake volume (the GPU zone on direct-front-to-GPU cases), bottom the GPU zone, top the main case volume.
With a water-cooled CPU the CPU heat rides this air stream; with an air-cooled CPU a present radiator is a
passive core with fans and no heat.

---

## 3. Factorial sweep: 2^4 = 16 cells + stock baseline (on Stefano's default build)

| Factor | Level A | Level B |
|---|---|---|
| **spacing** | `stacked`: 3 horizontal cards in adjacent dual-slot positions | `gap1`: one empty slot between horizontal cards |
| **pressure** | `high`: all case fans and the radiator intake | `standard`: front/bottom/side intake, top/rear/radiator exhaust |
| **shroud** | `off` | `on` (2× NF-A14 iPPC-3000) |
| **leakage** | `sealed` — seal levels **4–5** (front 4, top 4, bottom 5, side 5, seams 5, rear slots 5) | `leaky` — realistic stock, levels **3–5** (front 3, top 3, bottom 4, side 5 glass, seams 4, rear slots 3) |

Rear slots `leaky` = level 3 (45 %): brackets are removed, but roughly half of the slot openings sit behind
the cards' own brackets. The 4th card stays in vertical slot v2 in all cells. Stock row: stacked, standard,
shroud off, leaky, stock GPU curve. The open-air single-card reference is reported for calibration.

**Ranking (rev 4).** Configurations that do not throttle come first, ordered by hottest die then mean die.
Configurations that throttle follow, ordered by **unthrottled** hottest die: their throttled dies all sit on
the cutoff, so that column cannot separate them. The same rule is used by the sweep, the CLI and the API.

---

## 4. Flow network

Nodes (gauge pressure, ambient = 0): main case volume, GPU zone, each card's inlet and exhaust region, rear
plume (shroud off) or shroud plenum (on/passive), and **CPU cooler outlet** (air-cooled CPU only).
Branches are sign-aware `ΔP = k·Q·|Q| + k_lin·Q − P_fan(Q)`; k from orifice relations
`k = ρ / (2 C_d² A²)` (Idelchik-style). Fans and GPU fans are pressure sources scaled by affinity laws.
Damped Newton with an analytic Jacobian; fails loudly on non-convergence; mass conserved at every node.

Rev 4 branches:

- **Flow-through card**: fan-face inlet slit(s) (GPU zone → card inlet), axial fans + fin channel
  (inlet → exhaust), **up-exit** (exhaust → main case volume) with area `min(exit_width × gap_above,
  backplate cutout)`, and the bracket vent (exhaust → plume/plenum). The bracket share follows from the
  areas: ≈ 7–8 % for PRO 6000 WS / 5090 FE, ≈ 22 % for the 3090 FE. The jet rises into the upper case
  volume, not back into the GPU zone the cards breathe from; what the card above swallows is the plume
  overlay (§6.3). No blower short-circuit branch on flow-through cards.
- **Air-cooled CPU**: `case → cpu` = tower fan (default generic 140, count, duty) in series with the fin
  stack (`cpu_heatsink_k = 2.5e4 Pa/(m³/s)²`, ≈ 20 Pa at 60 CFM, approximate); `cpu → case` = cooler outlet
  spreading back into the case (`cpu_exit_area = 0.03 m²` × internal k multiplier); the **rear mount pulls
  from the cooler outlet**. The CPU heat is added on the cooler branch, so it enters the case air.
- **Water-cooled CPU**: heat on the radiator branch (rev 3 behaviour). Water-cooled with no radiator is a
  loud error.
- **Sealed interfaces (level 5)** have no branch (infinite resistance) and are still reported, with k = ∞.
- Blower cards, shroud, recirculation, rear-slot reingestion, adjacent-card preheating, altitude and
  optional buoyancy: unchanged from rev 3.

## 5. Interfaces and seal levels (reversed in rev 4)

Every interface (front/top/bottom/side panels, seams, rear slot mouths) has a seal level. The level sets
the open-area fraction of the interface's geometric area (case preset) and a discharge coefficient:

| Level | Name | Open area | C_d | Typical |
|---|---|---:|---:|---|
| 1 | fully open | 100 % | 0.80 | panel removed, no filter |
| 2 | open grille / missing covers | 70 % | 0.72 | coarse bare mesh, slot covers out |
| 3 | typical mesh + filter | 45 % | 0.65 | stock mesh front/top with dust filter |
| 4 | restricted | 5 % | 0.62 | solid panel seams, small gaps, taped mesh with gaps |
| 5 | sealed | 0 % | — | solid tempered glass or metal, taped; **no branch, R = ∞** |

**Default side seal is 5** (solid glass/metal). Side panel `mesh` caps the side at 3; `removed` forces 1.
Defaults when a build omits an interface: front 3, top 3, bottom 4, side 5, seams 4, rear slots 3.
**Migration from rev 3** (1 was sealed): rev 3 levels 1/2/3/4/5 map to rev 4 levels 5/4/4/3/1, except the
glass side (rev 3 level 2 → rev 4 level 5, its edge gaps now counted under seams). Every preset, the
factorial, the tests and the docs use the rev 4 direction. The percentages are assumptions; Monte Carlo
scales every seal area ±20 % (lognormal σ 0.20). Dust filter density per intake: none / fine / dense.

## 6. GPU layout and inter-card airflow (critical)

### 6.1 Slot map and gaps (unchanged)

Explicit slot map (horizontal + vertical). Fan face points down. For every card: fan side = card below,
empty slots, or `psu_shroud_clearance_mm`; backplate side = card above or CPU-area clearance; vertical
cards use `vertical_inlet_gap_mm`. Adjacent dual-slot Max-Q: ≈ 3.6 mm; one empty slot ≈ 24 mm. Slot gap
states `open_slot` / `blocked_slot` / `no_slot`, inlet resistance k(gap) rising steeply as gap → 0. No
special lowest-card bypass.

### 6.2 Blower cards

Unchanged: backplate/shroud heat is partly captured by the inlet that breathes that gap
(`capture_g0_mm = 9`).

### 6.3 Plume ingestion between stacked cards (new, item 12)

A flow-through card exhausts **up** through its backplate into the gap above it, which is the fan face of
the card above. A resistor alone cannot represent this: in a network the upper card's inlet node would mix
the jet with all the zone air at the zone temperature. Rev 4 adds an explicit coupling term:

- The upper card draws a fraction **φ(g)** of its **fan-side intake mass** straight from the lower card's
  exhaust jet instead of the GPU zone:
  `φ(g) = φ_max · exp(−g / L_plume)`, `φ_max = 0.85`, `L_plume = 40 mm` (global, approximate), g = the air
  gap between the two cards. One empty slot (≈ 21 mm) → φ ≈ 0.50; two (≈ 41 mm) → 0.30; three
  (≈ 62 mm) → 0.18.
- Ingested mass `ṁ_ing = min(φ · ṁ_inlet,fan(upper), 0.98 · ṁ_up-exit(lower))` — never more than the jet.
- **Mass and energy:** the overlay reroutes `ṁ_ing` in the thermal advection balance: jet → upper inlet,
  removed from the jet's stream into the case and from the zone's stream into the upper inlet, and the
  displaced zone air is sent where the jet share would have gone. Every node still balances (reported as
  `advection_residual_kg_s`, ~1e-8 kg/s); total enthalpy out equals heat in (energy error ~1e-6).
- Applies whenever the lower card is flow-through and a horizontal card sits directly above it (whatever
  the upper card's cooler). Vertical cards have no card above. Monte Carlo varies φ_max uniform 0.70–0.95
  and L_plume lognormal σ 0.25.

Behaviour (Meshify, two cards, shroud off, stock curve, unthrottled):

| Cards | Empty slots (gap) | Upper °C | Lower °C | Δ | Δ without the plume term |
|---|---|---:|---:|---:|---:|
| 2× RTX 5090 FE | 1 (21.0 mm) | 90.2 | 82.3 | +7.9 | +0.8 |
| | 2 (41.3 mm) | 83.8 | 78.9 | +4.9 | +0.7 |
| | 3 (61.6 mm) | 81.5 | 77.9 | +3.6 | +0.5 |
| 2× PRO 6000 Workstation | 1 / 2 / 3 | 91.2 / 84.6 / 82.7 | 83.2 / 79.9 / 78.9 | +8.0 / +4.8 / +3.7 | +0.8 / +0.7 / +0.6 |
| 2× RTX 3090 FE | 1 / 2 / 3 | 81.1 / 75.9 / 73.8 | 74.2 / 70.7 / 69.7 | +6.8 / +5.2 / +4.1 | −0.3 / +1.2 / +1.6 |

Touching dual-slot flow-through cards (0.6 mm) have no steady state at full power (unthrottled runaway,
flagged in the notes as not physical); the throttled equilibrium is reported. Tests
(`tests/test_plume.py`) check upper > lower, Δ shrinking with spacing, the jet cap, node balance and
energy balance.

## 7. Internal obstructions and other factors

- **Obstruction** `low / medium / high` and **cable management** `clean / cluttered` are **k multipliers** on
  the internal branches (GPU zone → main case, CPU cooler outlet → case): obstruction ×1.0 / ×2.5 / ×6.0,
  cables ×1.0 / ×2.0 (multiplied together). Cluttered cables also multiply every card inlet slit's k by
  1.35 (bundles lying across the fans). All approximate, in `gpusim/calib.py`. Anchors use low/clean
  (×1), so they do not move.
- **CPU** (Internals panel): power (W) and air vs water (§4).
- PSU (shrouded / open, fan up / down), drive cage, dust filters, radiator thickness/FPI/position, bracket
  vent area, ambient, altitude, per-card power limit, side panel, room re-ingestion offset, buoyancy:
  unchanged from rev 3.

## 8. Thermal network (per card)

Die, memory, heatsink, air stream. Die→heatsink `R_tim`, memory→heatsink `R_mem`; heatsink→air
`R_conv = 1 / (ε ṁ c_p)` with ε-NTU and `Nu = C Re^m Pr^(1/3)`; parallel shroud/backplate path `R_ext` to
the GPU zone. Air temperatures from an upwind advection balance on the solved flow field **plus the plume
overlay** (§6.3). Flow ⇄ thermal iterate to convergence (duty from the fan curve, density from
temperature). Each card's chain is reported (`thermal` block): zone air, inlet (with plume share and
captured heat), ṁ, ε, R_conv, heatsink, R_tim, die, memory, so that
`T_die = T_in + Q_channel · R_conv + P_die · R_tim` can be shown with numbers.

**Throttle**: die ≥ throttle flag (88 °C default) → `throttle = True`; above the cutoff (90 °C Max-Q /
5090 / PRO 6000 WS, 93 °C 3090) power is reduced to the throttled equilibrium. Rev 4 scales each limit by
`(cutoff − T_in) / (T_die − T_in)` (die rise over inlet is near-linear in power), up to 10 passes, and lets
overshot cards back up. Both unthrottled and throttled results are reported; unthrottled > 150 °C is
flagged as a non-physical runaway.

## 9. Outputs per configuration/cell

Per-card die (throttled and unthrottled), memory, inlet, exhaust, mass and volumetric flow, fan duty,
power, throttle flag, cooler, fan curve, thermal chain; case pressure; plume transfers; solver residuals;
advection residual; energy balance error; notes. Ranking rule in §3.

## 10. Calibration & honesty

Only global or per-card-type parameters; never per-cell. Checked by `gpusim/bounds.py`, written to
`results/<build>/bounds_check.{json,md}` on every sweep, and asserted in pytest:

| Check | Target | Rev 3 | Rev 4 | Δ |
|---|---|---:|---:|---:|
| Max-Q, open air, 300 W, stock | 75–85 °C (~83) | 82.81 | 82.81 | 0.00 |
| Anchor A (gap1 + vertical, shroud off, standard, leaky, stock) | 86 ± 3 °C | 86.52 | 86.58 | +0.06 |
| Anchor B (4 close-packed, stock) unthrottled, top → bottom | ≥ 90 hottest, throttle, middle hottest | 100.7 / 108.9 / 108.7 / 87.1 | 100.8 / 109.0 / 108.8 / 87.2 | +0.1 each |
| Max-Q, open air, Custom Accelerated (was maxq_aggressive) | < ~75 °C (~73) | 73.44 | 73.44 | 0.00 |
| Best Meshify cell (gap1, standard, shroud on, leaky) | — | 84.3 | 84.20 | −0.1 |
| Custom Accelerated on the best cell | — | 75.5 | 75.43 | −0.07 |
| RTX 5090 FE, open air, 575 W, stock | ~76 ± 5 °C (reviews) | — | 75.91 | new |
| RTX PRO 6000 Workstation, open air, 600 W, stock | ~76 ± 5 °C (5090 FE fit) | — | 76.35 | new |
| RTX 3090 FE, open air, 350 W, stock | ~68 ± 5 °C (reviews) | — | 68.04 | new |

The small anchor moves come from the seal re-map (§5), not from a retune; no global knob was changed for
the Max-Q. Monte Carlo (N = 200, seed 12345) now also varies the plume term; bands in `docs/CALIBRATION.md`.
**Typical accuracy ±5–10 °C absolute; better for ranking configurations than for absolute temperatures.**
Method citations as rev 3 (Ellison; Idelchik; flow-network modelling for electronics cooling), no invented
page numbers.

## 11. Visualizer (primary deliverable, designed for OBS live streaming)

`uv run gpusim ui` (FastAPI + three.js r160, vendored ES module). Binds 8000, or the next free port within
+29. Static files are served with `Cache-Control: no-cache`. Rev 4 layout at 1920 × 1080:

- **Header**: build name, mock banner, hottest die, case pressure, ambient; camera (¾ front, side, ¾ rear);
  view mode (Case / Split / Network); Optimize, °F, Compare, Demo, Present.
- **Left driving bar** (item 8): **Front / Top / Rear / Bottom / Side / Internals / GPUs**. Selecting a face
  opens only that face's panel: its mounts (fan model from the size-filtered top-10, direction, speed; a
  "Set all" row), seal level with the level's meaning, dust filter, radiator (front/top/bottom), and on Rear
  the brackets and the shroud. Internals: case, CPU (W, air/water, tower fan), obstruction, cables, drive
  cage, PSU, seams, ambient, altitude, re-ingestion, buoyancy. GPUs: card picker (blower / flow-through
  groups), slot, power limit, **Stock / Custom Accelerated / Custom** curve, clock and voltage
  approximations, spacing buttons.
- **3D case** (items 1–4): fans are discs lying in the plane of their face with a direction cone, so the ¾
  camera shows them as ovals on the front, top, rear, bottom or glass side; blue intake, red exhaust, grey
  blanked. Cards sit with the bracket at the rear wall and the PCB edge off the motherboard tray, coloured
  by die °C, with their own fan discs on the fan face and a plume cone on flow-through cards. PSU
  bottom-rear under its shroud. Motherboard, CPU tower or AIO pump. Radiator slab against its panel with
  its fans on its inner face. Rear shroud with its fans outside the rear wall.
- **Face inset** (item 5): head-on drawing of the selected face, auto-scaled so every fan is visible
  without overlap (the 9000D's 8×120 front grid included). Labels collapse identical fans on one face
  ("Front fans ×8: all Corsair iCUE AF120 RGB ELITE · 65.6 CFM · 2.68 mmH₂O · intake").
- **Network view** (item 6): alongside the case (Split) or full screen. Layer 1 airflow network — pressure
  = voltage, flow = current — with labelled seal resistances (∞ for solid glass/metal), fan impedances,
  inter-card slot resistances, fin channels, bracket vents, internal resistances, shroud and plume
  branches, node pressures and temperatures. Layer 2 thermal network per card — zone air → inlet mixing
  (plume share) → R_conv → heatsink → R_tim → die, R_ext and R_mem — with
  `T_die = T_in + Q_ch·R_conv + P_die·R_tim` evaluated in numbers. Parallel identical branches collapse
  (×n) with members in the tooltip.
- **Tooltips everywhere** (item 7): every input, legend item, header control and network element has a
  hover text stating its assumption (seal meaning and %, filter k, fan laws, curves, CPU air/water,
  obstruction/cable multipliers, PSU, shroud, card types, slot gaps, clocks, plume term).
- **Readout**: per card die (throttled), unthrottled, memory, inlet, exhaust, CFM, duty, power, gap, plume
  share; energy balance and residual; notes.
- **Start screen** (item 15): Quick start (Meshify 2 XL — Stefano; Corsair 9000D Airflow), **Start from a
  template** (9000D Airflow, Meshify 2 XL, generic ATX / mATX / E-ATX, Phanteks Enthoo Elite Server),
  Build from scratch (any case). Mike Bradley mock as a shareable demo URL **`/?demo=mike-bradley`**,
  labelled "Illustrative mock — not a measurement or claim about anyone's real build." Other URL params:
  `?template=<build id>`, `?start=meshify|9000|mock`, `?demo=stefano`, `?net=split|full`, `?face=…`,
  `?view=front34|side|rear34`, `?present=1`.
- Compare, Demo (arrow keys, auto-advance), Presentation mode, drag fans between mounts and cards between
  slots, Optimal air-cooled search: kept from rev 3. The Stefano demo gains a flow-through step
  (same slots, 4× PRO 6000 Workstation).

## 12. Other deliverables

- CLI: `sweep`, `run`, `optimize`, `schematic`, `calibrate`, `ui` (rev 3), plus **`simulate SPEC.json`**,
  **`rank REQUEST.json`** (variants or a factorial), **`schema`** (exports `docs/openapi.json` and
  `docs/simspec.schema.json`).
- **Agent API** (item 14), FastAPI, docs at `/docs`:
  - `POST /api/v1/simulate` — `SimSpec {build, extra_fans?, extra_cards?, options{throttle, mc, seed,
    detail}}` → summary, per-card rows, plume, notes, accuracy; `detail = "full"` adds the thermal chains
    and the network; `mc > 0` adds 5th–95th bands.
  - `POST /api/v1/rank` — `{base, variants[{name, patch (RFC 7396 merge patch), set (macros / dotted
    paths)}], include_base}` → ranked results; a failing variant reports its error in place.
  - `POST /api/v1/sweep` — `{base, factors{name: [levels]}}` → full factorial (≤ 256 cells), ranked.
    Macros: spacing (stacked|gap1|gap2|gap3), pressure, shroud, leakage, fan_curve, cpu_cooling,
    obstruction, cables; anything else is a dotted path (`gpus.*.power_limit_w`, `shroud.count`).
  - `GET /api/v1/presets`, `GET /api/v1/builds/{id}`, `GET /api/v1/schema`.
  - Inline fans (intercepts or P–Q points) and inline cards (`calibration_from` a calibrated card type,
    optional overrides). Validation errors (unknown ids, overlapping slots, cards past the last slot) are
    HTTP 422 with a reason.
  - Examples: `examples/api/*.json`, `examples/api_client.py` (stdlib HTTP, or `--offline`). README
    section with curl and Python.
- Plots, HYPOTHESIS.md, README, DEMO.md, docs/CALIBRATION.md as rev 3, updated for rev 4. The sweep for
  `meshify2xl-stefano` is rerun and `results/` and `plots/` committed. `pytest -q` green.

## 13. Engineering notes

Physically plausible, documented parameters; rankings emerge from physics (flow split, recirculation,
preheating, starvation, plume ingestion), never per-configuration offsets. Deterministic by default.
Solve time < 0.5 s per configuration without MC; the Meshify sweep with MC 200 runs in about 50 s.

## 14. Resolved questions and rev 4 decisions

Rev 3 answers stand (Noctua 140 redux-1700 case fans; Arctic 360 top exhaust; Enthoo Elite Server 12
slots; Meshify 9 + 3 slots, brackets removed; rear shroud 2× NF-A14 iPPC-3000; 25 °C; anchors A and B).
Rev 4 decisions made without further questions, all documented as assumptions:

- 9000D ships with no fans (Corsair); the template fills the 8×120 front with AF120 RGB ELITE.
- Flow-through exhaust rises into the main case volume; the card above swallows φ(g) of it.
- φ_max 0.85, L_plume 40 mm; CPU tower 2.5e4 Pa/(m³/s)²; obstruction ×1 / 2.5 / 6; cables ×1 / 2.
- Seal percentages 100 / 70 / 45 / 5 / 0; leaky rear slots at 3.
- 5090 FE and 3090 FE thicknesses and every flow-through fan/fin number are approximate.
- Ranking puts non-throttling configurations first; throttling ones by unthrottled die.

## 15. Rev 4 item map

| Item | Where |
|---|---|
| 1 fans on faces | §11 3D case |
| 2 GPUs at the rear | §11 3D case |
| 3 PSU | §11 3D case |
| 4 radiator on its fans | §2.3, §11 |
| 5 9000D fan array, auto-sized face, collapsed labels | §2.1, §11 face inset |
| 6 resistor-network view, two layers, math | §11 network view, §8 |
| 7 tooltips | §11 |
| 8 left driving bar | §11 |
| 9 seal levels 1 open … 5 sealed | §5 |
| 10 CPU air / water | §4, §7 |
| 11 GPU picker, Stock / Custom Accelerated | §1.1 |
| 12 plume ingestion | §6.3 |
| 13 obstruction / cables k multipliers | §7 |
| 14 agent API | §12 |
| 15 quick start, templates, mock demo URL | §2.1, §11 |
| 16 airflow-first scope | scope paragraph, §2.3 |

---

## 16. Revision 4.1 (review feedback, 2026-09-28)

**Physics.**
- **Series duct between stacked flow-through cards.** A resistor from the zone into a 0.6 mm slit made
  touching flow-through cards starve and run away (> 290 °C). In reality the lower card's backplate cutout
  breathes straight into the fans above, so a touching stack is fans in series. New branch
  `stack-<lower>-<upper>`: `cex(lower) → cin(upper)`, area `cutout · exp(−gap / 8 mm)`, lumped
  `C_d = 0.25` (cutout, fin exit, fan hub). It fades out as the gap opens; the plume overlay (§6.3) still
  handles the mixing at larger gaps. Global knobs `stack_length_mm`, `stack_cd`.
- **Calibration anchor C — Mike Bradley's "Dengen X Station"** (public posts, used with his permission):
  4× RTX PRO 6000 Workstation, touching (slots 1/3/5/7 — the only fit on a 7-slot WRX90E-SAGE SE),
  275 W caps, unified GPU fans. Published: bottom 49 °C / top 79 °C at ~80 % fans, 49 / 69 °C at 100 %.
  Model: 46.7 → 78.1 °C and 44.6 → 69.4 °C, rising card by card. Check: top ± 5 °C, bottom ± 6 °C (his
  room temperature is not published), monotonic rise. `stack_cd` was fit to it; nothing else moved.
- **Case pressure and fan flow** (question from review): every case fan is a pressure source on its P–Q
  curve in series with its mount, and the case volume and GPU zone are pressure nodes, so a sealed or
  pressurised case moves less air per fan (Meshify front trio: 143–179 CFM across the seal settings). The
  seal slider is the panel *around* the fans; it does not block the fans. For blower cards the case air
  barely matters as long as intake exceeds the cards' own ~100 CFM: removing every case fan raises the
  hottest Max-Q by only ~5 °C, because the blowers ventilate the case themselves.

**Data.** Faces can offer alternative fan patterns (`MountLayout.pattern`, `BuildCfg.patterns`): Meshify
front/top 3×140 or 4×120, 9000D front 8×120 or 3×140, top 4×120 or 3×140. The Mike Bradley preset is his
published build (not the rev 4 Max-Q mock). Scenario steps can pin `fan_duty` and `power_limit_w`.

**UI.** Start screen is a funnel: two quick starts (Mike Bradley's Dengen X Station, Stefano's Meshify 2 XL),
templates and scratch behind "More". Left bar starts with **Case**. Each face shows one fan picker with 140
mm / 120 mm option groups (picking the other size swaps the pattern), plus "set fans one by one", seal and
filter behind expanders. "Blanked" is "cover plate (plugged)". No text over the 3D view: stats sit in the
right column (hottest GPU, case pressure, fresh air, heat, then GPU 1…n with vertical cards last and
labelled); objects explain themselves on hover. The view is mirrored so the front is on the right as seen
through the glass, the motherboard is an ASUS Pro WS WRX90E-SAGE SE layout (EEB, sTR5, 8 DIMM, 7 PCIe
x16), cards sit on its slot positions (slot 1 ≈ 158 mm below the board top), and vertical cards stand in
their own positions next to the glass.

### 16.1 Plume share derived from the solved flows (rev 4.1, second pass)

The rev 4 plume share `φ = 0.85·exp(−gap/40 mm)` was a fixed function of the gap. It is replaced by a
calculation from the flows the network already solves (`thermal.plume_transfers`):

- jet speed `V_j = Q_up-exit / A_cutout` (lower card's exhaust through its backplate cutout);
- crossflow `U_c = Q_fresh-into-GPU-zone / A_sweep`, `A_sweep` = case width × (slot stack height + 60 mm);
- swept share `s = min(1, U_c·g / (V_j·L_f))`: how far the crossflow pushes the jet while it crosses the
  gap `g`, relative to the fan region length `L_f`;
- entrainment `e = α·P·g / A_cutout`, `α = 0.08` (free-jet entrainment coefficient, Morton–Taylor–Turner
  order), `P` the jet perimeter;
- `ṁ_ing = min(ṁ_in, ṁ_jet·(1 − s)·(1 + e)) / (1 + e)`, capped at 98 % of the jet; `φ = ṁ_ing / ṁ_in`.

Result: in a normal case the crossflow (≈ 1.1 m/s in the Meshify) is about as fast as the jet (1.3–1.7 m/s),
and over 2–6 cm it sweeps only 9–18 % of the jet away while entrainment dilutes it 8–23 %. Two 5090 FE
cards: φ ≈ 0.62 / 0.66 / 0.64 at 1 / 2 / 3 empty slots, upper − lower +10.4 / +9.8 / +9.7 °C (+1.8 / +0.8 /
+0.5 without the plume). Stagnant case (front fans removed) → φ 0.65–0.72; 3× iPPC-3000 front → 0.54–0.59.
Getting φ near 5 % at three slots would need ≈ 5.7 m/s of crossflow, or a baffle. So spacing flow-through
cards helps mostly by giving each card a bigger inlet, not by diluting the plume; for the 3090 FE the
upper − lower difference even grows slightly with spacing (+6.2 → +7.9 °C) while both cards get cooler.
Monte Carlo varies `α` (lognormal σ 0.35) and the crossflow scale (σ 0.30). Anchor C is unchanged (top
78.0 / 69.3 °C). The rev 4 "upper − lower shrinks with spacing" test is replaced by "φ falls as the case
crossflow rises", which is what the physics actually implies.

### 16.2 Assumption audit (rev 4.1)

| Where | Was | Now |
|---|---|---|
| `layout._pair_gap` | Slot covers installed made the gap *between two cards* a `blocked_slot` (inlet area × 0.22) | Covers close the rear wall, not the inter-card gap; the fan breathes the gap from the front and glass side. `blocked_slot` only via an explicit `gap_override` (e.g. cables). |
| `network.seal_level` | Slot covers had no effect on the rear slot openings | Covers installed → rear slot openings at seal level 4 or tighter. |
| `network` PSU | `psu_fan` input and `psu_fan_up_k_mult` were never used | Fan up = exhaust from the GPU zone out the rear (generic 140 mm at 50 %, × 1.45 through the shroud cut-outs); fan down = outside air, no branch. |
| Text: tooltip, demo, hypothesis, calib comment | "Open slots re-ingest the hot plume" stated unconditionally | The solver already sets that flow by pressure (−2.5 Pa: 5.9 CFM in; +7.7 Pa: 7.6 CFM out). Text now says re-ingestion only happens below room pressure. |
| `thermal` plume | Fixed φ(gap) | Derived from flows (§16.1). |
| `network._add_cpu_cooler` | A two-fan tower was two fans side by side (flow doubled) | Push-pull fans share one fin stack in series: same flow, pressure doubled. `cpu.cooler_fans` = both (stock default) / top / bottom. |
| CPU cooler direction | Tower always blew front → rear into the rear fan; drawn blowing forward | `cpu.cooler_airflow` = up (default: sTR5 / SP6 towers on WRX90 run bottom → top; the rear-half top fans and the rear fan draw from the cooler outlet) or rear. Drawn with amber internal fans flat above / below the stack. Mike Bradley's build: top fan only (per Stefano, the bottom fan crowds GPU 1). |

Known simplifications that remain, documented rather than changed: the GPU zone is one well-mixed air
volume (no vertical stratification, so an upper card does not see warmer zone air unless the plume or a
backplate hands it heat); `R_ext` (shroud/backplate to air) is a constant, not a function of the local air
speed; backplate heat captured by a neighbour's inlet depends on the gap only; the blower bracket
short-circuit always flows outward-to-zone because a blower outlet (~80 Pa) is far above any case pressure;
buoyancy is a small optional bias.
