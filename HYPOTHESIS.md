# What to test on the real machine

The factorial is a hypothesis generator for Stefano's Meshify 2 XL. Absolute temperatures carry about
±5–10 °C of uncertainty. Monte Carlo is 200 samples, seed 12345. On the stock cell the hottest-die band is
94–126 °C. On the best gapped cell it is 76–98 °C. Those tails touch only between about 94 and 98 °C. The
nominal spacing gap is about 25 °C, and it is the only factor that large. Differences of 2 °C among
already-gapped cells are inside the noise.

Numbers use the fan layout Stefano confirmed (rev 4.1): 3 front intakes, a top intake and a bottom
intake at the front, the radiator slid to the rear as exhaust, one rear exhaust.

Deltas below are versus the stock cell: three horizontal cards stacked, one vertical, standard fan
directions, shroud off, leaky seals, stock blower curve. Its unthrottled dies, top to bottom, are 100.2,
108.2, 86.6 and 86.0 °C (horizontal slots 1, 3, 5, then vertical v2). The throttled equilibrium sits just
under the 90 °C cutoff. The sweep writes a generated sibling at
`results/meshify2xl-stefano/hypothesis_auto.md` and leaves this file alone.

Seal levels in rev 4 run 1 = fully open to 5 = sealed. "Leaky" is the realistic stock case (mesh + filter
front and top at 3, glass side at 5, seams at 4, open slot mouths at 3). "Sealed" is tape: 4–5 everywhere.

The blower fan face points down. On a stacked pair it faces the next card across 3.6 mm; the lowest
horizontal card's fan sees the 40 mm PSU-shroud clearance (approximate). That is why the middle of a close
pack is the hot card.

## 1. Open a slot between the horizontal cards

`s-gap1__p-standard__sh-off__l-leaky` — measured anchor A.

Predicted hottest die 86.2 °C, no throttle; 86.2, 86.2, 86.1 and 86.2 °C on the vertical card, about
25.8 CFM each. Delta versus stock: −22 °C unthrottled (108.2 → 86.2). Monte Carlo 78–100 °C.

Why: stacked, the middle card's fan faces the next card across 3.6 mm and its unthrottled flow is about
14.9 CFM. One empty slot makes every downward fan eye-limited instead of gap-limited. No new parts.

Confidence: high for the direction and for "this is the test that matters". Low for the exact degree.

## 2. Then switch on the rear shroud

`s-gap1__p-standard__sh-on__l-leaky` — best cell in the factorial.

Predicted hottest die 84.0 °C on every card (83.9 °C sealed, a tie). Nominal delta versus the gapped,
shroud-off cell is −2.2 °C. Mean blower flow rises from 25.8 to 26.7 CFM. The case runs slightly below room pressure
(about −3 Pa), so with the shroud off some exhaust plume comes back in through the open slot
mouths; the plenum stops that. At positive case pressure there would be nothing to stop. Monte Carlo 76–98 °C fully overlaps the shroud-off band.

The shroud does not rescue a stacked layout: stacked with the shroud on is still an unthrottled 103.9 °C
(96.5, 103.9, 84.2, 83.6) and still throttles.

Confidence: low that the bench will see 2 °C. Medium that the shroud will not make a gapped machine worse.

## 3. Custom Accelerated fan curve on that same geometry

Not a factorial factor. Custom Accelerated (0 % at 25 °C, linear to 100 % at 70 °C) on gap + vertical,
shroud on, standard, leaky: hottest die 75.3 °C nominal, about 37 CFM per blower. The open-air check of
the same curve is 73.4 °C versus 82.8 °C stock. No parts: a vendor fan-curve change. Do it after tests 1
and 2 so the curve is not confounded with moving cards. The optimizer's best of 48 candidates is this same
point with sealed seams, 75.3 °C (Monte Carlo 68–88 °C).

## 4. Do not tape the case and flip every fan to intake yet

`s-gap1__p-high__sh-off__l-sealed` is the worst gapped cell: 88.2 °C, throttle flag on, about +20 Pa. The
radiator is an intake in that mode, so 150 W of CPU heat (assumed) rides in with the fresh air.
`s-gap1__p-high__sh-on__l-sealed` is 85.5 °C, still worse than leaving the fans alone with the shroud on
(84.0 °C). Treat positive-pressure-plus-tape as a later, optional negative test.

## Suggested order

1. Spacing only, shroud off (anchor A against the stacked stock cell).
2. Shroud on, same spacing.
3. Custom Accelerated GPU curve on that geometry.
4. Tape and intake radiator only if 1–3 are done and you want the negative control.

If two gapped cells differ by less than about 3 °C, call them a tie until the bench says otherwise.

## If the cards were ever flow-through

Not Stefano's hardware, but the same slots with 4× RTX PRO 6000 Workstation (600 W) run 95.0, 93.1, 83.1
and 83.3 °C unthrottled, and the top two throttle: each upper card breathes about half of the exhaust of
the card below it. For those cards the test would be spacing again, not the shroud. Water blocks are not
part of this plan.
