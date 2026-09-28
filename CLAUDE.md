# gpu-stack-thermal-sim

Compact airflow + thermal network for air-cooled multi-GPU workstations. Not CFD.
GPU water blocks are out of scope. Units are Celsius. Default ambient 25 °C.

## What matters

- `SPEC.md` is revision 3. Implement that, don't renegotiate it.
- Default build id: `meshify2xl-stefano` (Meshify 2 XL, 3×140 Noctua redux-1700 front intake, 1× rear exhaust assumed, Arctic 360 top exhaust, 4× RTX PRO 6000 Blackwell Max-Q, slots 1/4/7 + vertical v2, shroud on with 2× NF-A14 iPPC-3000, leaky, stock GPU curve).
- The factorial **stock** cell is different: stacked (no empty slot), shroud off, standard, leaky. It is reported as its own row even though it matches one cell.
- Anchor A is gap1 + standard + shroud off + leaky (hottest ~86.5 °C). Anchor B is four horizontal cards, no gaps (middle cards ~140 °C unthrottled, throttle at 90).
- Tuned knobs are global / per card type in `gpusim/calib.py`. Never per sweep cell.
- Presets are YAML. Every number needs a source or `approximate` plus an assumption (`gpusim/cite.py`).

## Commands

```bash
uv venv && uv pip install -e ".[dev]"
uv run pytest -q
uv run gpusim sweep --build meshify2xl-stefano --mc 200
uv run gpusim ui
```

Results land in `results/meshify2xl-stefano/` and `plots/meshify2xl-stefano/`.
