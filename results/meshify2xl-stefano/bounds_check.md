# Bounds check

Nominal solutions. Monte Carlo bands are a separate uncertainty, not these pass/fail limits.

| Check | Result | Detail |
|---|---|---|
| open_air_300w | PASS | single card open air die 82.81 °C (band 75–85, target ~83) |
| anchor_a | PASS | anchor A hottest unthrottled die 86.52 °C (86 ± 3) |
| anchor_b_throttle | PASS | anchor B unthrottled ['100.7', '108.9', '108.7', '87.1'] °C, throttle [True, True, True, False] |
| close_pack_middle_hottest | PASS | close-packed unthrottled dies ['100.7', '108.9', '108.7', '87.1'] °C (indexes 1 and 2 are the middle cards) |
| maxq_aggressive_open_air | PASS | aggressive curve, open air, die 73.44 °C (under ~75) |
| shroud_raises_flow | PASS | mean blower flow 25.68 CFM shroud off → 26.50 CFM shroud on |
| cell:s-stacked__p-high__sh-off__l-sealed | PASS | converged=True, residual=5.03e-08 kg/s, energy error=0.000% |
| cell:s-stacked__p-high__sh-off__l-leaky | PASS | converged=True, residual=3.31e-08 kg/s, energy error=0.000% |
| cell:s-stacked__p-high__sh-on__l-sealed | PASS | converged=True, residual=1.32e-08 kg/s, energy error=0.000% |
| cell:s-stacked__p-high__sh-on__l-leaky | PASS | converged=True, residual=9.31e-09 kg/s, energy error=0.000% |
| cell:s-stacked__p-standard__sh-off__l-sealed | PASS | converged=True, residual=4.43e-07 kg/s, energy error=0.000% |
| cell:s-stacked__p-standard__sh-off__l-leaky | PASS | converged=True, residual=1.65e-09 kg/s, energy error=0.000% |
| cell:stock | PASS | converged=True, residual=1.65e-09 kg/s, energy error=0.000% |
| cell:s-stacked__p-standard__sh-on__l-sealed | PASS | converged=True, residual=8.22e-07 kg/s, energy error=0.001% |
| cell:s-stacked__p-standard__sh-on__l-leaky | PASS | converged=True, residual=8.72e-07 kg/s, energy error=0.000% |
| cell:s-gap1__p-high__sh-off__l-sealed | PASS | converged=True, residual=7.27e-10 kg/s, energy error=0.000% |
| cell:s-gap1__p-high__sh-off__l-leaky | PASS | converged=True, residual=9.52e-10 kg/s, energy error=0.000% |
| cell:s-gap1__p-high__sh-on__l-sealed | PASS | converged=True, residual=1.95e-09 kg/s, energy error=0.000% |
| cell:s-gap1__p-high__sh-on__l-leaky | PASS | converged=True, residual=8.38e-10 kg/s, energy error=0.000% |
| cell:s-gap1__p-standard__sh-off__l-sealed | PASS | converged=True, residual=4.36e-09 kg/s, energy error=0.000% |
| cell:s-gap1__p-standard__sh-off__l-leaky | PASS | converged=True, residual=2.12e-09 kg/s, energy error=0.000% |
| cell:s-gap1__p-standard__sh-on__l-sealed | PASS | converged=True, residual=1.75e-09 kg/s, energy error=0.000% |
| cell:s-gap1__p-standard__sh-on__l-leaky | PASS | converged=True, residual=1.08e-09 kg/s, energy error=0.000% |

Overall: PASS
