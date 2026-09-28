# Demo run of show

`uv run gpusim ui`, then Demo. Arrow keys step, or tick auto. The server prints
`gpusim ui at http://127.0.0.1:8000`. If that port is taken it says so and
moves to the next free port.

Both scripts are in `presets/scenarios/`. Temperatures are the nominal model, Celsius, 25 °C ambient.

Say this once, up front: this is not CFD, GPU water blocks are out of scope, and a reading is good to about ±5–10 °C. The order is the point.

The blower fan face points down, toward the case floor. On the Max-Q preset, 0.75 of the inlet eye is that fan face and 0.25 is a smaller backplate-side / end opening. That split is an assumption. The gap each face sees comes from the slot map.

## 1. Stefano's Meshify 2 XL

### Close-packed, no shroud (anchor B)

Four horizontal Max-Q blowers, no empty slot, stock fan curve, shroud off.

Say: each fan face points down at the card below it. The gap is the leftover of a dual-slot pitch after a 37 mm card, about 3.6 mm. The stock curve is already capped near 70% duty, so a hot card cannot spin out of the hole. Unthrottled dies, top to bottom, are 100.7, 108.9, 108.7 and 87.1 °C. The two middle cards are the hot ones, about 14.5 CFM. They cross the 90 °C cutoff and the throttle flag comes on, as does the top card. The bottom card's fan sees about 40 mm of PSU-shroud clearance, holds about 25 CFM, and stays near 87 °C. Its backplate opening is the small share, so the open floor gap is what saves it.

### Gaps plus a vertical card (anchor A)

One empty slot between the three horizontal cards, fourth card in vertical slot v2, shroud still off.

Say: the empty slot is an open mouth, brackets are off, and the downward fan face sees that opening instead of the next card. Hottest die is 86.5 °C (86.5, 86.5, 86.4, 86.4 on the vertical card). About 26 CFM. Nothing throttles. This is the measured anchor. Spacing did almost all of the work.

### Rear shroud, 2× NF-A14 industrialPPC-3000

Same layout, shroud on.

Say: the shroud is one plenum over every bracket, and the two industrial fans pull on it, in series with the blowers. Hottest die 84.3 °C (84.3, 84.3, 84.2, 84.2). Mean flow rises from 25.7 CFM to 26.5 CFM. The larger effect on screen is inlet air falling back toward 25 °C, because exhaust is no longer available to be sucked in the open slot mouths. Do not claim a big CFM miracle. Also say the datasheet static pressure is 10.52 mmH₂O and the current Noctua web page says 6.58; the model uses the datasheet and the Monte Carlo spans both.

### Positive pressure, taped

Same cards, every case fan and the radiator flipped to intake, seals at tape level, shroud still on.

Say: case pressure goes positive, about +18 Pa, which does cut recirculation. The radiator is now heating the intake with the CPU. Hottest die 85.7 °C, a bit worse than leaving the fans alone (84.3 °C). Positive pressure is not free.

### Aggressive blower curve

Back to normal fan directions, shroud on, GPU fans allowed to reach 100% by 70 °C.

Say: affinity laws, flow with RPM and pressure with RPM squared. Hottest die 75.5 °C, about 37 CFM. On a single card in open air the same curve is 73.4 °C against 82.8 °C with the stock cap. This is a software change. Do it after the cards are already spaced, or you will not know which change you measured.

### Optimal search

Say: the search tried 48 air-cooled layouts. The winner is the point you are already on: gaps, vertical card, shroud on, normal case-fan direction, aggressive curve, 75.5 °C. Water blocks were not in the search.

## 2. Mike Bradley powerhouse (illustrative mock)

Read the banner out loud: illustrative mock, not a measurement or a claim about anyone's real build. Quick start has its own button for the plain Corsair 9000D sample. This script is the separate mock.

### As mocked

9000D, three gapped horizontal cards plus one vertical, Corsair intakes, top radiator exhaust, shroud, aggressive curve. Hottest die about 75.4 °C. Same solver as the Meshify. Only the box and the fans changed.

### Shroud off

Pull the shroud. Hottest die about 76.6 °C. Bracket outlets see the room again, and a path back into the case. Compare CFM, not just the colour of the cards.

### Close-packed

Eight horizontal slots, four dual-slot cards, no empty slot left, aggressive curve still on. Hottest dies about 84.6, 89.6, 89.6 and 74.9 °C. The two middle cards throttle. The bottom card's fan still sees the floor clearance. A strong shroud and a 100% blower curve do not invent an inlet gap. Watch the middle cards.
