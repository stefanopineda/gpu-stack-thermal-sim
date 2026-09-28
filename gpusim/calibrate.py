"""Fit the global Nusselt coefficient and TIM resistance to an nvidia-smi log.

The fit uses the same single-card open-air model as the simulator. It does not
invent a per-cell offset. Fan speed is read as a duty fraction (nvidia-smi
reports percent). Rows with missing power or temperature are skipped.

Example capture:

    nvidia-smi --query-gpu=timestamp,index,power.draw,temperature.gpu,temperature.memory,fan.speed,clocks.sm --format=csv -l 1
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import least_squares

from gpusim.calib import GLOBAL, card_tuning
from gpusim.factors import open_air_build
from gpusim.solve import solve


def _columns(frame: pd.DataFrame) -> dict[str, str]:
    lookup = {c.strip().lower(): c for c in frame.columns}
    def pick(*names):
        for name in names:
            if name in lookup:
                return lookup[name]
        return None
    power = pick("power.draw [w]", "power.draw", "power_w")
    temp = pick("temperature.gpu", "temperature.gpu [c]", "t_die_c")
    fan = pick("fan.speed [%]", "fan.speed", "fan_pct")
    mem = pick("temperature.memory", "temperature.memory [c]")
    if power is None or temp is None:
        raise ValueError(f"Log needs power.draw and temperature.gpu columns, got {list(frame.columns)}")
    return {"power": power, "temp": temp, "fan": fan, "mem": mem}


def _parse_number(value) -> float:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    text = str(value).strip().split()[0]
    return float(text)


def load_log(path: str | Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    cols = _columns(frame)
    rows = []
    for _, raw in frame.iterrows():
        try:
            power = _parse_number(raw[cols["power"]])
            temp = _parse_number(raw[cols["temp"]])
        except (TypeError, ValueError):
            continue
        if not np.isfinite(power) or not np.isfinite(temp) or power < 30:
            continue
        duty = 0.7
        if cols["fan"] is not None:
            try:
                duty = np.clip(_parse_number(raw[cols["fan"]]) / 100.0, 0.2, 1.0)
            except (TypeError, ValueError):
                duty = 0.7
        mem = None
        if cols["mem"] is not None:
            try:
                mem = _parse_number(raw[cols["mem"]])
            except (TypeError, ValueError):
                mem = None
        rows.append({"power_w": power, "t_die_c": temp, "duty": float(duty), "t_mem_c": mem})
    if len(rows) < 3:
        raise ValueError("Need at least 3 usable nvidia-smi rows to fit.")
    return pd.DataFrame(rows)


def fit_log(path: str | Path, card: str = "rtx-pro-6000-blackwell-maxq") -> dict:
    """Least squares on log(nu_C) and log(r_tim). Returns the fitted globals."""
    data = load_log(path)
    base_nu = GLOBAL["nu_C"]
    base_r = card_tuning(card)["r_tim"]

    def residual(x):
        nu = float(base_nu * np.exp(x[0]))
        r_tim = float(base_r * np.exp(x[1]))
        errors = []
        for row in data.itertuples(index=False):
            build = open_air_build(card=card, fan_curve="custom", power_w=row.power_w)
            build.gpus[0].custom_curve = [[0.0, row.duty], [120.0, row.duty]]
            sol = solve(
                build,
                sample={"nu_C": nu, "cards": {card: {"r_tim": r_tim}}},
                do_throttle=False,
                outer=4,
            )
            errors.append(sol.cards[0].t_die_c - row.t_die_c)
        return np.array(errors)

    result = least_squares(residual, np.zeros(2), bounds=([-1.2, -1.2], [1.2, 1.2]))
    nu = float(base_nu * np.exp(result.x[0]))
    r_tim = float(base_r * np.exp(result.x[1]))
    return {
        "nu_C": nu,
        "r_tim": r_tim,
        "card": card,
        "rows": int(len(data)),
        "rmse_c": float(np.sqrt(np.mean(result.fun**2))),
        "success": bool(result.success),
        "message": str(result.message),
        "note": (
            "Fit of the global Nusselt prefactor and die-to-heatsink resistance "
            "on the open-air model. Apply by editing gpusim/calib.py; do not paste "
            "the result into a single sweep cell."
        ),
    }
