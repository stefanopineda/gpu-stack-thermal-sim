# gpu-stack-thermal-sim

Compact airflow + thermal network for air-cooled multi-GPU workstations. Not CFD.
GPU water blocks are out of scope. Units are Celsius. Default ambient 25 °C.

## What matters

- `SPEC.md` is revision 3. Implement that, don't renegotiate it.
- Default build id: `meshify2xl-stefano` (Meshify 2 XL, 3×140 Noctua redux-1700 front intake, 1× rear exhaust assumed, Arctic 360 top exhaust, 4× RTX PRO 6000 Blackwell Max-Q, slots 1/4/7 + vertical v2, shroud on with 2× NF-A14 iPPC-3000, leaky, stock GPU curve).
- The factorial **stock** cell is different: stacked (no empty slot), shroud off, standard, leaky. It is reported as its own row even though it matches one cell.
- Anchor A is gap1 + standard + shroud off + leaky (hottest 86.5 °C; cards 86.5, 86.5, 86.4, 86.4). Anchor B is four horizontal cards, no gaps (unthrottled 100.7, 108.9, 108.7, 87.1 °C; middle two hottest; throttle at 90). Open air 82.8 °C. Aggressive open air 73.4 °C.
- The blower fan face points **down** (toward the floor / PSU). SPEC's old "inlet faces the previous card's backplate" sentence was a wording error and is corrected in SPEC §3, §4 and §6. Card presets set `inlet_faces` (`floor` | `cpu` | `both`) and `inlet_split`. Max-Q default is `both` / 0.75, approximate (0.25 is a smaller backplate/end opening). Gaps come from the slot map for every card: fan side = card below or `psu_shroud_clearance_mm` (Meshify 40 mm, approximate); backplate side = card above or CPU clearance. Vertical cards use `vertical_inlet_gap_mm` (Meshify 28 mm). No lowest-card bypass branch. Do not add one to force middle-hottest; this orientation already produces it.
- Tuned knobs are global / per card type in `gpusim/calib.py`. Never per sweep cell. Inlet split is on the card YAML, not a sweep-cell fudge. Global knobs were not retuned after the floor-facing inlet change.
- Presets are YAML. Every number needs a source or `approximate` plus an assumption (`gpusim/cite.py`).
- `gpusim sweep` writes `results/<build>/hypothesis_auto.md`. The root `HYPOTHESIS.md` is curated; do not point the sweep at it. Default `--out results` keeps plots in `plots/<build>`. Any other `--out` puts plots in `<out>/plots`.
- UI: three.js r160 ES module is vendored at `gpusim/ui/static/vendor/three.module.js` (no CDN, not `three.min.js`). `gpusim ui` prints the URL and, if 8000 is busy, binds the next free port within +29. Quick start: Meshify, plain `corsair-9000d-sample`, and a separate button for the Mike Bradley illustrative mock. Camera frames the whole case (fans, top radiator, rear shroud, PSU shroud) with the case outline and an intake/exhaust/blanked legend.

## Commands

```bash
uv venv && uv pip install -e ".[dev]"
uv run pytest -q
uv run gpusim sweep --build meshify2xl-stefano --mc 200
uv run gpusim ui
```

Results land in `results/meshify2xl-stefano/` (including `hypothesis_auto.md` and `bounds_check.md`) and `plots/meshify2xl-stefano/`.

Latest sweep (mc 200, seed 12345, floor-facing inlets): best cell gap1 / standard / shroud on / leaky, 84.3 °C all four cards. Stock unthrottled hottest 108.8 °C (per card 100.8, 108.8, 87.1, 86.4), throttled equilibrium ~90 °C. MC bands overlap in the tails (stock 94–129, best gapped 74–101). Bounds check overall PASS. Spacing is still the large nominal effect; a 2 °C shroud delta is inside the noise and does not rescue a stacked layout.
