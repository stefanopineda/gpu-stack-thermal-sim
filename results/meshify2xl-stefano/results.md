# Sweep results — Stefano Meshify 2 XL — 4× RTX PRO 6000 Blackwell Max-Q

Ranked by throttled hottest die, then unthrottled hottest die, then mean die.
Lower is better. Throttled equilibrium sits on the cutoff, so the unthrottled
column is what separates two configs that both hit 90 °C.

Typical accuracy ±5–10 °C absolute. Trust the order more than the number.
GPU water blocks are out of scope.

| Rank | Config | Hottest °C | Unthrottled °C | Mean °C | Case Pa | Throttle |
|---|---|---:|---:|---:|---:|---|
| 1 | `s-gap1__p-standard__sh-on__l-leaky` | 84.3 | 84.3 | 83.7 | -8.0 | False |
| 2 | `s-gap1__p-standard__sh-on__l-sealed` | 84.4 | 84.4 | 83.8 | -14.0 | False |
| 3 | `s-gap1__p-high__sh-on__l-leaky` | 84.9 | 84.9 | 84.2 | 11.0 | False |
| 4 | `s-gap1__p-high__sh-on__l-sealed` | 85.8 | 85.8 | 85.1 | 17.8 | False |
| 5 | `s-gap1__p-standard__sh-off__l-sealed` | 86.5 | 86.5 | 85.8 | -12.5 | False |
| 6 | `s-gap1__p-standard__sh-off__l-leaky` | 86.5 | 86.5 | 85.9 | -5.0 | False |
| 7 | `s-gap1__p-high__sh-off__l-leaky` | 86.7 | 86.7 | 86.1 | 10.4 | False |
| 8 | `s-gap1__p-high__sh-off__l-sealed` | 88.6 | 88.6 | 87.9 | 18.6 | True |
| 9 | `s-stacked__p-standard__sh-on__l-leaky` | 90.1 | 134.2 | 84.9 | -6.7 | True |
| 10 | `s-stacked__p-standard__sh-on__l-sealed` | 90.1 | 134.3 | 84.9 | -12.2 | True |
| 11 | `s-stacked__p-standard__sh-off__l-sealed` | 90.1 | 140.7 | 86.6 | -10.7 | True |
| 12 | `s-stacked__p-standard__sh-off__l-leaky` | 90.1 | 140.5 | 86.6 | -4.1 | True |
| 13 | `stock` | 90.1 | 140.5 | 86.6 | -4.1 | True |
| 14 | `s-stacked__p-high__sh-on__l-leaky` | 90.1 | 134.2 | 85.3 | 12.2 | True |
| 15 | `s-stacked__p-high__sh-off__l-leaky` | 90.1 | 139.9 | 86.7 | 11.4 | True |
| 16 | `s-stacked__p-high__sh-on__l-sealed` | 90.2 | 135.4 | 86.1 | 18.9 | True |
| 17 | `s-stacked__p-high__sh-off__l-sealed` | 90.2 | 142.2 | 88.0 | 19.5 | True |

Open-air reference (not ranked): die 82.8 °C.
