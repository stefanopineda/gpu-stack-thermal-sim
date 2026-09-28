"""Couple the flow network to the thermal network and, if needed, throttle."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from gpusim.calib import CARD, GLOBAL, card_tuning, global_curve
from gpusim.flow import solve_network
from gpusim.library import Library, get_library
from gpusim.models import BuildCfg
from gpusim.network import ROLE, build_network
from gpusim.physics import duty_at, electrical_power, m3s_to_cfm
from gpusim.thermal import solve_thermal


@dataclass
class CardReport:
    id: str
    slot: str
    card: str
    power_w: float
    power_unthrottled_w: float
    t_die_c: float
    t_die_unthrottled_c: float
    t_mem_c: float
    t_in_c: float
    t_exh_c: float
    flow_m3s: float
    flow_cfm: float
    mass_kg_s: float
    duty: float
    throttle: bool
    gap_mm: float
    gap_state: str
    cooler: str = "blower"
    fan_curve: str = "stock"
    thermal: dict | None = None


@dataclass
class Solution:
    build_id: str
    cards: list[CardReport]
    case_pressure_pa: float
    gpu_pressure_pa: float
    residual_kg_s: float
    node_residual: dict[str, float]
    energy_error: float
    heat_w: float
    enthalpy_w: float
    converged: bool
    iterations: int
    solve_time_s: float
    branches: list[dict] = field(default_factory=list)
    pressures: dict[str, float] = field(default_factory=dict)
    node_temp: dict[str, float] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    plume: list[dict] = field(default_factory=list)
    advection_residual_kg_s: float = 0.0

    @property
    def hottest_die(self) -> float:
        return max(c.t_die_c for c in self.cards)

    @property
    def hottest_unthrottled(self) -> float:
        return max(c.t_die_unthrottled_c for c in self.cards)

    @property
    def mean_die(self) -> float:
        return sum(c.t_die_c for c in self.cards) / len(self.cards)

    def to_dict(self) -> dict:
        return {
            "build_id": self.build_id,
            "case_pressure_pa": self.case_pressure_pa,
            "gpu_pressure_pa": self.gpu_pressure_pa,
            "residual_kg_s": self.residual_kg_s,
            "node_residual": self.node_residual,
            "energy_error": self.energy_error,
            "heat_w": self.heat_w,
            "enthalpy_w": self.enthalpy_w,
            "converged": self.converged,
            "iterations": self.iterations,
            "solve_time_s": self.solve_time_s,
            "hottest_die_c": self.hottest_die,
            "hottest_unthrottled_c": self.hottest_unthrottled,
            "mean_die_c": self.mean_die,
            "any_throttle": any(c.throttle for c in self.cards),
            "cards": [c.__dict__ for c in self.cards],
            "branches": self.branches,
            "pressures": self.pressures,
            "node_temp": self.node_temp,
            "notes": self.notes,
            "plume": self.plume,
            "advection_residual_kg_s": self.advection_residual_kg_s,
        }


def prepare_sample(build: BuildCfg, sample: dict | None = None, library: Library | None = None) -> dict:
    merged = dict(GLOBAL)
    extra_cards = {}
    if sample:
        extra_cards = sample.get("cards", {})
        for key, value in sample.items():
            if key != "cards":
                merged[key] = value
    cards = {}
    for gpu in build.gpus:
        base = card_tuning(gpu.card, library)
        base.update(extra_cards.get(gpu.card, {}))
        cards[gpu.card] = base
    merged["cards"] = cards
    return merged


def _curve_for(gpu, card_model) -> list[list[float]]:
    if gpu.fan_curve == "custom":
        if not gpu.custom_curve:
            raise ValueError(f"{gpu.id} uses a custom fan curve but no points were given")
        return gpu.custom_curve
    curves = card_model.fan_curves
    if gpu.fan_curve in curves:
        return curves[gpu.fan_curve]
    shared = global_curve(gpu.fan_curve)
    if shared is not None:
        return shared
    raise ValueError(
        f"{gpu.id} fan curve '{gpu.fan_curve}' is not on card '{card_model.id}'. "
        "Use stock, custom_accelerated, or custom."
    )


def _powers(build: BuildCfg, sample: dict, limits: dict[str, float] | None = None):
    out = {}
    for gpu in build.gpus:
        params = sample["cards"][gpu.card]
        limit = gpu.power_limit_w if limits is None else limits.get(gpu.id, gpu.power_limit_w)
        total, die, mem = electrical_power(
            limit,
            gpu.core_clock_offset_mhz,
            gpu.memory_clock_offset_mhz,
            gpu.undervolt_mv,
            params["core_ref_mhz"],
            params["memory_ref_mhz"],
            params["mem_share"],
        )
        out[gpu.id] = (total, die, mem)
    return out


def _couple(build, lib: Library, sample, limits, outer: int, duty_init: dict | None, t_amb: float):
    case = None if build.open_air else lib.cases[build.case]
    cards = lib.cards
    duties = dict(duty_init or {})
    for gpu in build.gpus:
        duties.setdefault(gpu.id, 0.62)
    node_temp = {}
    p_init = None
    flow = None
    thermal = None
    net = None
    for _ in range(outer):
        net = build_network(
            build,
            case,
            lib.fans,
            cards,
            lib.radiators,
            duties,
            node_temp,
            sample,
        )
        flow = solve_network(net.branches, net.nodes, p_init=p_init)
        p_init = flow.pressure
        powers = _powers(build, sample, limits)
        thermal = solve_thermal(build, net, flow, powers, duties, sample, t_amb)
        node_temp = thermal.node_temp
        updated = {}
        max_duty = 0.0
        max_temp = 0.0
        for row in thermal.cards:
            gpu = next(g for g in build.gpus if g.id == row.gpu_id)
            target = duty_at(_curve_for(gpu, cards[gpu.card]), row.t_die_c)
            previous = duties[row.gpu_id]
            updated[row.gpu_id] = 0.45 * previous + 0.55 * target
            max_duty = max(max_duty, abs(updated[row.gpu_id] - previous))
            max_temp = max(max_temp, abs(row.t_die_c - node_temp.get(f"_die_{row.gpu_id}", row.t_die_c)))
            node_temp[f"_die_{row.gpu_id}"] = row.t_die_c
        duties = updated
        if max_duty < 0.012:
            break
    assert flow is not None and thermal is not None and net is not None
    return net, flow, thermal, duties


def _reports(build, thermal, duties, unthrottled_die, unthrottled_power, thresholds) -> list[CardReport]:
    by_id = {g.id: g for g in build.gpus}
    reports = []
    for row in thermal.cards:
        gpu = by_id[row.gpu_id]
        t_un = unthrottled_die[row.gpu_id]
        cutoff, threshold = thresholds[row.gpu_id]
        throttled = t_un >= threshold - 1e-6
        reports.append(
            CardReport(
                id=row.gpu_id,
                slot=str(gpu.slot),
                card=gpu.card,
                power_w=row.power_w,
                power_unthrottled_w=unthrottled_power[row.gpu_id],
                t_die_c=row.t_die_c,
                t_die_unthrottled_c=t_un,
                t_mem_c=row.t_mem_c,
                t_in_c=row.t_in_c,
                t_exh_c=row.t_exh_c,
                flow_m3s=row.flow_m3s,
                flow_cfm=m3s_to_cfm(row.flow_m3s),
                mass_kg_s=row.mass_kg_s,
                duty=duties.get(row.gpu_id, row.duty),
                throttle=throttled,
                gap_mm=row.gap_mm,
                gap_state=row.gap_state,
                cooler=(row.detail or {}).get("cooler", "blower"),
                fan_curve=gpu.fan_curve,
                thermal=row.detail,
            )
        )
    return reports


def solve(
    build: BuildCfg,
    library: Library | None = None,
    sample: dict | None = None,
    outer: int = 7,
    do_throttle: bool = True,
) -> Solution:
    """Solve one configuration. Raises if the flow network does not converge."""
    started = time.perf_counter()
    lib = library or get_library()
    merged = prepare_sample(build, sample, lib)
    t_amb = (
        build.ambient_c
        + build.room_reingestion_c
        + float(merged.get("ambient_offset", 0.0))
    )
    net, flow, thermal, duties = _couple(build, lib, merged, None, outer, None, t_amb)
    unthrottled_die = {row.gpu_id: row.t_die_c for row in thermal.cards}
    unthrottled_power = {row.gpu_id: row.power_w for row in thermal.cards}
    thresholds = {}
    for gpu in build.gpus:
        card = lib.cards[gpu.card]
        thresholds[gpu.id] = (card.cutoff_c, card.throttle_c)

    if do_throttle and any(
        unthrottled_die[g.id] > thresholds[g.id][0] + 0.15 for g in build.gpus
    ):
        original = {g.id: g.power_limit_w for g in build.gpus}
        limits = dict(original)
        # Die rise over the card's own inlet air is close to linear in power,
        # so scale each limit by (cutoff − T_in) / (T_die − T_in). Cards that
        # overshoot low are allowed back up, never above their own limit.
        for _ in range(10):
            changed = False
            for row in thermal.cards:
                cutoff = thresholds[row.gpu_id][0]
                t_ref = min(row.t_in_c, cutoff - 5.0)
                current = limits[row.gpu_id]
                too_hot = row.t_die_c > cutoff + 0.25
                too_cold = row.t_die_c < cutoff - 1.0 and current < original[row.gpu_id] - 0.5
                if not (too_hot or too_cold):
                    continue
                ratio = (cutoff - 0.3 - t_ref) / max(row.t_die_c - t_ref, 0.5)
                ratio = min(max(ratio, 0.15), 1.6)
                limits[row.gpu_id] = min(original[row.gpu_id], max(20.0, current * ratio))
                changed = True
            if not changed:
                break
            _, flow, thermal, duties = _couple(
                build, lib, merged, limits, max(outer - 2, 4), duties, t_amb
            )

    reports = _reports(build, thermal, duties, unthrottled_die, unthrottled_power, thresholds)
    branches = []
    for br in net.branches:
        if br.kind == "bleed":
            continue
        q = flow.flow_m3s.get(br.id, 0.0)
        branches.append(
            {
                "id": br.id,
                "a": br.a,
                "b": br.b,
                "k": br.k,
                "flow_m3s": q,
                "flow_cfm": m3s_to_cfm(q),
                "dp_pa": flow.dp.get(br.id, 0.0),
                "mass_kg_s": flow.mass_kg_s.get(br.id, 0.0),
                "kind": br.kind,
                "role": ROLE.get(br.kind, br.kind),
                "label": br.label,
                "fan": br.q_tab is not None and br.rpm > 0,
            }
        )
    for sealed in getattr(net, "sealed", []) or []:
        branches.append(
            {
                "id": sealed["id"],
                "a": sealed["a"],
                "b": sealed["b"],
                "k": None,
                "flow_m3s": 0.0,
                "flow_cfm": 0.0,
                "dp_pa": flow.pressure.get(sealed["a"], 0.0),
                "mass_kg_s": 0.0,
                "kind": "sealed",
                "role": "seal resistance: infinite (solid glass / metal, taped)",
                "label": sealed["label"],
                "fan": False,
            }
        )
    plume = []
    for t in thermal.transfers or []:
        rho = t.get("rho", 1.2) or 1.2
        plume.append(
            {
                **{k: v for k, v in t.items() if k != "rho"},
                "flow_cfm": m3s_to_cfm(t["mass_kg_s"] / rho),
                "t_from_c": thermal.node_temp.get(t["from_node"]),
                "t_to_c": thermal.node_temp.get(t["to_node"]),
                "role": ROLE["plume-ingest"],
            }
        )
        branches.append(
            {
                "id": t["id"],
                "a": t["from_node"],
                "b": t["to_node"],
                "k": None,
                "flow_m3s": t["mass_kg_s"] / rho,
                "flow_cfm": m3s_to_cfm(t["mass_kg_s"] / rho),
                "dp_pa": 0.0,
                "mass_kg_s": t["mass_kg_s"],
                "kind": "plume-ingest",
                "role": ROLE["plume-ingest"],
                "label": (
                    f"{t['upper']} ingests {t['share_of_upper_intake']:.0%} of its fan-side intake "
                    f"from {t['lower']}'s exhaust jet (gap {t['gap_mm']:.1f} mm, φ = {t['phi']:.2f})"
                ),
                "fan": False,
            }
        )
    adv = thermal.advection_residual or {}
    adv_max = max((abs(v) for v in adv.values()), default=0.0)
    notes = [
        "Air-cooled model only. GPU water blocks are out of scope.",
        "Typical accuracy ±5–10 °C absolute; better for ranking than for absolute temperature.",
        "Blower P–Q, fin geometry and TIM are calibrated approximations, not vendor curves.",
    ]
    if build.illustrative_mock:
        notes.append("Illustrative mock — not a measurement or claim about anyone's real build.")
    runaway = [c.id for c in reports if c.t_die_unthrottled_c > 150.0]
    if runaway:
        notes.append(
            f"Unthrottled runaway on {', '.join(runaway)} (> 150 °C): the card is starved and has no steady "
            "state at full power. That number is not physical; read the throttled result."
        )
    if any(t["mass_kg_s"] > 0 for t in thermal.transfers or []):
        notes.append(
            "Stacked flow-through cards: the upper card breathes part of the lower card's exhaust "
            "(plume ingestion, φ(gap) = φ_max·exp(−gap/L))."
        )
    return Solution(
        build_id=build.id,
        cards=reports,
        case_pressure_pa=float(flow.pressure.get("case", flow.pressure.get("gpu", 0.0))),
        gpu_pressure_pa=float(flow.pressure.get("gpu", 0.0)),
        residual_kg_s=flow.residual_max,
        node_residual={k: v for k, v in flow.residual.items() if not str(k).startswith("_")},
        energy_error=thermal.energy_error,
        heat_w=thermal.heat_w,
        enthalpy_w=thermal.enthalpy_w,
        converged=flow.converged,
        iterations=flow.iterations,
        solve_time_s=time.perf_counter() - started,
        branches=branches,
        pressures=flow.pressure,
        node_temp={k: v for k, v in thermal.node_temp.items() if not str(k).startswith("_")},
        notes=notes,
        plume=plume,
        advection_residual_kg_s=adv_max,
    )


def sample_tuning(rng, build: BuildCfg, library: Library | None = None) -> dict:
    """One Monte Carlo draw. Distributions are documented in docs/CALIBRATION.md."""
    def ln(sigma: float) -> float:
        return float(rng.lognormal(0.0, sigma))

    cards = {}
    for gpu in build.gpus:
        base = card_tuning(gpu.card, library)
        base["r_tim"] *= ln(0.10)
        base["r_mem"] *= ln(0.10)
        base["qmax_m3s"] *= ln(0.08)
        base["pmax_pa"] *= ln(0.10)
        base["channel_k"] *= ln(0.15)
        base["fin_area_m2"] *= ln(0.08)
        base["r_ext"] *= ln(0.10)
        cards[gpu.card] = base
    # Datasheet static pressure is 10.52 mmH2O; the web spec page says 6.58.
    ippc_lo = 6.58 / 10.52
    return {
        "cards": cards,
        "nu_C": GLOBAL["nu_C"] * ln(0.12),
        "nu_m": float(min(0.85, max(0.45, GLOBAL["nu_m"] * ln(0.04)))),
        "k_scale": ln(0.18),
        "seal_scale": ln(0.20),
        "ambient_offset": float(rng.normal(0.0, 0.8)),
        "ippc_p_scale": float(rng.uniform(ippc_lo, 1.0)),
        "recirc_area_m2": GLOBAL["recirc_area_m2"] * ln(0.25),
        "plume_phi_max": float(rng.uniform(0.70, 0.95)),
        "plume_length_mm": GLOBAL["plume_length_mm"] * ln(0.25),
    }


def solve_monte_carlo(build: BuildCfg, n: int = 200, seed: int = 12345, library=None, outer: int = 4):
    import numpy as np

    rng = np.random.default_rng(seed)
    lib = library or get_library()
    rows = []
    for _ in range(n):
        draw = sample_tuning(rng, build, lib)
        # Uncertainty bands are on the unthrottled coupled solution (duty still iterates).
        sol = solve(build, lib, draw, outer=outer, do_throttle=False)
        rows.append(sol)
    return rows


def copy_build(build: BuildCfg) -> BuildCfg:
    return build.model_copy(deep=True)
