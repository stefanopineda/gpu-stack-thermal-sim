# What to test on the real machine

The model is a hypothesis generator. These are the cells most worth a Saturday
on Stefano's Meshify, cheapest and most informative first. Deltas are versus
the stock cell (stacked, standard pressure, shroud off, leaky), whose
unthrottled hottest die is 108.8 °C.

Monte Carlo sample count for the bands below: 200.

## 1. `s-gap1__p-standard__sh-off__l-sealed`

Predicted unthrottled hottest die 86.4 °C (-22.4 °C vs stock). Throttled equilibrium 86.4 °C. Monte Carlo hottest-die band 76.8–103.0 °C.

Why it should move: Move cards apart by one slot. No parts. Tape panel gaps. Reversible, fiddly.

## 2. `s-gap1__p-standard__sh-on__l-leaky`

Predicted unthrottled hottest die 84.3 °C (-24.5 °C vs stock). Throttled equilibrium 84.3 °C. Monte Carlo hottest-die band 74.5–101.2 °C.

Why it should move: Move cards apart by one slot. No parts. Fit the rear shroud and its two fans. Hardware already in hand.

## 3. `s-gap1__p-standard__sh-on__l-sealed`

Predicted unthrottled hottest die 84.3 °C (-24.4 °C vs stock). Throttled equilibrium 84.3 °C. Monte Carlo hottest-die band 74.6–101.4 °C.

Why it should move: Move cards apart by one slot. No parts. Fit the rear shroud and its two fans. Hardware already in hand. Tape panel gaps. Reversible, fiddly.

## 4. `s-gap1__p-high__sh-on__l-leaky`

Predicted unthrottled hottest die 84.8 °C (-24.0 °C vs stock). Throttled equilibrium 84.8 °C. Monte Carlo hottest-die band 75.0–101.7 °C.

Why it should move: Move cards apart by one slot. No parts. Fit the rear shroud and its two fans. Hardware already in hand. Flip the radiator and the rear fan to intake. A few screws.

## 5. `s-gap1__p-high__sh-on__l-sealed`

Predicted unthrottled hottest die 85.7 °C (-23.0 °C vs stock). Throttled equilibrium 85.7 °C. Monte Carlo hottest-die band 76.1–102.6 °C.

Why it should move: Move cards apart by one slot. No parts. Fit the rear shroud and its two fans. Hardware already in hand. Flip the radiator and the rear fan to intake. A few screws. Tape panel gaps. Reversible, fiddly.

## Suggested order

1. Spacing (gap1, shroud still off). Confirms anchor A against anchor B with no new parts.
2. Shroud on, same spacing. Isolates the plenum fans.
3. GPU fan curve to maxq_aggressive, which is not a sweep factor — do it on the winning geometry.
4. Only then tape the case or flip the radiator. Those fight each other (CPU heat vs recirculation).

Confidence is higher for the order than for the absolute degree. If two neighbouring
cells differ by less than about 3 °C, treat them as a tie until the bench says otherwise.
