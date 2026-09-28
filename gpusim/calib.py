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
follows SPEC rev 3 and the custom_accelerated curve (0 % at 25 °C → 100 % at
70 °C) follows the rev 4 brief. Neither is an NVIDIA table.

Rev 4 adds flow-through cards (RTX PRO 6000 Blackwell Workstation Edition,
RTX 5090 FE, RTX 3090 FE). Their blocks are per card type and set only
against a single-card open-air review temperature; they were not used to
move the Max-Q anchors.
"""

from __future__ import annotations

# Seal level → open-area fraction of an interface's geometric area, and the
# orifice discharge coefficient for that opening. Rev 4 direction: 1 is open,
# 5 is sealed (rev 3 was the reverse). Concrete percentages:
#   1 fully open (panel off, no filter)                       100 %
#   2 open grille / missing slot covers / bare coarse mesh      70 %
#   3 typical mesh panel with a dust filter                     45 %
#   4 restricted: seams, small gaps, vents in a solid panel      5 %
#   5 sealed: solid glass or metal, taped                         0 %  (no branch, R = ∞)
# The percentages are engineering assumptions, covered by the Monte Carlo
# seal-area scale. The geometric areas live on each case preset.
SEAL_OPEN_FRACTION = {1: 1.00, 2: 0.70, 3: 0.45, 4: 0.05, 5: 0.0}
SEAL_CD = {1: 0.80, 2: 0.72, 3: 0.65, 4: 0.62, 5: 0.60}
SEAL_NAMES = {
    1: "fully open",
    2: "open grille / missing covers",
    3: "typical mesh + filter",
    4: "restricted (seams, small gaps)",
    5: "sealed (solid glass / metal, taped)",
}
# Used when a build does not list an interface. Side 5 = solid glass or metal.
DEFAULT_SEALS = {"front": 3, "top": 3, "bottom": 4, "side": 5, "seams": 4, "rear_slots": 3}

# Internal resistance multipliers. They multiply k (ΔP = k Q|Q|) on the
# internal branches: GPU zone → main case volume, and the CPU cooler exit.
# low: open interior, drive cages out, nothing between the front fans and the
# cards. medium: a drive cage or a big tower cooler shadowing part of the path.
# high: cages, cables and brackets in the way. Approximate, not measured.
OBSTRUCTION_K = {"low": 1.0, "medium": 2.5, "high": 6.0}
# clean: cables routed behind the tray. cluttered: bundles in the GPU zone.
CABLE_K = {"clean": 1.0, "cluttered": 2.0}
# Cables in the GPU zone also lie across card inlet slits. k multiplier on
# every card inlet branch. Approximate.
CABLE_INLET_K = {"clean": 1.0, "cluttered": 1.35}
FILTER_K_AT_REF = {  # Pa / (m³/s)² added on an intake, ~ at 140 mm fan flow
    "none": 0.0,
    "fine": 1.4e4,
    "dense": 4.0e4,
}

# GPU fan curves that are not per card. Duty is a fraction of max fan RPM.
# custom_accelerated: off at 25 °C, linear to 100 % at 70 °C (rev 4 brief).
# It replaces rev 3's `maxq_aggressive`, which is accepted as an alias.
GLOBAL_FAN_CURVES = {
    "custom_accelerated": [[25.0, 0.0], [70.0, 1.0]],
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
    # Plume ingestion between stacked cards (rev 4 item 12). A card whose
    # exhaust leaves upward (flow-through) sends a jet at the fan face of the
    # card above. That card draws a fraction φ of its fan-side intake mass
    # straight from the jet instead of from the mixed GPU zone:
    #     φ(g) = plume_phi_max · exp(−g / plume_length_mm)
    # g is the air gap between the two cards. Capped by the jet's own mass.
    # A free jet from a ~10 cm slot spreads and entrains room air over a few
    # centimetres; 40 mm is the e-folding length assumed here. Approximate.
    "plume_phi_max": 0.85,
    "plume_length_mm": 40.0,
    # Series duct between stacked flow-through cards (rev 4.1). The lower
    # card's backplate cutout breathes straight into the fans above through
    # area = cutout · exp(−gap / stack_length_mm). stack_cd lumps the losses of
    # the cutout, the fin exit and the fan hub. Fit to Mike Bradley's published
    # 4× RTX PRO 6000 Workstation stack (touching, 275 W): top card 79 °C at
    # ~80 % fans, 69 °C at 100 %. Global, not per cell. See docs/CALIBRATION.md.
    "stack_length_mm": 8.0,
    "stack_cd": 0.25,
    # Tower CPU cooler fin stack, Pa/(m³/s)². ~20 Pa at 0.028 m³/s (60 CFM).
    # Approximate, typical of a dual-tower 140 mm heatsink.
    "cpu_heatsink_k": 2.5e4,
    # Cooler outlet back into the case volume (the air spreads out behind the
    # tower). Divided by the internal k multipliers above.
    "cpu_exit_area_m2": 0.03,
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
    # Flow-through (axial) cards. Same field meanings as the blowers, plus the
    # exhaust that leaves up through the backplate side:
    #   exit_width_m  width of the flow-through region, × the gap above = slit
    #   exit_area_m2  the backplate cutout itself (ceiling on that slit)
    # Fan intercepts, fin geometry and TIM are not published. They are set so
    # one card in open air, stock curve, lands on a review temperature (see
    # docs/CALIBRATION.md). They do not touch the Max-Q anchors.
    # PRO 6000 Workstation and 5090 FE share the cooler (Puget: "housing nearly
    # identical"), so they share every cooler number. Only the fit to the 5090
    # FE review temperature set fin_area; no PRO 6000 load temperature exists.
    "rtx-pro-6000-blackwell-workstation": {
        "qmax_m3s": 0.062,  # two axial fans, ~130 CFM free air at 100 %
        "pmax_pa": 95.0,
        "rpm_max": 3000.0,
        "rpm_min": 0.0,
        "r_tim": 0.032,
        "r_mem": 0.42,
        "mem_share": 0.14,  # 96 GB GDDR7, both sides of the board
        "dh_m": 0.0022,
        "fin_area_m2": 0.80,
        "channel_area_m2": 0.0105,
        "channel_k": 2.2e4,
        "r_ext": 2.4,
        "capture_g0_mm": 9.0,
        "inlet_width_m": 0.24,
        "inlet_eye_m2": 0.019,
        "exit_width_m": 0.22,
        "exit_area_m2": 0.012,
        "bracket_vent_m2": 0.0009,
        "core_ref_mhz": 2617.0,
        "memory_ref_mhz": 1750.0,
    },
    "rtx-5090-fe": {
        "qmax_m3s": 0.062,
        "pmax_pa": 95.0,
        "rpm_max": 3000.0,
        "rpm_min": 0.0,
        "r_tim": 0.032,
        "r_mem": 0.50,
        "mem_share": 0.10,  # 32 GB GDDR7
        "dh_m": 0.0022,
        "fin_area_m2": 0.80,
        "channel_area_m2": 0.0105,
        "channel_k": 2.2e4,
        "r_ext": 2.4,
        "capture_g0_mm": 9.0,
        "inlet_width_m": 0.24,
        "inlet_eye_m2": 0.019,
        "exit_width_m": 0.22,
        "exit_area_m2": 0.012,
        "bracket_vent_m2": 0.0009,
        "core_ref_mhz": 2407.0,
        "memory_ref_mhz": 1750.0,
    },
    "rtx-3090-fe": {
        # One fan on the PCB side pushes through fins and out the bracket; the
        # rear fan pulls through a fin stack past the short PCB and exhausts up.
        "qmax_m3s": 0.058,
        "pmax_pa": 85.0,
        "rpm_max": 3000.0,
        "rpm_min": 0.0,
        "r_tim": 0.050,
        "r_mem": 0.45,
        "mem_share": 0.18,  # 24 GB GDDR6X, both sides of the board
        "dh_m": 0.0022,
        "fin_area_m2": 0.83,
        "channel_area_m2": 0.0100,
        "channel_k": 2.6e4,
        "r_ext": 2.4,
        "capture_g0_mm": 9.0,
        "inlet_width_m": 0.24,
        "inlet_eye_m2": 0.019,
        "exit_width_m": 0.11,
        "exit_area_m2": 0.006,
        "bracket_vent_m2": 0.0016,
        "core_ref_mhz": 1695.0,
        "memory_ref_mhz": 1219.0,
    },
}


def card_tuning(card_id: str, library=None) -> dict:
    """Per-card-type block. A library card may borrow another type's block."""
    if card_id not in CARD and library is not None and card_id in library.cards:
        card = library.cards[card_id]
        if card.calibration_from and card.calibration_from in CARD:
            out = dict(CARD[card.calibration_from])
            out.update({k: float(v) for k, v in (card.tuning_overrides or {}).items() if k in out})
            return out
    if card_id not in CARD:
        raise KeyError(
            f"No calibration block for card '{card_id}'. "
            "Add one to gpusim/calib.py (global, not per sweep cell)."
        )
    return dict(CARD[card_id])


def global_curve(name: str) -> list[list[float]] | None:
    curve = GLOBAL_FAN_CURVES.get(name)
    return [list(p) for p in curve] if curve else None


def merged_global(overrides: dict | None = None) -> dict:
    out = dict(GLOBAL)
    if overrides:
        out.update(overrides)
    return out
