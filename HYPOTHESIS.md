# What to test on the real machine

The factorial is a hypothesis generator for Stefano's Meshify 2 XL. Absolute
temperatures carry about ±5–10 °C of uncertainty. Monte Carlo is 200 samples,
seed 12345. On the stock cell the hottest-die band is 94–129 °C. On the best
gapped cell it is 74–101 °C. Those tails overlap from about 94 to 101 °C, so
one bench reading can land in both. The nominal spacing gap is still about
24 °C, and it is the only factor that large. Differences of 2 °C among
already-gapped cells are inside the noise.

Deltas below are versus the stock cell: three horizontal cards stacked, one
vertical, standard fan directions, shroud off, leaky seals, stock blower curve.
Its unthrottled dies, top to bottom, are 100.8, 108.8, 87.1 and 86.4 °C
(horizontal slots 1, 3, 5, then vertical v2). The throttled equilibrium sits
on the 90 °C cutoff. The sweep writes a generated sibling at
`results/meshify2xl-stefano/hypothesis_auto.md` and leaves this file alone.

The blower fan face points down, toward the floor. Each card preset splits the
eye: 0.75 on that fan face, 0.25 on a smaller backplate-side / end opening
(approximate; NVIDIA does not publish the split). The gap on each face comes
from the slot map. A stacked pair leaves about 3.6 mm (dual-slot pitch minus
the 37 mm card). The lowest horizontal card's fan sees the Meshify PSU-shroud
clearance, 40 mm, marked approximate. The top card's backplate opening sees
the CPU-area clearance. That is why the middle of a close pack is the hot
card, and why the card over the shroud is not.

## 1. Open a slot between the horizontal cards

`s-gap1__p-standard__sh-off__l-leaky` — this is measured anchor A.

Predicted hottest die 86.5 °C, unthrottled, no throttle flag.
Per card, top to bottom: 86.5, 86.5, 86.4, and 86.4 °C on the vertical card.
About 25.7 CFM each. Delta versus stock: −22 °C unthrottled (108.8 → 86.5).
Monte Carlo 77–103 °C.

Why: with no empty slot, the middle card's fan faces the next card across
3.6 mm and its backplate opening faces the card above across the same gap.
Unthrottled flow on that card is about 14.5 CFM and the die runs to 108.8 °C.
The lowest horizontal card is already at 87.1 °C because its fan sees 40 mm,
and the vertical card sees about 28 mm off to the side. One empty slot makes
every downward fan eye-limited instead of gap-limited. No new parts. Move the
cards.

Confidence: high for the direction and for "this is the test that matters".
Low for the exact degree. The Monte Carlo tails do touch the stock band, so
treat a single noisy reading as a tie until you have both layouts.

## 2. Then switch on the rear shroud

`s-gap1__p-standard__sh-on__l-leaky` — best cell in the factorial.

Predicted hottest die 84.3 °C (84.3, 84.3, 84.2, 84.2). Nominal delta versus
the gapped, shroud-off cell is −2.2 °C. Mean blower flow rises from 25.7 CFM
to 26.5 CFM. The plenum stops the exhaust plume being pulled in the open slot
mouths.

Monte Carlo 74–101 °C fully overlaps the shroud-off band (77–103 °C). A 2 °C
nominal gain is inside the noise. The shroud does not rescue a stacked layout:
stacked with the shroud on is still an unthrottled 104.2 °C (96.8, 104.2,
84.4, 83.8) and still throttles.

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

`s-gap1__p-high__sh-on__l-sealed` is 85.7 °C, still worse than leaving the
fans in the normal direction with the shroud on (84.3 °C). Monte Carlo bands
overlap. Treat positive-pressure-plus-tape as a later, optional negative test:
if the bench agrees it is not cooler, the radiator-preheat story holds.

Four horizontal cards with no vertical (anchor B, not a factorial cell) is the
close-pack check. Unthrottled dies 100.7, 108.9, 108.7, 87.1 °C. The two
middle cards are hottest. The bottom card's fan sees the 40 mm shroud
clearance and holds about 25 CFM. Throttle flags on the three cards that
cross 90 °C.

## Suggested order

1. Spacing only, shroud off (anchor A against the stacked stock cell).
2. Shroud on, same spacing.
3. Aggressive GPU fan curve on that geometry.
4. Tape and intake-radiator only if 1–3 are done and you want the negative control.

If two gapped cells differ by less than about 3 °C, call them a tie until the
bench says otherwise. Water blocks are not part of this plan.
