# What to test on the real machine

The factorial is a hypothesis generator for Stefano's Meshify 2 XL. Absolute
temperatures carry about ±5–10 °C of uncertainty (the Monte Carlo 5th–95th
band on a gapped cell is roughly 75–101 °C). The spacing effect is much larger
than that band. The 2 °C differences among already-gapped cells are not.

Deltas below are versus the stock cell: three horizontal cards stacked, one
vertical, standard fan directions, shroud off, leaky seals, stock blower curve.
Its unthrottled hottest die is 140.5 °C (Monte Carlo 122–165 °C) and the
throttled equilibrium sits on the 90 °C cutoff. Bands are 200 samples, seed 12345.

## 1. Open a slot between the horizontal cards

`s-gap1__p-standard__sh-off__l-leaky` — this is measured anchor A.

Predicted hottest die 86.5 °C, unthrottled, no throttle flag.
Per card, top to bottom: 86.3, 86.5, 84.3, and 86.3 °C on the vertical card.
Delta versus stock: −54 °C unthrottled (140.5 → 86.5). Monte Carlo 77–101 °C,
which does not overlap the stock band.

Why: with no empty slot, card 2's blower inlet faces card 1's backplate across
about 3.6 mm (dual-slot pitch minus the 37 mm card). Flow on that card falls to
about 8 CFM and the unthrottled die runs away. One empty slot restores about
26 CFM and the card stops throttling. No new parts. Move the cards.

Confidence: high for the direction and for "this is the test that matters".
Low for the exact degree.

## 2. Then switch on the rear shroud

`s-gap1__p-standard__sh-on__l-leaky` — best cell in the factorial.

Predicted hottest die 84.3 °C (84.1, 84.3, 82.2, 84.1). Nominal delta versus
the gapped, shroud-off cell is −2.2 °C. Mean blower flow rises from 26.2 CFM
to 27.0 CFM, and inlet air drops back toward ambient because the plenum stops
the exhaust plume being pulled in the open slot mouths.

Monte Carlo 74.5–99.2 °C fully overlaps the shroud-off band. A 2 °C nominal
gain is inside the noise. The shroud does not rescue a stacked layout: stacked
with the shroud on is still an unthrottled 134 °C and still throttles.

Confidence: low that the bench will see 2 °C. Medium that the shroud will not
make a gapped machine worse, and that it is not a substitute for spacing.
Hardware is already in hand, so it is the second test, not the first.

## 3. Raise the GPU fan cap on that same geometry

Not a factorial factor. `maxq_aggressive` (100% duty by 70 °C) on
gap + vertical, shroud on, standard, leaky: hottest die 75.5 °C nominal,
about 37 CFM per blower. The open-air check of the same curve is 73.4 °C
versus 82.8 °C on the stock cap. No parts: it is a vendor fan-curve change.
Do it after the geometry in tests 1 and 2 is on the bench, so the curve is not
confounded with moving cards.

The optimizer's best of 48 air-cooled candidates is this same point
(gap-plus-vertical, shroud on, standard, leaky, aggressive), 75.5 °C.

## 4. Do not tape the case and flip every fan to intake yet

`s-gap1__p-high__sh-off__l-sealed` is the worst gapped cell: hottest 88.6 °C,
throttle flag on, case pressure about +19 Pa. The radiator is an intake in
that mode, so CPU heat (150 W assumed) rides in with the fresh air, and the
sealed box cannot dump it anywhere except the blowers.

`s-gap1__p-high__sh-on__l-sealed` is 85.8 °C, still worse than leaving the
fans in the normal direction with the shroud on (84.3 °C). Monte Carlo bands
overlap. Treat positive-pressure-plus-tape as a later, optional negative test:
if the bench agrees it is not cooler, the radiator-preheat story holds.

## Suggested order

1. Spacing only, shroud off (anchor A against the stacked stock cell).
2. Shroud on, same spacing.
3. Aggressive GPU fan curve on that geometry.
4. Tape and intake-radiator only if 1–3 are done and you want the negative control.

If two gapped cells differ by less than about 3 °C, call them a tie until the
bench says otherwise. Water blocks are not part of this plan.
