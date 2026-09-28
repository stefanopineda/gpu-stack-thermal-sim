# Sweep results — Stefano Meshify 2 XL — 4× RTX PRO 6000 Blackwell Max-Q

Ranked by throttled hottest die, then unthrottled hottest die, then mean die.
Lower is better. Throttled equilibrium sits on the cutoff, so the unthrottled
column is what separates two configs that both hit 90 °C.

Typical accuracy ±5–10 °C absolute. Trust the order more than the number.
GPU water blocks are out of scope.

| Rank | Config | Hottest °C | Unthrottled °C | Mean °C | Case Pa | Throttle |
|---|---|---:|---:|---:|---:|---|
| 1 | `s-gap1__p-standard__sh-on__l-leaky` | 84.3 | 84.3 | 84.2 | -7.8 | False |
| 2 | `s-gap1__p-standard__sh-on__l-sealed` | 84.3 | 84.3 | 84.3 | -13.8 | False |
| 3 | `s-gap1__p-high__sh-on__l-leaky` | 84.8 | 84.8 | 84.8 | 11.2 | False |
| 4 | `s-gap1__p-high__sh-on__l-sealed` | 85.7 | 85.7 | 85.7 | 18.0 | False |
| 5 | `s-gap1__p-standard__sh-off__l-sealed` | 86.4 | 86.4 | 86.4 | -12.3 | False |
| 6 | `s-gap1__p-standard__sh-off__l-leaky` | 86.5 | 86.5 | 86.5 | -4.9 | False |
| 7 | `s-gap1__p-high__sh-off__l-leaky` | 86.7 | 86.7 | 86.7 | 10.5 | False |
| 8 | `s-gap1__p-high__sh-off__l-sealed` | 88.6 | 88.6 | 88.6 | 18.8 | True |
| 9 | `s-stacked__p-standard__sh-on__l-leaky` | 90.0 | 104.2 | 86.6 | -6.6 | True |
| 10 | `s-stacked__p-standard__sh-on__l-sealed` | 90.0 | 104.3 | 86.6 | -12.0 | True |
| 11 | `s-stacked__p-standard__sh-off__l-sealed` | 90.1 | 108.7 | 87.7 | -10.5 | True |
| 12 | `s-stacked__p-high__sh-on__l-leaky` | 90.1 | 104.6 | 86.8 | 12.3 | True |
| 13 | `s-stacked__p-standard__sh-off__l-leaky` | 90.1 | 108.8 | 87.8 | -4.0 | True |
| 14 | `stock` | 90.1 | 108.8 | 87.8 | -4.0 | True |
| 15 | `s-stacked__p-high__sh-off__l-leaky` | 90.1 | 108.6 | 87.8 | 11.6 | True |
| 16 | `s-stacked__p-high__sh-on__l-sealed` | 90.1 | 105.9 | 87.4 | 19.0 | True |
| 17 | `s-stacked__p-high__sh-off__l-sealed` | 90.2 | 111.3 | 88.8 | 19.6 | True |

Open-air reference (not ranked): die 82.8 °C.
