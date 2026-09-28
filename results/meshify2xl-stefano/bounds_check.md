# Bounds check

Nominal solutions. Monte Carlo bands are a separate uncertainty, not these pass/fail limits.

| Check | Result | Detail |
|---|---|---|
| open_air_300w | PASS | single card open air die 82.81 °C (band 75–85, target ~83) |
| anchor_a | PASS | anchor A hottest unthrottled die 86.55 °C (86 ± 3) |
| anchor_b_throttle | PASS | anchor B unthrottled ['86.3', '140.4', '142.7', '88.4'] °C, throttle [False, True, True, True] |
| close_pack_middle_hottest | PASS | close-packed unthrottled dies ['86.3', '140.4', '142.7', '88.4'] °C (indexes 1 and 2 are the middle cards) |
| maxq_aggressive_open_air | PASS | aggressive curve, open air, die 73.44 °C (under ~75) |
| shroud_raises_flow | PASS | mean blower flow 26.20 CFM shroud off → 26.98 CFM shroud on |
| cell:s-stacked__p-high__sh-off__l-sealed | PASS | converged=True, residual=4.17e-08 kg/s, energy error=0.000% |
| cell:s-stacked__p-high__sh-off__l-leaky | PASS | converged=True, residual=5.56e-08 kg/s, energy error=0.000% |
| cell:s-stacked__p-high__sh-on__l-sealed | PASS | converged=True, residual=4.14e-07 kg/s, energy error=0.001% |
| cell:s-stacked__p-high__sh-on__l-leaky | PASS | converged=True, residual=3.93e-07 kg/s, energy error=0.001% |
| cell:s-stacked__p-standard__sh-off__l-sealed | PASS | converged=True, residual=6.52e-08 kg/s, energy error=0.000% |
| cell:s-stacked__p-standard__sh-off__l-leaky | PASS | converged=True, residual=1.09e-07 kg/s, energy error=0.000% |
| cell:stock | PASS | converged=True, residual=1.09e-07 kg/s, energy error=0.000% |
| cell:s-stacked__p-standard__sh-on__l-sealed | PASS | converged=True, residual=3.75e-07 kg/s, energy error=0.001% |
| cell:s-stacked__p-standard__sh-on__l-leaky | PASS | converged=True, residual=3.80e-07 kg/s, energy error=0.001% |
| cell:s-gap1__p-high__sh-off__l-sealed | PASS | converged=True, residual=1.07e-08 kg/s, energy error=0.000% |
| cell:s-gap1__p-high__sh-off__l-leaky | PASS | converged=True, residual=9.68e-10 kg/s, energy error=0.000% |
| cell:s-gap1__p-high__sh-on__l-sealed | PASS | converged=True, residual=1.34e-09 kg/s, energy error=0.000% |
| cell:s-gap1__p-high__sh-on__l-leaky | PASS | converged=True, residual=1.35e-09 kg/s, energy error=0.000% |
| cell:s-gap1__p-standard__sh-off__l-sealed | PASS | converged=True, residual=1.63e-09 kg/s, energy error=0.000% |
| cell:s-gap1__p-standard__sh-off__l-leaky | PASS | converged=True, residual=1.05e-09 kg/s, energy error=0.000% |
| cell:s-gap1__p-standard__sh-on__l-sealed | PASS | converged=True, residual=1.07e-08 kg/s, energy error=0.000% |
| cell:s-gap1__p-standard__sh-on__l-leaky | PASS | converged=True, residual=6.51e-09 kg/s, energy error=0.000% |

Overall: PASS
