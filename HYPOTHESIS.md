# What to test on the real machine

The factorial is a hypothesis generator for Stefano's Meshify 2 XL. Absolute temperatures carry about
±5–10 °C of uncertainty. Monte Carlo is 200 samples, seed 12345. On the stock cell the hottest-die band is
94–126 °C. On the best gapped cell it is 76–98 °C. Those tails touch only between about 94 and 98 °C. The
nominal spacing gap is about 25 °C, and it is the only factor that large. Differences of 2 °C among
already-gapped cells are inside the noise.

Numbers use the fan layout Stefano confirmed (rev 4.1): 3 front intakes, a top intake and a bottom
intake at the front, the radiator slid to the rear as exhaust, one rear exhaust.

Deltas below are versus the stock cell: four horizontal cards stacked, standard fan
directions, shroud off, leaky seals, stock blower curve. After the 2026-09-30 soak fit its dies,
top to bottom, are 91.4, 93.1, 93.1 and 88.7 °C at full board power (the old 90 °C cutoff is no
longer folding this cell onto 89.5 °C). The sweep writes a generated sibling at
`results/meshify2xl-stefano/hypothesis_auto.md` and leaves this file alone. That generated file
still describes the pre-soak sweep until the next `gpusim sweep`.

Seal levels in rev 4 run 1 = fully open to 5 = sealed. "Leaky" is the realistic stock case (mesh + filter
front and top at 3, glass side at 5, seams at 4, open slot mouths at 3). "Sealed" is tape: 4–5 everywhere.

The blower fan face points down. On a stacked pair it faces the next card across 3.6 mm; the lowest
horizontal card's fan sees the 40 mm PSU-shroud clearance (approximate). That is why the middle of a close
pack is the hot card.

## 1. Open a slot between the horizontal cards

`s-gap1__p-standard__sh-off__l-leaky` — the spaced, shroud-off soak (measured hottest die 89 °C).

Hottest die 88.9 °C at full power; 88.9, 88.9, 88.8 and 88.8 °C, about 29 CFM each. Delta versus
the stacked stock cell: −4 °C (93.1 → 88.9).

Why: one empty slot opens the blower inlet. The slit is no longer a sharp-edged orifice of the
projected gap (`inlet_cd` 2.0, calibrated to the same soaks), so a stacked card already moves
about 26 CFM and spacing is a few degrees, not twenty. No new parts.

Confidence: the soak is the number. Spacing still helps; it is not the whole story.

## 2. Then switch on the rear shroud

`s-gap1__p-standard__sh-on__l-leaky` — best cell in the factorial.

Hottest die 79.0 °C (middle card 72.9 °C, the other three 79.0 °C). Nominal delta versus the
gapped, shroud-off cell is −9.9 °C, which is the spaced soak (89 °C off, 79 °C on). About 58 CFM
bypasses the fins through the two interior gaps and cools the skins, including one face of the
vertical card. The open-gap mouth coefficient is 0.95 and the open-gap Nusselt prefactor is 1.15,
both calibrated to that soak. The taped crack is unchanged.

The shroud does not rescue a stacked, taped layout: orientation B is 91.1 °C against 93.1 °C with
the shroud off, a 2.0 °C benefit, matching the stacked soaks. See docs/CALIBRATION.md.

Confidence: these four soaks are what the coefficients were fit to. A new layout is still ±5–10 °C.

## 3. Custom Accelerated fan curve on that same geometry

Not a factorial factor. Custom Accelerated (0 % at 25 °C, linear to 100 % at 70 °C) on gap + vertical,
shroud on, standard, leaky: hottest die 73.5 °C nominal, about 42 CFM per blower. The open-air check of
the same curve is 78.6 °C versus 88.7 °C stock. No parts: a vendor fan-curve change. Do it after tests 1
and 2 so the curve is not confounded with moving cards.

## 4. Do not tape the case and flip every fan to intake yet

`s-gap1__p-high__sh-off__l-sealed` is 90.5 °C at about +20 Pa. The
radiator is an intake in that mode, so 150 W of CPU heat (assumed) rides in with the fresh air.
`s-gap1__p-high__sh-on__l-sealed` is 78.8 °C, within a degree of leaving the fans alone with the shroud on
(79.0 °C). Treat positive-pressure-plus-tape as a later, optional negative test.

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
