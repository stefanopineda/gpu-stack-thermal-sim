# What to test on the real machine

The model is a hypothesis generator. These are the cells most worth a Saturday
on Stefano's Meshify, cheapest and most informative first. Deltas are versus
the stock cell (stacked, standard pressure, shroud off, leaky), whose
unthrottled hottest die is 108.8 °C.

Monte Carlo sample count for the bands below: 200.

## 1. `s-gap1__p-standard__sh-off__l-sealed`

Predicted unthrottled hottest die 86.4 °C (-22.5 °C vs stock). Throttled equilibrium 86.4 °C. Monte Carlo hottest-die band 78.0–100.1 °C.

Why it should move: Move cards apart by one slot. No parts. Tape panel gaps. Reversible, fiddly.

## 2. `s-gap1__p-standard__sh-on__l-leaky`

Predicted unthrottled hottest die 84.2 °C (-24.6 °C vs stock). Throttled equilibrium 84.2 °C. Monte Carlo hottest-die band 76.1–97.6 °C.

Why it should move: Move cards apart by one slot. No parts. Fit the rear shroud and its two fans. Hardware already in hand.

## 3. `s-gap1__p-standard__sh-on__l-sealed`

Predicted unthrottled hottest die 84.3 °C (-24.5 °C vs stock). Throttled equilibrium 84.3 °C. Monte Carlo hottest-die band 76.2–97.7 °C.

Why it should move: Move cards apart by one slot. No parts. Fit the rear shroud and its two fans. Hardware already in hand. Tape panel gaps. Reversible, fiddly.

## 4. `s-gap1__p-high__sh-on__l-leaky`

Predicted unthrottled hottest die 84.7 °C (-24.1 °C vs stock). Throttled equilibrium 84.7 °C. Monte Carlo hottest-die band 76.5–98.1 °C.

Why it should move: Move cards apart by one slot. No parts. Fit the rear shroud and its two fans. Hardware already in hand. Flip the radiator and the rear fan to intake. A few screws.

## 5. `s-gap1__p-high__sh-on__l-sealed`

Predicted unthrottled hottest die 85.5 °C (-23.3 °C vs stock). Throttled equilibrium 85.5 °C. Monte Carlo hottest-die band 77.3–99.2 °C.

Why it should move: Move cards apart by one slot. No parts. Fit the rear shroud and its two fans. Hardware already in hand. Flip the radiator and the rear fan to intake. A few screws. Tape panel gaps. Reversible, fiddly.

## Suggested order

1. Spacing (gap1, shroud still off). Confirms anchor A against anchor B with no new parts.
2. Shroud on, same spacing. Isolates the plenum fans.
3. GPU fan curve to custom_accelerated (0 % at 25 °C → 100 % at 70 °C), which is not a sweep factor — do it on the winning geometry.
4. Only then tape the case or flip the radiator. Those fight each other (CPU heat vs recirculation).

Confidence is higher for the order than for the absolute degree. If two neighbouring
cells differ by less than about 3 °C, treat them as a tie until the bench says otherwise.
