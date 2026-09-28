# Calibration

Three anchors, one set of global and per-card-type parameters, no per-cell
offsets. The numbers live in `gpusim/calib.py`. Card geometry that NVIDIA or
ELSA actually publish (300 W, 266.7 × 111.15 × 37 mm, dual slot) stays in
`presets/cards/`.

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
| B | 4 horizontal cards, no gaps, stock curve, no shroud, standard direction, leaky | unthrottled hottest ≥ 90 °C and `throttle` | **142.7 °C** unthrottled on a middle card, throttle on the cards that cross 88 °C |

Anchor B unthrottled dies, top to bottom: 86.3, 140.4, 142.7, 88.4 °C.
Cards 2 and 3 are hotter than cards 1 and 4. Card 4 has a bypass from the
PSU-shroud gap, so it is starved less than the two cards sandwiched above it.

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

Case-side knobs, also global:

- Rear-slot reingestion fraction 0.22 (the rest of an open slot mouth exchanges with room air, because a real exhaust jet entrains ambient).
- Shroud bypass fraction 0.04 of the raw slot area. The iPPC fans still only add a few percent of blower CFM; their clearer effect in this geometry is killing plume reingestion.
- Lowest-card PSU-shroud bypass 11.5 cm².

Seal steps (open-area fraction): 1 → 0.002, 2 → 0.012, 3 → 0.07, 4 → 0.28, 5 → 0.92.
Orifice `ΔP = ρ Q|Q| / (2 Cd² A²)`, Cd about 0.6–0.8. Idelchik's handbook is the
method; no page number is invented here.

## What the Monte Carlo is varying

Lognormal multipliers, seed 12345, default N = 200:

- `nu_C` σ = 0.12, `nu_m` σ = 0.04 (clipped)
- TIM, memory resistance, blower Q and P, channel k, fin area, `r_ext`
- every orifice k (σ = 0.18) and seal area (σ = 0.20)
- ambient ± about 0.8 °C
- recirculation area and the bottom bypass
- NF-A14 iPPC-3000 static pressure uniform between the web-page 6.58 mmH₂O and the datasheet 10.52 mmH₂O

On the stock cell the hottest unthrottled die is 140.5 °C with a 5th–95th band of 122–165 °C. On the best gapped cell the band is about 74–99 °C around a nominal 84 °C. Those two bands do not overlap. Bands of neighbouring gapped cells do.

The tornado on the stock cell (`plots/meshify2xl-stefano/tornado_stock.png`) is dominated by `nu_C` and the orifice-k scale. Blower free-air flow barely moves the hottest card, because that card is inlet-starved: more blower pressure does not create a gap.

## nvidia-smi refit

`gpusim calibrate --log nvidia-smi.csv` runs a least-squares fit of `nu_C` and `r_tim` on the open-air model. It does not write `calib.py`. Copy a result in only if you intend to refit the global anchors afterwards. An example log is `examples/nvidia_smi.csv`.

```
nvidia-smi --query-gpu=timestamp,index,power.draw,temperature.gpu,temperature.memory,fan.speed,clocks.sm --format=csv -l 1
```
