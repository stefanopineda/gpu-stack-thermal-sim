# Calibration

Three anchors, one set of global and per-card-type parameters, no per-cell
offsets. The numbers live in `gpusim/calib.py`. Card geometry that NVIDIA or
ELSA actually publish (300 W, 266.7 × 111.15 × 37 mm, dual slot) stays in
`presets/cards/`. Inlet orientation is a card-preset field, documented below,
and it is not refit per sweep cell.

## Inlet geometry

In a standard ATX tower the blower fan face points down, toward the case floor.
SPEC rev 3 originally said card N's inlet faces card N-1's backplate (toward
the CPU). That sentence was a wording error. The model follows the tower.

Each card preset sets `inlet_faces` (`floor`, `cpu`, or `both`) and
`inlet_split`, the fraction of inlet eye on the fan face. The rest is the
backplate-side / end opening. The Max-Q and the custom 300 W blower both use
`both` with `inlet_split` 0.75. NVIDIA does not publish that split. 0.75 / 0.25
is an assumption, flagged approximate on the card YAML: most of the eye is the
fan, and workstation blowers often also draw through a smaller opening on the
backplate or the end. It was not tuned to force a ranking.

The gap on each face comes from the slot map, for every card:

- Fan side: the next card below, empty slots between, or `psu_shroud_clearance_mm` when nothing is below. On the Meshify that clearance is 40 mm, approximate.
- Backplate side: the next card above, or `clearance_above_top_mm` on the top card.
- Vertical cards: both faces see `vertical_inlet_gap_mm` (28 mm on the Meshify, approximate, off to the side).
- An open PSU bay, or a case with no PSU shroud, multiplies the floor clearance by 1.8. That is case geometry, applied whenever the floor is the neighbour.

A dual-slot 37 mm card on a 20.32 mm pitch leaves about 3.6 mm (`no_slot`) against the next card. One empty slot is about 24 mm (`open_slot`) with the brackets removed. There is no extra orifice that only the lowest card receives.

With the fan pointing down, anchor B's middle cards are the hottest without any per-cell offset. Unthrottled dies, top to bottom: 100.7, 108.9, 108.7, 87.1 °C. Cards 2 and 3 see 3.6 mm on both faces and fall to about 14.5 CFM. Card 1's fan is just as tight, but a quarter of its eye sees the CPU clearance, so it stops at 100.7 °C. Card 4's fan sees the 40 mm floor clearance and holds about 25 CFM at 87.1 °C. Global knobs in `calib.py` were not retuned for this orientation. The same values still land every anchor.

## What was fit

Blower free-air flow and dead-head pressure, fin area, channel loss, the
Nusselt prefactor `nu_C`, die-to-heatsink resistance, and the backplate
resistance. They were adjusted together until all three anchors landed inside
their bands at once. The stock duty cap (70% from 88 °C) and the aggressive
curve (100% at 70 °C) were not fit; they are the curves from SPEC rev 3.

| Anchor | Definition | Target | Result |
|---|---|---|---|
| Open air | 1× RTX PRO 6000 Blackwell Max-Q, 300 W, stock curve, 25 °C, no case | 75–85 °C, aim ~83 | **82.8 °C**, no throttle |
| A | Meshify 2 XL, 3 horizontal cards with one empty slot, 1 vertical, stock curve, no shroud, standard direction, leaky | 86 ± 3 °C | **86.5 °C**, no throttle |
| B | 4 horizontal cards, no gaps, stock curve, no shroud, standard direction, leaky | unthrottled hottest ≥ 90 °C and `throttle`, middle cards hottest | **108.9 °C** unthrottled on a middle card, throttle on the three cards that cross 88 °C |

Anchor A unthrottled dies, top to bottom: 86.5, 86.5, 86.4, 86.4 °C, about 25.7 CFM.
Anchor B unthrottled dies, top to bottom: 100.7, 108.9, 108.7, 87.1 °C.
Cards 2 and 3 are hotter than cards 1 and 4.

Aggressive curve, same open-air card: **73.4 °C** (the spec asks for under ~75 °C).

Residuals against the point targets: open air −0.2 °C, anchor A +0.5 °C.
Anchor B is a threshold, not a point target. Nothing was nudged after the fact
on a single sweep cell.

## Frozen parameters (approximations)

Blower, shared by both card types:

- `qmax_m3s = 0.0292` (~62 CFM at 100% RPM). Not published.
- `pmax_pa = 720`. Not published.
- `rpm_max = 5000`, `rpm_min = 1200`. Duty is a fraction of max RPM, with that floor.
- `r_tim = 0.062` K/W, `r_mem = 0.42` K/W, memory share 0.12.
- `nu_C = 0.100`, `nu_m = 0.60` in `Nu = C Re^m Pr^(1/3)`.
- Fin area 0.095 m², hydraulic diameter 1.7 mm, channel flow area 0.00115 m².
- Channel loss `k = 1.6e5` Pa/(m³/s)². Bracket vent 14.5 cm².
- Backplate path `r_ext = 3.2` K/W. Capture length 9 mm.
- `inlet_faces = both`, `inlet_split = 0.75` on the card preset. Approximate.

Case-side knobs, also global:

- Rear-slot reingestion fraction 0.22 (the rest of an open slot mouth exchanges with room air, because a real exhaust jet entrains ambient).
- Shroud bypass fraction 0.04 of the raw slot area. The iPPC fans still only add a few percent of blower CFM (25.68 → 26.50 on the gapped layout); their clearer effect in this geometry is killing plume reingestion.
- Meshify floor clearance 40 mm and vertical-slot side clearance 28 mm, both approximate, on the case preset.

Seal steps (open-area fraction): 1 → 0.002, 2 → 0.012, 3 → 0.07, 4 → 0.28, 5 → 0.92.
Orifice `ΔP = ρ Q|Q| / (2 Cd² A²)`, Cd about 0.6–0.8. Idelchik's handbook is the
method; no page number is invented here.

## What the Monte Carlo is varying

Lognormal multipliers, seed 12345, default N = 200:

- `nu_C` σ = 0.12, `nu_m` σ = 0.04 (clipped)
- TIM, memory resistance, blower Q and P, channel k, fin area, `r_ext`
- every orifice k (σ = 0.18) and seal area (σ = 0.20)
- ambient ± about 0.8 °C
- recirculation area
- NF-A14 iPPC-3000 static pressure uniform between the web-page 6.58 mmH₂O and the datasheet 10.52 mmH₂O

On the stock cell the hottest unthrottled die is 108.8 °C with a 5th–95th band of 94–129 °C. On the best gapped cell the band is 74–101 °C around a nominal 84.3 °C. The tails overlap between about 94 and 101 °C. The nominals are 24 °C apart, and the stacked layout still throttles while the gapped layout does not. Bands of neighbouring gapped cells overlap completely.

The tornado on the stock cell (`plots/meshify2xl-stefano/tornado_stock.png`) is dominated by `nu_C` (about −7 to +10 °C for a ±20% kick) and the orifice-k scale (about ±5 °C). Blower free-air flow barely moves the hottest card (under 1 °C), because that card is inlet-starved: more blower pressure does not create a gap.

## nvidia-smi refit

`gpusim calibrate --log nvidia-smi.csv` runs a least-squares fit of `nu_C` and `r_tim` on the open-air model. It does not write `calib.py`. Copy a result in only if you intend to refit the global anchors afterwards. An example log is `examples/nvidia_smi.csv`.

```
nvidia-smi --query-gpu=timestamp,index,power.draw,temperature.gpu,temperature.memory,fan.speed,clocks.sm --format=csv -l 1
```
