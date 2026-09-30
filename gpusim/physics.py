"""Air properties, fan laws, orifice losses, and the rough GPU power model.

Losses follow the standard orifice relation (Idelchik, Handbook of Hydraulic
Resistance; no page numbers are invented here):

    ΔP = ρ / (2 Cd² A²) · Q |Q|

Fan pressure and flow scale with RPM by the affinity laws Q ∝ N, P ∝ N².
"""

from __future__ import annotations

import math

import numpy as np

CP_AIR = 1007.0  # J/(kg·K)
PR_AIR = 0.70
R_SPECIFIC = 287.058  # J/(kg·K)
MMH2O_TO_PA = 9.80665
CFM_PER_M3S = 2118.88


def ambient_pressure_pa(altitude_m: float) -> float:
    """Barometric pressure. Scale height 8434 m is the isothermal approximation."""
    return 101325.0 * math.exp(-float(altitude_m) / 8434.0)


def air_density(temp_c: float, altitude_m: float = 0.0) -> float:
    temp_k = float(temp_c) + 273.15
    return ambient_pressure_pa(altitude_m) / (R_SPECIFIC * temp_k)


def air_viscosity(temp_c: float) -> float:
    """Sutherland's law for dry air, Pa·s."""
    t_k = float(temp_c) + 273.15
    return 1.716e-5 * (t_k / 273.15) ** 1.5 * (273.15 + 110.4) / (t_k + 110.4)


def air_conductivity(temp_c: float) -> float:
    """Rough linear fit around room temperature, W/(m·K). Approximate."""
    return 0.0242 + 7.4e-5 * float(temp_c)


def orifice_k(area_m2: float, rho: float, cd: float = 0.65) -> float:
    """Quadratic loss coefficient so ΔP = k Q |Q|, with Q in m³/s and ΔP in Pa."""
    cda = max(cd * float(area_m2), 1e-9)
    return float(rho) / (2.0 * cda * cda)


def shroud_mouth_loss(
    aperture_mm: float,
    duct_gap_mm: float,
    span_m: float,
    length_m: float,
    rho: float,
    mu: float,
    cd: float,
) -> tuple[float, float, float] | None:
    """Rear-shroud mouth: orifice on the aperture plus laminar slit friction.

    The aperture is the opening the plenum actually sees,
    ``A = (aperture_mm / 1000) × span``. ``k`` is Idelchik's sharp-edge
    orifice, ``ΔP = ρ Q|Q| / (2 Cd² A²)``. The duct term is plane-Poiseuille
    flow along the card, ``ΔP = 12 μ L Q / (g³ W)``, with ``g`` the mechanical
    gap the air travels through and ``W`` the span. Returns ``(k, k_lin, area)``
    or None when the aperture is closed.
    """
    span = max(float(span_m), 1e-6)
    aperture_m = max(float(aperture_mm), 0.0) / 1000.0
    area = aperture_m * span
    if area < 1e-8:
        return None
    k = orifice_k(area, rho, cd)
    duct_m = max(float(duct_gap_mm), 0.3) / 1000.0
    k_lin = 12.0 * float(mu) * max(float(length_m), 0.01) / (duct_m**3 * span)
    return float(k), float(k_lin), float(area)


def gap_channel_h(
    mass_kg_s: float,
    rho: float,
    mu: float,
    k_air: float,
    gap_m: float,
    span_m: float,
    nu_c: float,
    nu_m: float,
) -> float:
    """Convective coefficient on one wall of a parallel-plate gap, W/(m²·K).

    ``Nu = C Re^m Pr^(1/3)``, ``Dh = 2 g``. ``C`` and ``m`` are assumed
    (``skin_nu_C``, ``skin_nu_m``); they are not the fin-channel fit.
    """
    gap = max(float(gap_m), 1e-5)
    span = max(float(span_m), 1e-6)
    if mass_kg_s <= 1e-8 or rho <= 0 or mu <= 0:
        return 0.0
    area = gap * span
    dh = 2.0 * gap
    velocity = (float(mass_kg_s) / float(rho)) / area
    re = max(float(rho) * velocity * dh / float(mu), 1.0)
    nu = float(nu_c) * (re ** float(nu_m)) * (PR_AIR ** (1.0 / 3.0))
    return float(nu * k_air / dh)


def skin_couple_ua(
    gap_m: float,
    area_m2: float,
    t_a_c: float,
    t_b_c: float,
    emissivity: float,
    k_air: float,
) -> float:
    """Conduction plus radiation across a thin air gap between two skins, W/K.

    Two infinite gray planes, view factor 1. Conduction is ``k_air / g``.
    No flow term: a taped crack does not carry useful convection.
    """
    gap = max(float(gap_m), 3.0e-4)
    area = max(float(area_m2), 0.0)
    if area <= 0.0:
        return 0.0
    eps = min(max(float(emissivity), 0.05), 0.98)
    eps_eff = 1.0 / (2.0 / eps - 1.0)
    ta = float(t_a_c) + 273.15
    tb = float(t_b_c) + 273.15
    h_rad = eps_eff * 5.670374419e-8 * (ta + tb) * (ta * ta + tb * tb)
    h_cond = float(k_air) / gap
    return float((h_cond + h_rad) * area)


def m3h_to_m3s(value: float) -> float:
    return float(value) / 3600.0


def m3s_to_cfm(value: float) -> float:
    return float(value) * CFM_PER_M3S


def quadratic_curve(qmax_m3h: float, pmax_mmh2o: float, n: int = 9) -> list[list[float]]:
    """Generic fan curve P = Pmax (1 − (Q/Qmax)²). Shape is an assumption when
    a manufacturer publishes only the two intercepts.
    """
    pts = []
    for i in range(n):
        frac = i / (n - 1)
        q = qmax_m3h * frac
        p = pmax_mmh2o * (1.0 - frac * frac)
        pts.append([round(q, 4), round(max(p, 0.0), 4)])
    return pts


def fan_tables(
    points_m3h_mmh2o: list[list[float]] | np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Return (Q m³/s, P Pa) sorted by rising flow. The table is at the fan's rated RPM."""
    arr = np.asarray(points_m3h_mmh2o, dtype=float)
    if arr.ndim != 2 or arr.shape[1] != 2 or len(arr) < 2:
        raise ValueError("fan curve needs at least two [m3/h, mmH2O] points")
    q = arr[:, 0] / 3600.0
    p = arr[:, 1] * MMH2O_TO_PA
    order = np.argsort(q)
    q = q[order]
    p = np.maximum(p[order], 0.0)
    # Drop duplicate flow stations so interpolation slopes stay finite.
    keep = np.concatenate([[True], np.diff(q) > 1e-9])
    return q[keep], p[keep]


def scale_parallel(q: np.ndarray, p: np.ndarray, count: int) -> tuple[np.ndarray, np.ndarray]:
    count = max(int(count), 1)
    if count == 1:
        return q, p
    return q * count, p


def fan_pressure(
    flow_m3s: float,
    q_tab: np.ndarray | None,
    p_tab: np.ndarray | None,
    rpm: float,
    rpm_ref: float,
) -> tuple[float, float]:
    """Pressure rise (Pa) and dP/dQ at a signed volumetric flow.

    Q > 0 is the fan's forward direction. Reverse flow produces no pressure rise
    (the impeller is treated as a passive blockage via the branch loss).
    """
    if q_tab is None or p_tab is None or rpm_ref <= 0.0 or rpm <= 0.0:
        return 0.0, 0.0
    # Reverse flow: no fan pressure (the branch loss is the blockage).
    # Q = 0 is the dead-head point and must return Pmax, not zero.
    if flow_m3s < 0.0:
        return 0.0, 0.0
    speed = rpm / rpm_ref
    q_ref = flow_m3s / speed
    q_max = float(q_tab[-1])
    if q_ref >= q_max:
        return 0.0, 0.0
    i = int(np.searchsorted(q_tab, q_ref) - 1)
    i = max(0, min(i, len(q_tab) - 2))
    dq = float(q_tab[i + 1] - q_tab[i])
    slope_ref = float(p_tab[i + 1] - p_tab[i]) / dq if dq > 1e-12 else 0.0
    p_ref = float(p_tab[i]) + slope_ref * (q_ref - float(q_tab[i]))
    if p_ref <= 0.0:
        return 0.0, 0.0
    # P = P_ref * speed² and Q = Q_ref * speed → dP/dQ = slope_ref * speed.
    return p_ref * speed * speed, slope_ref * speed


def duty_at(curve: list[list[float]], temp_c: float) -> float:
    """Piecewise-linear fan duty versus die temperature. Duty is a fraction of max RPM."""
    pts = sorted((float(t), float(d)) for t, d in curve)
    temp = float(temp_c)
    if temp <= pts[0][0]:
        return float(np.clip(pts[0][1], 0.0, 1.0))
    if temp >= pts[-1][0]:
        return float(np.clip(pts[-1][1], 0.0, 1.0))
    for (t0, d0), (t1, d1) in zip(pts, pts[1:]):
        if t0 <= temp <= t1:
            span = t1 - t0
            frac = 0.0 if span <= 0 else (temp - t0) / span
            return float(np.clip(d0 + frac * (d1 - d0), 0.0, 1.0))
    return float(np.clip(pts[-1][1], 0.0, 1.0))


def rpm_from_duty(rpm_min: float, rpm_max: float, duty: float) -> float:
    duty = float(np.clip(duty, 0.0, 1.0))
    return float(rpm_min + duty * (rpm_max - rpm_min))


def electrical_power(
    power_limit_w: float,
    core_offset_mhz: float,
    memory_offset_mhz: float,
    undervolt_mv: float,
    core_ref_mhz: float,
    memory_ref_mhz: float,
    mem_share: float,
) -> tuple[float, float, float]:
    """Map clock and voltage tweaks onto heat. This is a rough approximation.

    At zero offsets the card is assumed to sit on its power limit under the
    simulated load (a 100% compute load, not idle).

    Shares at stock, summing to 1:
        memory  = mem_share
        static  = 0.18 * (1 - mem_share)
        dynamic = 0.82 * (1 - mem_share)

    Scaling, then clamped to the power limit:
        f_scale   = clip(1 + core_offset / f_ref, 0.50, 1.35)
        v_scale   = clip(1 + undervolt_mV / 1000, 0.70, 1.15)
        mem_scale = clip(1 + mem_offset / mem_ref, 0.50, 1.35)
        P_dyn     ∝ f_scale · v_scale²
        P_static  ∝ v_scale^1.3
        P_mem     ∝ mem_scale

    Undervolt is in millivolts added to a 1.000 V reference, so −100 mV is
    v_scale = 0.90. Returns (P_total, P_die, P_memory) in watts.
    """
    limit = max(float(power_limit_w), 1.0)
    share = float(np.clip(mem_share, 0.02, 0.40))
    rest = 1.0 - share
    f_scale = float(np.clip(1.0 + core_offset_mhz / max(core_ref_mhz, 1.0), 0.50, 1.35))
    v_scale = float(np.clip(1.0 + undervolt_mv / 1000.0, 0.70, 1.15))
    mem_scale = float(np.clip(1.0 + memory_offset_mhz / max(memory_ref_mhz, 1.0), 0.50, 1.35))
    p_mem = share * limit * mem_scale
    p_static = 0.18 * rest * limit * (v_scale**1.3)
    p_dyn = 0.82 * rest * limit * f_scale * (v_scale**2)
    total = min(limit, p_mem + p_static + p_dyn)
    # Keep the memory/die split when the limit clamps the sum.
    raw = p_mem + p_static + p_dyn
    if raw > 1e-9:
        p_mem *= total / raw
    p_die = total - p_mem
    return total, p_die, p_mem


def fin_epsilon(
    mass_kg_s: float,
    rho: float,
    mu: float,
    k_air: float,
    nu_c: float,
    nu_m: float,
    dh_m: float,
    fin_area_m2: float,
    channel_area_m2: float,
) -> float:
    """ε for a cold-fluid / hot-wall channel, Nu = C Re^m Pr^(1/3).

    C and m lump fin efficiency and developing-channel effects. They are global
    calibration knobs, not per-configuration fudge factors. Returns 0 when the
    blower is essentially stalled.
    """
    if mass_kg_s <= 1e-8 or channel_area_m2 <= 0 or dh_m <= 0:
        return 0.0
    velocity = (mass_kg_s / rho) / channel_area_m2
    re = max(rho * velocity * dh_m / mu, 1.0)
    nu = nu_c * (re**nu_m) * (PR_AIR ** (1.0 / 3.0))
    h = nu * k_air / dh_m
    ua = h * fin_area_m2
    ntu = ua / (mass_kg_s * CP_AIR)
    return float(1.0 - math.exp(-min(ntu, 40.0)))
