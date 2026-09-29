# Bounds check

Nominal solutions. Monte Carlo bands are a separate uncertainty, not these pass/fail limits.

| Check | Result | Detail |
|---|---|---|
| open_air_300w | PASS | single card open air die 82.81 °C (band 75–85, target ~83) |
| anchor_a | PASS | anchor A hottest unthrottled die 86.25 °C (86 ± 3) |
| anchor_b_throttle | PASS | anchor B unthrottled ['99.9', '108.0', '107.9', '86.3'] °C, throttle [True, True, True, False] |
| close_pack_middle_hottest | PASS | close-packed unthrottled dies ['99.9', '108.0', '107.9', '86.3'] °C (indexes 1 and 2 are the middle cards) |
| custom_accelerated_open_air | PASS | custom accelerated curve (0 % at 25 °C → 100 % at 70 °C), open air, die 73.44 °C (under ~75) |
| shroud_raises_flow | PASS | mean blower flow 25.80 CFM shroud off → 26.70 CFM shroud on |
| open_air_rtx-5090-fe | PASS | rtx-5090-fe at 575 W, open air, stock curve: die 75.91 °C (target ~76 ± 5) |
| open_air_rtx-pro-6000-blackwell-workstation | PASS | rtx-pro-6000-blackwell-workstation at 600 W, open air, stock curve: die 76.35 °C (target ~76 ± 5) |
| open_air_rtx-3090-fe | PASS | rtx-3090-fe at 350 W, open air, stock curve: die 68.04 °C (target ~68 ± 5) |
| anchor_c_fans_80 | PASS | Mike Bradley stack, fans 80%: top→bottom ['77.9', '67.1', '56.6', '46.7'] °C (published top 79, bottom 49; rising bottom→top True) |
| anchor_c_fans_100 | PASS | Mike Bradley stack, fans 100%: top→bottom ['69.3', '60.7', '52.5', '44.5'] °C (published top 69, bottom 49; rising bottom→top True) |
| cell:s-stacked__p-high__sh-off__l-sealed | PASS | converged=True, residual=1.92e-08 kg/s, energy error=0.000% |
| cell:s-stacked__p-high__sh-off__l-leaky | PASS | converged=True, residual=3.37e-08 kg/s, energy error=0.000% |
| cell:s-stacked__p-high__sh-on__l-sealed | PASS | converged=True, residual=7.00e-09 kg/s, energy error=0.000% |
| cell:s-stacked__p-high__sh-on__l-leaky | PASS | converged=True, residual=6.14e-09 kg/s, energy error=0.000% |
| cell:s-stacked__p-standard__sh-off__l-sealed | PASS | converged=True, residual=1.32e-08 kg/s, energy error=0.000% |
| cell:s-stacked__p-standard__sh-off__l-leaky | PASS | converged=True, residual=1.85e-08 kg/s, energy error=0.000% |
| cell:stock | PASS | converged=True, residual=1.85e-08 kg/s, energy error=0.000% |
| cell:s-stacked__p-standard__sh-on__l-sealed | PASS | converged=True, residual=5.04e-07 kg/s, energy error=0.000% |
| cell:s-stacked__p-standard__sh-on__l-leaky | PASS | converged=True, residual=3.61e-07 kg/s, energy error=0.000% |
| cell:s-gap1__p-high__sh-off__l-sealed | PASS | converged=True, residual=1.52e-09 kg/s, energy error=0.000% |
| cell:s-gap1__p-high__sh-off__l-leaky | PASS | converged=True, residual=1.77e-09 kg/s, energy error=0.000% |
| cell:s-gap1__p-high__sh-on__l-sealed | PASS | converged=True, residual=1.76e-09 kg/s, energy error=0.000% |
| cell:s-gap1__p-high__sh-on__l-leaky | PASS | converged=True, residual=1.69e-09 kg/s, energy error=0.000% |
| cell:s-gap1__p-standard__sh-off__l-sealed | PASS | converged=True, residual=1.30e-09 kg/s, energy error=0.000% |
| cell:s-gap1__p-standard__sh-off__l-leaky | PASS | converged=True, residual=2.11e-07 kg/s, energy error=0.000% |
| cell:s-gap1__p-standard__sh-on__l-sealed | PASS | converged=True, residual=1.32e-09 kg/s, energy error=0.000% |
| cell:s-gap1__p-standard__sh-on__l-leaky | PASS | converged=True, residual=8.13e-08 kg/s, energy error=0.000% |

Overall: PASS
