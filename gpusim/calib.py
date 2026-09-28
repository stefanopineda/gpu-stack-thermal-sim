"""Global calibration knobs.

These are fit once, jointly, to three anchors and then frozen:

* one RTX PRO 6000 Blackwell Max-Q in open air at 300 W, stock blower curve,
  die near 83 °C (acceptable band 75–85 °C);
* Stefano anchor A — Meshify 2 XL, three horizontal cards with one empty slot
  between them plus one vertical card, stock curve, no shroud — hottest die
  near 86 °C;
* Stefano anchor B — four horizontal cards, no gaps, stock curve, no shroud —
  unthrottled hottest die at or above the 90 °C cutoff.

Nothing here is allowed to depend on the sweep cell. Per-card numbers are
per card *type*. See docs/CALIBRATION.md.

Blower P–Q, fin geometry, TIM and the Nusselt coefficient are not published
for this card. They are labelled approximations. The stock duty cap (~70%)
and the aggressive curve (100% by 70 °C) follow SPEC rev 3, not an NVIDIA table.
"""

from __future__ import annotations

# Seal step → open-area fraction of the geometric interface, and the orifice
# discharge coefficient used with that opening. This map is an engineering
# assumption (foil tape → bare mesh), covered by the Monte Carlo seal scale.
SEAL_OPEN_FRACTION = {1: 0.002, 2: 0.012, 3: 0.07, 4: 0.28, 5: 0.92}
SEAL_CD = {1: 0.60, 2: 0.62, 3: 0.65, 4: 0.70, 5: 0.80}

# Extra resistance multipliers. Dimensionless, approximate.
OBSTRUCTION_K = {"low": 1.0, "medium": 2.2, "high": 5.5}
CABLE_K = {"clean": 1.0, "cluttered": 2.4}
FILTER_K_AT_REF = {  # Pa / (m³/s)² added on an intake, ~ at 140 mm fan flow
    "none": 0.0,
    "fine": 1.4e4,
    "dense": 4.0e4,
}

# Shared model knobs (not per card).
GLOBAL = {
    # Internal short-circuit from each blower outlet back into the GPU zone
    # when the shroud is off. Small on purpose: most exhaust should leave.
    "recirc_area_m2": 1.1e-4,
    # Plume (just outside the rear slots) dissipates to the room through this area.
    "plume_area_m2": 0.04,
    # Imperfect shroud shell, plenum ↔ room, when the shroud is fitted.
    "shroud_shell_area_m2": 8.0e-4,
    # Fraction of the open rear-slot area that still bypasses into the plenum
    # (empty brackets under the shroud). The rest is baffled by the shroud walls.
    "shroud_bypass_fraction": 0.04,
    # Of the open rear-slot area with the shroud off, this fraction exchanges with the
    # hot exhaust plume. The rest exchanges with room air. A real jet entrains ambient
    # before any of it is pulled back in, so most of a large opening is not pure exhaust.
    "reingest_fraction": 0.22,
    # Bleed orifice on every node so the Jacobian stays nonsingular.
    # ~0.1 CFM at 100 Pa. Numerical regularisation, not a modelled leak path.
    "bleed_area_m2": 8.0e-6,
    "nu_C": 0.100,
    "nu_m": 0.60,
    # Drive cage parked in the front intake.
    "drive_cage_k": 6.0e4,
    # PSU fan pulling from the chamber instead of the floor.
    "psu_fan_up_k_mult": 1.45,
    # Direct front-to-GPU spill (Meshify) vs a mixed mid-tower.
    "spill_area_direct_m2": 0.045,
    "spill_area_mixed_m2": 0.012,
    # Lowest-card bypass from the GPU zone around the PSU shroud lip.
    "bottom_bypass_m2": 1.15e-3,
    "bottom_bypass_open_psu_m2": 2.2e-3,
}

# Per card type. Overridden nowhere by cell index.
CARD = {
    "rtx-pro-6000-blackwell-maxq": {
        # ~62 CFM free air and a high dead-head pressure. Professional blowers
        # are pressure-biased; neither intercept is on the NVIDIA datasheet.
        "qmax_m3s": 0.0292,
        "pmax_pa": 720.0,
        "rpm_max": 5000.0,
        "rpm_min": 1200.0,
        "r_tim": 0.062,  # K/W die → heatsink metal, TIM + spreading
        "r_mem": 0.42,  # K/W memory → heatsink
        "mem_share": 0.12,
        "dh_m": 0.0017,
        "fin_area_m2": 0.095,
        "channel_area_m2": 0.00115,
        "channel_k": 1.6e5,  # heatsink core, Pa/(m³/s)²
        "r_ext": 3.2,  # K/W heatsink → surrounding air via shroud and backplate
        "capture_g0_mm": 9.0,
        "inlet_width_m": 0.085,
        "inlet_eye_m2": 0.0017,
        "bracket_vent_m2": 0.00145,
        "core_ref_mhz": 2286.0,
        "memory_ref_mhz": 1750.0,
    },
    "custom-blower-300w": {
        # Template twin of the Max-Q blower, so a user-added 300 W blower
        # starts from the same calibrated physics and can be edited.
        "qmax_m3s": 0.0292,
        "pmax_pa": 720.0,
        "rpm_max": 5000.0,
        "rpm_min": 1200.0,
        "r_tim": 0.062,
        "r_mem": 0.42,
        "mem_share": 0.12,
        "dh_m": 0.0017,
        "fin_area_m2": 0.095,
        "channel_area_m2": 0.00115,
        "channel_k": 1.6e5,
        "r_ext": 3.2,
        "capture_g0_mm": 9.0,
        "inlet_width_m": 0.085,
        "inlet_eye_m2": 0.0017,
        "bracket_vent_m2": 0.00145,
        "core_ref_mhz": 2000.0,
        "memory_ref_mhz": 1750.0,
    },
}


def card_tuning(card_id: str) -> dict:
    if card_id not in CARD:
        raise KeyError(
            f"No calibration block for card '{card_id}'. "
            "Add one to gpusim/calib.py (global, not per sweep cell)."
        )
    return dict(CARD[card_id])


def merged_global(overrides: dict | None = None) -> dict:
    out = dict(GLOBAL)
    if overrides:
        out.update(overrides)
    return out
