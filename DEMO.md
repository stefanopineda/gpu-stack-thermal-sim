# Demo run of show

## Launch stream: "Would you rip the case apart for 5 °C?" (gpuism.com)

Record and stream from **https://gpuism.com**, the page viewers will click. Before going live, open it
once so the in-browser solver is loaded and cached (a cold load takes 7–10 s), click **Stefano's Meshify
2 XL**, open **Worth it?**, and press **Present** (the Worth it? panel stays on screen in Present mode).

### 60–90 s cut

1. **Hook: Mike Bradley's stack.** Home → Mike Bradley's Dengen X Station. Four RTX PRO 6000
   Workstation cards touching. "One number in this model was fit to his top card at 80 % fans, 79 °C.
   Then it predicted his 100 % reading: he measured 69, the model says 71.1. That duct was not refit today."
2. **Your build.** Home → Stefano's Meshify 2 XL. Hover the hottest card (79 °C). That number is the spaced, shroud-on soak from 2026-09-30.
3. **The answer.** Worth it? Walk down the list:
   - Cap power at 80 %: −10 °C, free (costs performance).
   - Aggressive fan curve: −5.6 °C, free (louder).
   - Seal, fill the empty mount, flip exhausts: a few tenths, inside the noise.
   - The shroud: taking it off warms the hottest die by 10 °C (79 → 89), which is the spaced pair of soaks. Not inside the noise.
   - Stack and tape (orientation B) is 91 °C, 12 °C hotter than this layout. The stacked soaks only moved 2 °C when the shroud went on.
4. **Close.** Apply the fan curve: 79 → 73.5 °C.
   Copy link: the whole build is in the URL.

### Live shroud test (the part that might fail on stream)

Fit to the four soaks on 2026-09-30: **spaced, shroud on 79 °C; spaced, shroud off 89 °C
(a 10 °C benefit). Stacked and taped, shroud off 93 °C; stacked and taped, shroud on 91 °C
(a 2 °C benefit).** The model is still ±5–10 °C on a layout it was not fit to. Compare the
*difference* when you try something new.

1. Same load both times, long enough to flatten (10–15 min): the same benchmark or a fixed power
   limit on all four cards. Log with
   `nvidia-smi --query-gpu=index,temperature.gpu,power.draw,fan.speed --format=csv -l 5`.
2. Note the room temperature at the end of each run.
3. Run without the shroud, then with it (or the other way round; the room correction handles drift).
4. On the shroud row press **Test it for real** and type the hottest-GPU temperature and the room
   temperature for both states. It shows measured vs predicted, with the room drift taken out, and
   says whether the result is inside the prediction (band ± 1 °C for the reading).
5. The verdict line: under 3 °C either way means not worth tearing the case apart for.

---

## Scripted demos (local)

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
near 70 % duty. Dies, top to bottom, at full board power: 91.4, 93.1, 93.1 and 88.7 °C. The middle two
are the hot ones. This is the stacked shroud-off soak (hottest 93 °C). The bottom card's fan sees about
40 mm of PSU-shroud clearance and stays near 89 °C. In the network view, look at the slot-gap resistors
on the middle cards.

### Gaps plus a vertical card (anchor A)

One empty slot between the three horizontal cards, fourth card in vertical slot v2, shroud still off.

Say: the empty slot is an open mouth with the brackets off. Hottest die 88.9 °C, all four within 0.1 °C,
about 29 CFM each. This is the spaced shroud-off soak (measured 89 °C). Spacing is a few degrees once
the inlet is not treated as a sharp orifice.

### Rear shroud, 2× NF-A14 industrialPPC-3000

Same layout, shroud on.

Say: one plenum over every bracket, two industrial fans pulling on it. Interior gaps are their own orifices
into that plenum, in parallel with the GPU mouths. Hottest die 79.0 °C. About 58 CFM bypasses the fins
through the two gaps and cools the skins. That is the spaced shroud-on soak. The datasheet static pressure
is 10.52 mmH₂O and the web page says 6.58; the model uses the datasheet and the Monte Carlo spans both.

### Positive pressure, taped

Every case fan and the radiator flipped to intake, seals at level 4–5, shroud on.

Say: seal levels now run 1 = fully open to 5 = sealed; tape is 4–5. Case pressure goes positive,
which cuts recirculation, but the radiator now heats the intake with the CPU. Hottest die 78.8 °C,
within a degree of 79.0. Positive pressure is not where the 10 °C came from.

### Custom Accelerated fan curve

Normal fan directions, shroud on, GPU fans on Custom Accelerated: off at 25 °C, 100 % at 70 °C.

Say: affinity laws, flow with RPM and pressure with RPM squared. Hottest die 73.5 °C, about 42 CFM. One
card in open air on the same curve is 78.6 °C against 88.7 °C stock. This is a software change; do it after
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

## 2. Mike Bradley's Dengen X Station (`?demo=mike-bradley`)

His public build, used with his permission: Corsair 9000D, four RTX PRO 6000 Workstation cards touching,
275 W caps, unified GPU fans, air-cooled Threadripper PRO. Only the end-card temperatures he posted are
measurements; case fans and CPU load are assumptions on the preset.

### As built, fans ~80 %

Say: these cards pull air from underneath and push it out of the top, so four touching cards are four fans
in series. Each card breathes the one below it. Model 47 → 79 °C bottom to top; he posted 49 → 79 °C.

### Fans at 100 %

Say: more air through the column, less rise per card. Model 45 → 70 °C; he posted 49 → 69 °C.

### Full 600 W per card

Say: lift the cap and the column cannot carry it; the top two cards reach the cutoff and throttle. That is
why he runs 275 W.
