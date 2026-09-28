# Demo run of show

`uv run gpusim ui`, then Demo. Arrow keys step, or tick auto; Esc closes. The server prints
`gpusim ui at http://127.0.0.1:8000`; if that port is taken it says so and moves to the next free port.
For OBS, press Present (hides the left bar and panel) and use the window at 1920 × 1080.

Both scripts are in `presets/scenarios/`. Temperatures are the nominal model, Celsius, 25 °C ambient.

Say this once, up front: this is not CFD, GPU water blocks are out of scope, and a reading is good to about
±5–10 °C. The order is the point. Hover anything on screen for the assumption behind it.

Every card's fan face points down, toward the floor. Blowers push their air out of the rear bracket.
Flow-through cards push it up, into the card above.

Tip: press **Split** in the header to put the resistor network next to the case. Layer 1 is the airflow
(pressure = voltage, flow = current); layer 2 is each card's thermal chain, with the die temperature
written out as `T_in + Q·R_conv + P·R_tim`.

## 1. Stefano's Meshify 2 XL (`?demo=stefano`)

### Close-packed, no shroud (anchor B)

Four horizontal Max-Q blowers, no empty slot, stock fan curve, shroud off.

Say: each fan face points down at the card below across about 3.6 mm. The stock curve is already capped
near 70 % duty, so a hot card cannot spin out of the hole. Unthrottled dies, top to bottom: 100.8, 109.0,
108.8 and 87.2 °C. The middle two are the hot ones, about 15 CFM each. Three cards cross the 90 °C cutoff
and throttle. The bottom card's fan sees about 40 mm of PSU-shroud clearance, holds 26 CFM, and stays near
87 °C. In the network view, look at the slot-gap resistors on the middle cards.

### Gaps plus a vertical card (anchor A)

One empty slot between the three horizontal cards, fourth card in vertical slot v2, shroud still off.

Say: the empty slot is an open mouth with the brackets off. Hottest die 86.6 °C, all four within 0.1 °C,
about 26 CFM each. Nothing throttles. This is the measured anchor. Spacing did almost all of the work.

### Rear shroud, 2× NF-A14 industrialPPC-3000

Same layout, shroud on.

Say: one plenum over every bracket, two industrial fans pulling on it, in series with the blowers. Hottest
die 84.2 °C. Mean flow rises from 25.7 to 26.5 CFM. The larger effect is that exhaust is no longer pulled
back in through the open slot mouths. The datasheet static pressure is 10.52 mmH₂O and the web page says
6.58; the model uses the datasheet and the Monte Carlo spans both.

### Positive pressure, taped

Every case fan and the radiator flipped to intake, seals at level 4–5, shroud on.

Say: seal levels now run 1 = fully open to 5 = sealed; tape is 4–5. Case pressure goes to about +18 Pa,
which cuts recirculation, but the radiator now heats the intake with the CPU. Hottest die 85.5 °C, a bit
worse than 84.2. Positive pressure is not free.

### Custom Accelerated fan curve

Normal fan directions, shroud on, GPU fans on Custom Accelerated: off at 25 °C, 100 % at 70 °C.

Say: affinity laws, flow with RPM and pressure with RPM squared. Hottest die 75.4 °C, about 37 CFM. One
card in open air on the same curve is 73.4 °C against 82.8 °C stock. This is a software change; do it after
the cards are spaced, or you will not know which change you measured.

### Same slots, flow-through cards

Same layout and shroud, but 4× RTX PRO 6000 Workstation (600 W, flow-through).

Say: these cards pull air from underneath and blow it out of the top, straight into the fan of the card
above. With one empty slot the upper card breathes half of that exhaust. Unthrottled 95.0, 93.1 and
83.1 °C top to bottom, 83.3 °C on the vertical card; the top two throttle. Open the network view: the orange
dashed branches are the plume. The shroud hardly matters now, because the heat leaves through the case
fans, not the brackets.

### Optimal search

Say: the search tried 48 air-cooled layouts on the Max-Q. The winner is gaps, vertical card, shroud on,
normal fan directions, Custom Accelerated, 75.4 °C (Monte Carlo 68–88 °C). Water blocks were not in the
search.

## 2. Mike Bradley powerhouse (illustrative mock, `?demo=mike-bradley`)

Read the banner out loud: *Illustrative mock — not a measurement or claim about anyone's real build.* The
link is shareable. Quick start has a separate button for the plain Corsair 9000D template.

### As mocked

A 9000D with eight AF120 RGB ELITE front intakes (the case ships with no fans; the front takes 8×120, four
high and two wide — click Front to see all eight in the face inset), three RS120 side intakes, a top 360
exhaust, a 2× iPPC shroud, three gapped Max-Q cards plus one vertical, Custom Accelerated. Hottest die about
75.2 °C. Same solver as the Meshify; only the box and the fans changed.

### Shroud off

Pull the shroud. Hottest die about 75.5 °C. With this much intake the shroud buys very little.

### Close-packed

Eight horizontal slots, four dual-slot cards, no empty slot, Custom Accelerated still on. Unthrottled about
85.1, 91.0, 90.9 and 75.2 °C; the middle two throttle. A strong shroud and a 100 % curve do not invent an
inlet gap.
