# Calibration

Three anchors for the Max-Q, one open-air review target for each flow-through card, one set of global
and per-card-type parameters, no per-cell offsets. The numbers live in `gpusim/calib.py`. Card geometry
that NVIDIA, ELSA or a review publishes stays in `presets/cards/`. Inlet orientation is a card-preset
field and is not refit per sweep cell.

## Rev 4 against rev 3

No global knob and no Max-Q number was retuned for rev 4. The small moves come from the seal re-map
(1 = open … 5 = sealed, with concrete open-area percentages) and the throttle search.

| Check | Target | Rev 3 | Rev 4 | Δ |
|---|---|---:|---:|---:|
| Max-Q, open air, 300 W, stock | 75–85 °C (~83) | 82.81 | **82.81** | 0.00 |
| Anchor A (gap1 + vertical, shroud off, standard, leaky) | 86 ± 3 °C | 86.52 | **86.58** | +0.06 |
| Anchor B unthrottled, top → bottom | hottest ≥ 90, throttle, middle hottest | 100.7 / 108.9 / 108.7 / 87.1 | **100.8 / 109.0 / 108.8 / 87.2** | +0.1 each |
| Anchor B throttled equilibrium | at the 90 °C cutoff | ~90.1 | 89.6 | −0.5 |
| Max-Q open air, Custom Accelerated (rev 3 `maxq_aggressive`) | < ~75 °C (~73) | 73.44 | **73.44** | 0.00 |
| Best Meshify cell (gap1, standard, shroud on, leaky) | — | 84.3 | **84.20** | −0.1 |
| Custom Accelerated on that cell | — | 75.5 | **75.43** | −0.07 |

The throttled equilibrium now lands 0.3–0.5 °C under the cutoff instead of 0–0.2 °C over it, because
the rev 4 search scales power by the die rise over inlet air and stops inside a 1.25 °C window.

Custom Accelerated is 0 % duty at 25 °C and 100 % at 70 °C, linear. Rev 3's aggressive curve was
100 % at 70 °C with a 35 % floor. Both sit at 100 % at the ~73 °C equilibrium, so the open-air result
is identical. The blower RPM floor (1200 RPM) was removed so 0 % really is off; no stock curve reaches
that low, so the anchors are unaffected.

## Inlet geometry (unchanged)

In a standard ATX tower the fan face points down, toward the case floor. Each card preset sets
`inlet_faces` (`floor`, `cpu`, or `both`) and `inlet_split`. The Max-Q and the custom blower use `both`
/ 0.75 (approximate). Flow-through cards use `floor` / 1.0: both axial fans are on the fan face.

The gap on each face comes from the slot map, for every card: fan side = next card below, empty slots,
or `psu_shroud_clearance_mm` (Meshify 40 mm, approximate); backplate side = next card above or
`clearance_above_top_mm`; vertical cards `vertical_inlet_gap_mm` (Meshify 28 mm). An open PSU bay
multiplies the floor clearance by 1.8. A dual-slot 37 mm card on a 20.32 mm pitch leaves 3.6 mm; the
40 mm flow-through cards leave 0.6 mm; one empty slot adds 20.32 mm.

## What was fit for the Max-Q (rev 3, frozen)

Blower free-air flow and dead-head pressure, fin area, channel loss, the Nusselt prefactor `nu_C`,
die-to-heatsink resistance and the backplate resistance, adjusted together until open air and both
anchors landed inside their bands at once. Frozen values:

- `qmax_m3s = 0.0292` (~62 CFM at 100 %), `pmax_pa = 720`, `rpm_max = 5000`.
- `r_tim = 0.062` K/W, `r_mem = 0.42` K/W, memory share 0.12.
- `nu_C = 0.100`, `nu_m = 0.60` in `Nu = C Re^m Pr^(1/3)` — **global**, shared by every card.
- Fin area 0.095 m², hydraulic diameter 1.7 mm, channel flow area 0.00115 m², channel `k = 1.6e5`.
- Bracket vent 14.5 cm², backplate path `r_ext = 3.2` K/W, capture length 9 mm.

## Flow-through cards (rev 4, per card type)

Only the per-card-type block was set, against one single-card open-air temperature at 25 °C ambient,
stock curve, full TBP. The global `nu_C`/`nu_m` stay at the Max-Q fit. Fan intercepts, fin geometry and
TIM are not published for any of these coolers; every number in their blocks is approximate.

| Card | Target (source) | Result | Fan duty | CFM | Memory |
|---|---|---:|---:|---:|---:|
| RTX 5090 FE, 575 W | ~76 °C: Gamers Nexus ≈72 °C at 21–22 °C ambient, ≈1570 RPM; Tom's Hardware ≈80 °C | **75.91** | 54 % (≈1620 of an assumed 3000 RPM) | 46.5 | 88.1 |
| RTX PRO 6000 Workstation, 600 W | none published; same housing as the 5090 FE (Puget), so it shares every cooler number | **76.35** | 56 % | 48.3 | 95.1 |
| RTX 3090 FE, 350 W | ~68 °C: Tom's Hardware ≈65 °C at ≈1100 RPM; Legit Reviews ≈67 °C at ≈1175 RPM | **68.04** | 41 % | 29.3 | 82.0 |

Fitted per card type: `fin_area_m2` (0.80 for the 5090 FE / PRO 6000 WS pair, 0.83 for the 3090 FE).
Chosen, not fitted: two-fan free air 0.062 m³/s (0.058 for the 3090), dead-head 95 Pa (85), 3000 RPM,
`r_tim` 0.032 K/W (0.050), channel `k` 2.2e4 (2.6e4), `r_ext` 2.4 K/W, inlet slit width 0.24 m and eye
0.019 m², flow-through exit width 0.22 m and backplate cutout 120 cm² (0.11 m / 60 cm² for the 3090,
whose PCB-side fan exhausts through the bracket), bracket vent 9 cm² (16 cm²). Memory resistance was set
so the 5090 FE memory lands near the ~90 °C Gamers Nexus reports.

With Custom Accelerated the same open-air cards run 65.6 (5090 FE), 66.1 (PRO 6000 WS) and 58.1 °C
(3090 FE). These are checked in `bounds_check` as `open_air_<card>` with a ±5 °C band.

## Plume ingestion (rev 4, global)

`φ(g) = φ_max · exp(−g / L_plume)` with `φ_max = 0.85`, `L_plume = 40 mm`: the share of the upper card's
fan-side intake taken straight from the lower flow-through card's jet, capped at 98 % of the jet mass.
Not fitted — there is no stacked flow-through measurement to fit against. The e-folding length is the
distance over which a ~10 cm slot jet entrains enough room air to lose most of its identity. The plume
term is what makes the stack order matter: two 5090 FE cards one empty slot apart differ by +7.9 °C with
it and +0.8 °C without it (full table in SPEC §6.3).

## Other rev 4 knobs (global, approximate)

- Seal open area 100 / 70 / 45 / 5 / 0 % for levels 1–5, discharge coefficient 0.80 / 0.72 / 0.65 /
  0.62 / —. Level 5 has no branch.
- Obstruction k multiplier 1.0 / 2.5 / 6.0, cables 1.0 / 2.0, on the GPU zone → case spill and the CPU
  cooler outlet; cluttered cables ×1.35 on card inlet slits. Rev 3 divided the spill area by 2.2 / 5.5
  (k ×4.8 / ×30) and 2.4 (k ×5.8); rev 4 states k multipliers directly and uses gentler values. Only the
  generic samples use `medium`.
- Air-cooled CPU: tower fin stack 2.5e4 Pa/(m³/s)², outlet area 0.03 m². Stefano's build is
  water-cooled, so neither touches the anchors.

## Case-side knobs (rev 3, unchanged)

Rear-slot reingestion fraction 0.22; shroud bypass fraction 0.04; shroud shell 8 cm²; plume-to-room 0.04 m²;
blower short-circuit 1.1 cm²; direct-front spill 0.045 m², mixed 0.012 m². Orifice
`ΔP = ρ Q|Q| / (2 Cd² A²)`, Idelchik's handbook as the method; no page number is invented here.

## Monte Carlo

Lognormal multipliers, seed 12345, default N = 200: `nu_C` σ 0.12, `nu_m` σ 0.04 (clipped), TIM, memory
resistance, fan Q and P, channel k, fin area, `r_ext`, every orifice k (σ 0.18), seal area (σ 0.20),
ambient ±0.8 °C, blower short-circuit area (σ 0.25), NF-A14 iPPC static pressure uniform between the web
page 6.58 and datasheet 10.52 mmH₂O, and (rev 4) `φ_max` uniform 0.70–0.95 and `L_plume` σ 0.25.

Hottest unthrottled die, 5th–95th percentile (rev 4 sweep):

| Cell | Nominal | Band | Rev 3 band |
|---|---:|---|---|
| stock (stacked, standard, shroud off, leaky) | 108.8 | 95.6–126.7 | 94–129 |
| stacked, standard, shroud on, leaky | 104.2 | 92.1–121.0 | — |
| gap1, standard, shroud off, leaky (anchor A) | 86.6 | 78.2–100.3 | 77–103 |
| gap1, standard, shroud on, leaky (best) | 84.2 | 76.1–97.6 | 74–101 |

Adding the two plume draws shifts the random stream, which is most of the band change. The stock and
best bands still overlap between about 96 and 98 °C. The nominal spacing gap is 24.6 °C and the stacked
layout still throttles while the gapped one does not.

The tornado on the stock cell (`plots/meshify2xl-stefano/tornado_stock.png`) is dominated by `nu_C`
(−6.8 / +10.1 °C for ±20 %), the orifice-k scale (−4.5 / +4.9 °C) and TIM (±3.3 °C). Blower free-air
flow barely moves the hottest card: it is inlet-starved.

## nvidia-smi refit

`gpusim calibrate --log nvidia-smi.csv` runs a least-squares fit of `nu_C` and `r_tim` on the open-air
model. It does not write `calib.py`. Copy a result in only if you intend to refit the global anchors
afterwards. An example log is `examples/nvidia_smi.csv`.

```
nvidia-smi --query-gpu=timestamp,index,power.draw,temperature.gpu,temperature.memory,fan.speed,clocks.sm --format=csv -l 1
```
