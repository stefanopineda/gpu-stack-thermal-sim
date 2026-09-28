# Sweep results — Stefano's Meshify 2 XL — 4× RTX PRO 6000 Max-Q

Configurations that do not throttle come first, by hottest die, then mean die. Configurations that throttle follow, by unthrottled hottest die: their throttled dies all sit on the cutoff, so that column cannot separate them.
Lower is better.

Typical accuracy ±5–10 °C absolute. Trust the order more than the number.
GPU water blocks are out of scope.

| Rank | Config | Hottest °C | Unthrottled °C | Mean °C | Case Pa | Throttle |
|---|---|---:|---:|---:|---:|---|
| 1 | `s-gap1__p-standard__sh-on__l-leaky` | 84.2 | 84.2 | 84.2 | -6.4 | False |
| 2 | `s-gap1__p-standard__sh-on__l-sealed` | 84.3 | 84.3 | 84.2 | -12.9 | False |
| 3 | `s-gap1__p-high__sh-on__l-leaky` | 84.7 | 84.7 | 84.7 | 9.5 | False |
| 4 | `s-gap1__p-high__sh-on__l-sealed` | 85.5 | 85.5 | 85.5 | 17.6 | False |
| 5 | `s-gap1__p-standard__sh-off__l-sealed` | 86.4 | 86.4 | 86.3 | -11.6 | False |
| 6 | `s-gap1__p-standard__sh-off__l-leaky` | 86.6 | 86.6 | 86.5 | -3.7 | False |
| 7 | `s-gap1__p-high__sh-off__l-leaky` | 86.6 | 86.6 | 86.5 | 8.3 | False |
| 8 | `s-gap1__p-high__sh-off__l-sealed` | 88.3 | 88.3 | 88.2 | 18.3 | True |
| 9 | `s-stacked__p-standard__sh-on__l-leaky` | 89.5 | 104.2 | 86.3 | -5.4 | True |
| 10 | `s-stacked__p-standard__sh-on__l-sealed` | 89.5 | 104.2 | 86.4 | -11.1 | True |
| 11 | `s-stacked__p-high__sh-on__l-leaky` | 89.6 | 104.6 | 86.6 | 10.6 | True |
| 12 | `s-stacked__p-high__sh-on__l-sealed` | 89.6 | 105.7 | 87.1 | 18.6 | True |
| 13 | `s-stacked__p-high__sh-off__l-leaky` | 89.5 | 108.5 | 87.5 | 9.2 | True |
| 14 | `s-stacked__p-standard__sh-off__l-sealed` | 89.5 | 108.6 | 87.4 | -9.9 | True |
| 15 | `s-stacked__p-standard__sh-off__l-leaky` | 89.5 | 108.8 | 87.5 | -3.1 | True |
| 16 | `stock` | 89.5 | 108.8 | 87.5 | -3.1 | True |
| 17 | `s-stacked__p-high__sh-off__l-sealed` | 89.6 | 110.8 | 88.4 | 19.2 | True |

Open-air reference (not ranked): die 82.8 °C.
