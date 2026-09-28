"""Pressure-based flow network solver.

Unknowns are gauge pressures at internal nodes (ambient is 0). Each branch is

    P_a − P_b = k Q |Q| + k_lin Q − P_fan(Q)

with Q > 0 from a to b. Mass is conserved. The fan map is monotone, so the
scalar branch solve has one root; the node system is a damped Newton iteration
with an analytic Jacobian. Non-convergence raises.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from gpusim.physics import fan_pressure


@dataclass
class Branch:
    id: str
    a: str
    b: str
    k: float
    k_lin: float
    rho: float
    kind: str
    label: str
    q_tab: np.ndarray | None = None
    p_tab: np.ndarray | None = None
    rpm: float = 0.0
    rpm_ref: float = 1.0
    heat_tag: str | None = None


@dataclass
class FlowSolution:
    pressure: dict[str, float]
    flow_m3s: dict[str, float]
    mass_kg_s: dict[str, float]
    residual: dict[str, float]
    residual_max: float
    iterations: int
    converged: bool
    dp: dict[str, float]


def _bracket_root(func, lo: float, hi: float) -> float:
    flo = func(lo)
    fhi = func(hi)
    expand = 0
    while flo > 0 or fhi < 0:
        expand += 1
        if expand > 12:
            # No sign change — return the end with the smaller residual.
            return lo if abs(flo) < abs(fhi) else hi
        span = hi - lo
        lo -= span
        hi += span
        flo = func(lo)
        fhi = func(hi)
    for _ in range(28):
        mid = 0.5 * (lo + hi)
        fm = func(mid)
        if abs(fm) < 1e-10 or (hi - lo) < 1e-12:
            return mid
        if fm > 0:
            hi, fhi = mid, fm
        else:
            lo, flo = mid, fm
    return 0.5 * (lo + hi)


def branch_flow(br: Branch, d_p: float, q_hint: float = 0.0) -> tuple[float, float]:
    """Volumetric flow a→b and dQ/d(P_a−P_b)."""
    k = max(br.k, 1e-6)
    k_lin = max(br.k_lin, 1e-4)

    def f(q: float) -> float:
        p_fan, _ = fan_pressure(q, br.q_tab, br.p_tab, br.rpm, br.rpm_ref)
        return k * q * abs(q) + k_lin * q - p_fan - d_p

    def fp(q: float) -> float:
        _, dp_dq = fan_pressure(q, br.q_tab, br.p_tab, br.rpm, br.rpm_ref)
        return 2.0 * k * abs(q) + k_lin - dp_dq

    q_scale = 0.05
    if br.q_tab is not None and br.rpm_ref > 0:
        q_scale = max(q_scale, float(br.q_tab[-1]) * max(br.rpm, 1.0) / br.rpm_ref)
    q_hi = max(q_scale * 1.5, math_sqrt_term(d_p, k), abs(q_hint) * 2, 0.02)
    q = _bracket_root(f, -q_hi, q_hi)
    deriv = 1.0 / max(fp(q), 1e-5)
    return q, deriv


def math_sqrt_term(d_p: float, k: float) -> float:
    return (abs(d_p) / k) ** 0.5 + 0.01


def solve_network(
    branches: list[Branch],
    node_ids: list[str],
    ambient: str = "amb",
    tol: float = 1e-6,
    max_iter: int = 30,
    p_init: dict[str, float] | None = None,
) -> FlowSolution:
    internals = [n for n in node_ids if n != ambient]
    if not internals:
        return FlowSolution({}, {}, {}, {}, 0.0, 0, True, {})
    index = {n: i for i, n in enumerate(internals)}
    n = len(internals)
    pressure = np.zeros(n)
    if p_init:
        for name, value in p_init.items():
            if name in index:
                pressure[index[name]] = value

    def pack(pvec: np.ndarray) -> tuple[np.ndarray, np.ndarray, dict[str, float], dict[str, float]]:
        residual = np.zeros(n)
        jacobian = np.zeros((n, n))
        flows: dict[str, float] = {}
        masses: dict[str, float] = {}

        def p_of(name: str) -> float:
            if name == ambient:
                return 0.0
            return float(pvec[index[name]])

        for br in branches:
            d_p = p_of(br.a) - p_of(br.b)
            q, dq_ddp = branch_flow(br, d_p)
            flows[br.id] = q
            mass = br.rho * q
            masses[br.id] = mass
            dmd = br.rho * dq_ddp
            # Mass into b is +ṁ, into a is −ṁ, for Q defined a → b.
            if br.b in index:
                residual[index[br.b]] += mass
                if br.a in index:
                    jacobian[index[br.b], index[br.a]] += dmd
                jacobian[index[br.b], index[br.b]] -= dmd
            if br.a in index:
                residual[index[br.a]] -= mass
                jacobian[index[br.a], index[br.a]] -= dmd
                if br.b in index:
                    jacobian[index[br.a], index[br.b]] += dmd
        return residual, jacobian, flows, masses

    flows: dict[str, float] = {}
    masses: dict[str, float] = {}
    residual = np.zeros(n)
    converged = False
    iterations = 0
    for iterations in range(1, max_iter + 1):
        residual, jacobian, flows, masses = pack(pressure)
        nrm = float(np.max(np.abs(residual))) if n else 0.0
        if nrm < tol:
            converged = True
            break
        delta = _pressure_step(jacobian, residual)
        delta = np.clip(delta, -500.0, 500.0)
        accepted = False
        for alpha in (1.0, 0.5, 0.25, 0.12, 0.05):
            trial = pressure + alpha * delta
            r_try, _, flows_try, mass_try = pack(trial)
            if float(np.max(np.abs(r_try))) <= nrm * (1.0 - 0.15 * alpha) + 1e-12:
                pressure = trial
                residual, flows, masses = r_try, flows_try, mass_try
                accepted = True
                break
        if not accepted:
            pressure = pressure + 0.02 * delta
    nrm = float(np.max(np.abs(residual))) if n else 0.0
    if not converged and nrm < tol * 5:
        converged = True
    p_map = {ambient: 0.0}
    p_map.update({name: float(pressure[index[name]]) for name in internals})
    r_map = {name: float(residual[index[name]]) for name in internals}
    r_map[ambient] = float(-sum(r_map.values()))
    dp = {}
    for br in branches:
        dp[br.id] = p_map.get(br.a, 0.0) - p_map.get(br.b, 0.0)
    if not converged:
        worst = max(r_map, key=lambda k: abs(r_map[k]))
        raise RuntimeError(
            f"Flow network did not converge in {max_iter} iterations "
            f"(max |mass residual| = {nrm:.3e} kg/s at '{worst}')."
        )
    return FlowSolution(
        pressure=p_map,
        flow_m3s=flows,
        mass_kg_s=masses,
        residual=r_map,
        residual_max=nrm,
        iterations=iterations,
        converged=True,
        dp=dp,
    )


def _pressure_step(jacobian: np.ndarray, residual: np.ndarray) -> np.ndarray:
    try:
        delta = np.linalg.solve(jacobian, -residual)
        if np.all(np.isfinite(delta)):
            return delta
    except np.linalg.LinAlgError:
        pass
    eye = np.eye(jacobian.shape[0])
    scale = max(float(np.linalg.norm(jacobian)), 1.0)
    lam = 1e-6 * scale
    normal = jacobian.T @ jacobian + lam * eye
    try:
        return np.linalg.solve(normal, -jacobian.T @ residual)
    except np.linalg.LinAlgError:
        return np.linalg.lstsq(jacobian, -residual, rcond=None)[0]
