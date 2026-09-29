# Sweep results — Stefano's Meshify 2 XL — 4× RTX PRO 6000 Max-Q

Configurations that do not throttle come first, by hottest die, then mean die. Configurations that throttle follow, by unthrottled hottest die: their throttled dies all sit on the cutoff, so that column cannot separate them.
Lower is better.

Typical accuracy ±5–10 °C absolute. Trust the order more than the number.
GPU water blocks are out of scope.

| Rank | Config | Hottest °C | Unthrottled °C | Mean °C | Case Pa | Throttle |
|---|---|---:|---:|---:|---:|---|
| 1 | `s-gap1__p-standard__sh-on__l-sealed` | 83.9 | 83.9 | 83.9 | -1.8 | False |
| 2 | `s-gap1__p-standard__sh-on__l-leaky` | 84.0 | 84.0 | 84.0 | -0.9 | False |
| 3 | `s-gap1__p-high__sh-on__l-leaky` | 84.5 | 84.5 | 84.4 | 13.5 | False |
| 4 | `s-gap1__p-high__sh-on__l-sealed` | 85.5 | 85.5 | 85.4 | 19.5 | False |
| 5 | `s-gap1__p-standard__sh-off__l-sealed` | 85.9 | 85.9 | 85.9 | -0.9 | False |
| 6 | `s-gap1__p-high__sh-off__l-leaky` | 86.2 | 86.2 | 86.2 | 12.1 | False |
| 7 | `s-gap1__p-standard__sh-off__l-leaky` | 86.2 | 86.2 | 86.2 | -0.6 | False |
| 8 | `s-gap1__p-high__sh-off__l-sealed` | 88.2 | 88.2 | 88.2 | 20.0 | True |
| 9 | `s-stacked__p-standard__sh-on__l-sealed` | 89.6 | 103.6 | 86.2 | -0.6 | True |
| 10 | `s-stacked__p-standard__sh-on__l-leaky` | 89.6 | 103.9 | 86.3 | -0.7 | True |
| 11 | `s-stacked__p-high__sh-on__l-leaky` | 89.6 | 104.2 | 86.5 | 14.4 | True |
| 12 | `s-stacked__p-high__sh-on__l-sealed` | 89.6 | 105.6 | 87.0 | 20.2 | True |
| 13 | `s-stacked__p-standard__sh-off__l-sealed` | 89.5 | 107.9 | 87.2 | 0.2 | True |
| 14 | `s-stacked__p-high__sh-off__l-leaky` | 89.5 | 108.1 | 87.4 | 12.9 | True |
| 15 | `s-stacked__p-standard__sh-off__l-leaky` | 89.5 | 108.2 | 87.3 | -0.4 | True |
| 16 | `stock` | 89.5 | 108.2 | 87.3 | -0.4 | True |
| 17 | `s-stacked__p-high__sh-off__l-sealed` | 89.6 | 110.7 | 88.4 | 20.5 | True |

Open-air reference (not ranked): die 82.8 °C.
