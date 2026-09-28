# Demo run of show

`uv run gpusim ui`, then Demo. Arrow keys step, or tick auto.
Both scripts are in `presets/scenarios/`. Temperatures are the nominal model, Celsius, 25 °C ambient.

Say this once, up front: this is not CFD, GPU water blocks are out of scope, and a reading is good to about ±5–10 °C. The order is the point.

## 1. Stefano's Meshify 2 XL

### Close-packed, no shroud (anchor B)

Four horizontal Max-Q blowers, no empty slot, stock fan curve, shroud off.

Say: each blower inlet faces the card above it. The gap is the leftover of a dual-slot pitch after a 37 mm card, about 3.6 mm. The stock curve is already capped near 70% duty, so a hot card cannot spin out of the hole. Middle cards fall to about 8 CFM. Unthrottled dies are about 86, 140, 143 and 88 °C. The two middle cards cross the 90 °C cutoff and the throttle flag comes on. The lowest card is cooler than the middle because air can still sneak in along the PSU shroud.

### Gaps plus a vertical card (anchor A)

One empty slot between the three horizontal cards, fourth card in vertical slot v2, shroud still off.

Say: the empty slot is an open mouth, brackets are off, and the Meshify's front fans blow straight at the stack. Hottest die is 86.5 °C (86.3, 86.5, 84.3 on the vertical card's neighbours, 86.3 vertical). Nothing throttles. This is the measured anchor. Spacing did almost all of the work.

### Rear shroud, 2× NF-A14 industrialPPC-3000

Same layout, shroud on.

Say: the shroud is one plenum over every bracket, and the two industrial fans pull on it, in series with the blowers. Hottest die 84.3 °C. Flow per card only rises a couple of CFM; the larger effect on screen is inlet air falling back toward 25 °C, because exhaust is no longer available to be sucked in the open slot mouths. Do not claim a big CFM miracle. Also say the datasheet static pressure is 10.52 mmH₂O and the current Noctua web page says 6.58; the model uses the datasheet and the Monte Carlo spans both.

### Positive pressure, taped

Same cards, every case fan and the radiator flipped to intake, seals at tape level, shroud still on.

Say: case pressure goes positive, about +18 Pa, which does cut recirculation. The radiator is now heating the intake with the CPU. Hottest die 85.8 °C, a bit worse than leaving the fans alone. Positive pressure is not free.

### Aggressive blower curve

Back to normal fan directions, shroud on, GPU fans allowed to reach 100% by 70 °C.

Say: affinity laws, flow with RPM and pressure with RPM squared. Hottest die 75.5 °C, about 37 CFM. On a single card in open air the same curve is 73.4 °C against 82.8 °C with the stock cap. This is a software change. Do it after the cards are already spaced, or you will not know which change you measured.

### Optimal search

Say: the search tried 48 air-cooled layouts. The winner is the point you are already on: gaps, vertical card, shroud on, normal case-fan direction, aggressive curve, 75.5 °C. Water blocks were not in the search.

## 2. Mike Bradley powerhouse (illustrative mock)

Read the banner out loud: illustrative mock, not a measurement or a claim about anyone's real build.

### As mocked

9000D, three gapped horizontal cards plus one vertical, Corsair intakes, top radiator exhaust, shroud, aggressive curve. Same solver as the Meshify. Only the box and the fans changed.

### Shroud off

Pull the shroud. Bracket outlets see the room again, and a path back into the case. Compare CFM, not just the colour of the cards.

### Close-packed

Eight horizontal slots, four dual-slot cards, no empty slot left. A strong shroud and a 100% blower curve do not invent an inlet gap. Watch the middle cards.
