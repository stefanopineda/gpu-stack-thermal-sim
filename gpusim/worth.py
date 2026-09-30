"""Worth it? — what each single change is worth on the current build.

Every candidate is one change a person could make this evening, applied to
the build as it stands. Each is solved once for the ranking, then (optionally)
under paired Monte Carlo: the same random draw of the uncertain inputs is used
for the build before and after, so the band is on the *difference*, not on two
overlapping absolute temperatures.

The metric is the hottest die, unthrottled (throttling caps the reported
temperature near the limit and would hide the difference). The throttled
value is reported beside it.

A change is flagged "inside the noise" when either
  * the paired 90 % band of the gain crosses zero, or
  * the nominal gain is smaller than NOISE_FLOOR_C.
The floor is an assumption: the model's residuals against measured builds
(anchor C, Mike Bradley's stack: 1.1 °C top card, 2.3 °C bottom card) plus
the run-to-run drift of a real test (room temperature moves about ±1 °C over
an hour). A smaller gain may be real, but neither this model nor one evening's
test can show it reliably.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from gpusim.factors import LEAKAGE_SEALS, layout_slots
from gpusim.layout import is_vertical, sort_gpus
from gpusim.library import Library, get_library
from gpusim.models import BuildCfg, MountCfg
from gpusim.solve import sample_tuning, solve

NOISE_FLOOR_C = 3.0

EFFORT_LABEL = {
    "free": "Free · software",
    "10min": "About 10 min",
    "rebuild": "Rebuild · pull the cards",
}

NOISE_RULE = (
    f"Inside the noise: the paired 90 % band crosses zero, or the gain is under {NOISE_FLOOR_C:.0f} °C "
    "(the model's error against measured builds plus the ±1 °C a room drifts during a test)."
)


@dataclass
class Candidate:
    id: str
    title: str
    detail: str
    effort: str
    build: BuildCfg
    note: str = ""
    framing: str = ""
    tags: list[str] = field(default_factory=list)


def _is_vertical(slot: str) -> bool:
    return is_vertical(slot)


def _taped_stack(build: BuildCfg, lib: Library) -> bool:
    """Orientation B: every card horizontal, touching, shroud suction taped to the mouths."""
    if build.shroud.intake != "taped" or build.shroud.mode == "off":
        return False
    ordered = sort_gpus(build)
    if any(is_vertical(g.slot) for g in ordered) or len(ordered) < 2:
        return False
    width = max(lib.cards[g.card].slots for g in ordered)
    return all(int(b.slot) - int(a.slot) <= width for a, b in zip(ordered, ordered[1:]))


def _assign_slots(build: BuildCfg, slots: list[str]) -> None:
    ordered = sort_gpus(build)
    for gpu, slot in zip(ordered, slots):
        gpu.slot = slot


def _shroud_orientation(build: BuildCfg, lib: Library) -> Candidate | None:
    """Hardware A/B: printed open plenum versus a taped, close-packed stack.

    A is the gapped layout (one card vertical when four dual-slot cards do not
    fit with a gap). B stacks every card and tapes the shroud so it can pull
    only the GPU exhaust openings. Same fans, seals, power and fan curve.
    """
    if build.open_air or build.case not in lib.cases:
        return None
    case = lib.cases[build.case]
    ordered = sort_gpus(build)
    if len(ordered) < 2:
        return None
    width = max(lib.cards[g.card].slots for g in ordered)
    out = build.model_copy(deep=True)
    out.shroud.mode = "on"
    if out.shroud.count <= 0:
        out.shroud.count = 2
    if _taped_stack(build, lib):
        n = len(ordered)
        slots = layout_slots(n, "gap1", case.horizontal_slots, width)
        if len(slots) == n:
            _assign_slots(out, [str(s) for s in slots])
        elif case.vertical_positions and n >= 2:
            horiz = layout_slots(n - 1, "gap1", case.horizontal_slots, width)
            if len(horiz) != n - 1:
                return None
            vertical = case.vertical_positions[min(1, len(case.vertical_positions) - 1)].id
            _assign_slots(out, [str(s) for s in horiz] + [vertical])
        else:
            return None
        out.shroud.intake = "open"
        return Candidate(
            "shroud_orientation",
            "Open the shroud and space the cards (orientation A)",
            "Printed rear plenum: it pulls the interior gaps between cards as well as the GPU exhaust openings. "
            "Top of the top card and bottom of the bottom card stay outside the mouth.",
            "rebuild",
            out,
            framing="shroud_ab",
            note="The other half of the shroud A/B. Predicted, not a measured temperature.",
        )
    slots = layout_slots(len(ordered), "stacked", case.horizontal_slots, width)
    if len(slots) < len(ordered):
        return None
    _assign_slots(out, [str(s) for s in slots])
    out.shroud.intake = "taped"
    return Candidate(
        "shroud_orientation",
        "Stack the cards and tape the shroud (orientation B)",
        "Cards touching. Tape every gap so the shroud pulls only the GPU exhaust openings; "
        "a crack remains between the skins, and those skins face each other.",
        "rebuild",
        out,
        framing="shroud_ab",
        note="Hardware A/B against the printed shroud. Predicted, not a measured temperature.",
    )


def _fan_curve(build: BuildCfg) -> Candidate | None:
    if all(g.fan_curve == "custom_accelerated" for g in build.gpus):
        return None
    out = build.model_copy(deep=True)
    for gpu in out.gpus:
        gpu.fan_curve = "custom_accelerated"
        gpu.custom_curve = None
    return Candidate(
        "fan_curve",
        "Aggressive GPU fan curve",
        "Every card on Custom Accelerated: 0 % fan at 25 °C rising to 100 % at 70 °C (MSI Afterburner / nvidia-settings).",
        "free",
        out,
        note="Louder under load.",
    )


def _power_cap(build: BuildCfg, lib: Library) -> Candidate | None:
    """80 % of each card's stock TBP, only while the build is still above that.

    The cap is the rated board power, not the limit already dialed in. A card
    at or below 80 % of stock has used this lever; a further cut is not "80 %".
    """
    out = build.model_copy(deep=True)
    changed = False
    for gpu in out.gpus:
        card = lib.cards[gpu.card]
        target = round(0.8 * card.tbp_w)
        if target < gpu.power_limit_w - 1:
            gpu.power_limit_w = float(target)
            changed = True
    if not changed:
        return None
    watts = ", ".join(sorted({f"{g.power_limit_w:.0f} W" for g in out.gpus}))
    return Candidate(
        "power_cap",
        "Cap GPU power at 80 %",
        f"nvidia-smi -pl on every card ({watts}).",
        "free",
        out,
        note="Costs some performance; the model does not estimate how much.",
    )


def _shroud(build: BuildCfg, lib: Library) -> Candidate | None:
    if build.open_air:
        return None
    out = build.model_copy(deep=True)
    fan = lib.fans.get(build.shroud.fan)
    fan_name = fan.name if fan else build.shroud.fan
    count = build.shroud.count or 2
    if build.shroud.mode == "on":
        out.shroud.mode = "off"
        return Candidate(
            "shroud",
            "Take the rear shroud off",
            f"Remove the rear GPU exhaust shroud ({count}× {fan_name}).",
            "10min",
            out,
            framing="shroud_on",
            note="A negative gain here is what your shroud is worth.",
        )
    out.shroud.mode = "on"
    out.shroud.count = count
    return Candidate(
        "shroud",
        "Add a rear GPU exhaust shroud",
        f"A plenum over the bracket vents pulled by {count}× {fan_name}.",
        "10min",
        out,
        note="Needs a printed shroud and fans.",
    )


def _seal(build: BuildCfg) -> Candidate | None:
    if build.open_air:
        return None
    sealed = LEAKAGE_SEALS["sealed"]
    current = {k: build.seals.get(k) for k in sealed}
    if all((current[k] or 0) >= v for k, v in sealed.items()):
        return None
    out = build.model_copy(deep=True)
    out.seals = {**build.seals, **{k: max(v, build.seals.get(k, 0) or 0) for k, v in sealed.items()}}
    return Candidate(
        "seal",
        "Seal the gaps",
        "Tape the mesh around the fans and the panel seams, cover unused slot openings.",
        "10min",
        out,
        note="Foil tape and slot covers.",
    )


def _flip_to_intake(build: BuildCfg) -> Candidate | None:
    if build.open_air:
        return None
    fans = [m for m in build.mounts if m.state == "fan"]
    exhausts = [m for m in fans if m.direction == "exhaust"]
    if not exhausts:
        return None
    out = build.model_copy(deep=True)
    for mount in out.mounts:
        if mount.state == "fan":
            mount.direction = "intake"
    names = ", ".join(sorted({m.panel for m in exhausts}))
    return Candidate(
        "flip_fans",
        "Flip the exhaust fans to intake",
        f"Every case fan pulls air in ({names} flipped); hot air leaves through the GPU brackets, mesh and gaps.",
        "10min",
        out,
        note="Positive pressure. The radiator, if any, is left as it is.",
    )


def _add_fans(build: BuildCfg, lib: Library) -> Candidate | None:
    if build.open_air:
        return None
    case = lib.cases[build.case]
    by_id = {m.id: m for m in build.mounts}
    by_size: dict[int, list[str]] = {}
    for mount in build.mounts:
        if mount.state == "fan" and mount.fan:
            by_size.setdefault(mount.size_mm, []).append(mount.fan)
    out = build.model_copy(deep=True)
    out_by_id = {m.id: m for m in out.mounts}
    added = []
    for layout in case.active_mounts(build.patterns):
        if layout.panel == "side":
            continue
        current = by_id.get(layout.id)
        if current is not None and current.state in ("fan", "radiator"):
            continue
        used = by_size.get(layout.size_mm)
        fan_id = max(set(used), key=used.count) if used else f"generic-{layout.size_mm}"
        if fan_id not in lib.fans:
            continue
        direction = "intake" if layout.panel in ("front", "bottom") else "exhaust"
        target = out_by_id.get(layout.id)
        if target is None:
            target = MountCfg(id=layout.id, panel=layout.panel, size_mm=layout.size_mm)
            out.mounts.append(target)
            out_by_id[layout.id] = target
        target.state, target.fan, target.direction, target.duty = "fan", fan_id, direction, 1.0
        added.append((layout.panel, direction))
    if not added:
        return None
    counts: dict[tuple[str, str], int] = {}
    for key in added:
        counts[key] = counts.get(key, 0) + 1
    detail = ", ".join(f"{n}× {panel} {direction}" for (panel, direction), n in counts.items())
    return Candidate(
        "add_fans",
        f"Fill the empty fan mounts ({len(added)})",
        f"{detail}, using the fan model already on that size.",
        "10min",
        out,
        note="Front and bottom as intake, top and rear as exhaust.",
    )


def _space_cards(build: BuildCfg, lib: Library) -> Candidate | None:
    if build.open_air:
        return None
    case = lib.cases[build.case]
    horizontal = sorted((g for g in build.gpus if not _is_vertical(g.slot)), key=lambda g: int(g.slot))
    if len(horizontal) < 2:
        return None
    width = max(lib.cards[g.card].slots for g in horizontal)
    touching = any(int(b.slot) - int(a.slot) <= width for a, b in zip(horizontal, horizontal[1:]))
    if not touching:
        return None
    slots = layout_slots(len(horizontal), "gap1", case.horizontal_slots, width)
    gapped = len(slots) == len(horizontal) and any(b - a > width for a, b in zip(slots, slots[1:]))
    out = build.model_copy(deep=True)
    moved_vertical = None
    if gapped:
        order = {g.id: str(s) for g, s in zip(horizontal, slots)}
    else:
        # Not enough slots for a gap under every card: gap the rest and stand
        # the top card up on a free vertical bracket, if the case has one.
        used = {g.slot for g in build.gpus if _is_vertical(g.slot)}
        free = [v.id for v in case.vertical_positions if v.id not in used]
        fewer = layout_slots(len(horizontal) - 1, "gap1", case.horizontal_slots, width)
        if not free or len(fewer) != len(horizontal) - 1 or not any(b - a > width for a, b in zip(fewer, fewer[1:])):
            return None
        moved_vertical = free[min(1, len(free) - 1)]
        order = {g.id: str(s) for g, s in zip(horizontal[1:], fewer)}
        order[horizontal[0].id] = moved_vertical
    for gpu in out.gpus:
        if gpu.id in order:
            gpu.slot = order[gpu.id]
    before = "/".join(g.slot for g in horizontal)
    after = "/".join(order[g.id] for g in horizontal)
    detail = f"Horizontal slots {before} → {after}"
    if moved_vertical:
        detail += f" (one card to vertical {moved_vertical})"
    return Candidate(
        "space_cards",
        "Space the cards out",
        detail + ": an empty slot under every card.",
        "rebuild",
        out,
        note=(
            "One card moves to a vertical mount on a riser cable. " if moved_vertical else ""
        ) + "Needs the free slots; check PCIe lane wiring on your board.",
    )


def candidates(build: BuildCfg, lib: Library | None = None) -> list[Candidate]:
    lib = lib or get_library()
    makers = [
        lambda: _fan_curve(build),
        lambda: _power_cap(build, lib),
        lambda: _shroud(build, lib),
        lambda: _shroud_orientation(build, lib),
        lambda: _seal(build),
        lambda: _flip_to_intake(build),
        lambda: _add_fans(build, lib),
        lambda: _space_cards(build, lib),
    ]
    out = []
    for make in makers:
        cand = make()
        if cand is not None:
            cand.build.name = build.name
            out.append(cand)
    return out


def _summary(sol) -> dict:
    return {
        "hottest_die_c": sol.hottest_die,
        "hottest_unthrottled_c": sol.hottest_unthrottled,
        "throttling": any(c.throttle for c in sol.cards),
        "cards": {c.id: round(c.t_die_c, 2) for c in sol.cards},
    }


def worth_it(build: BuildCfg, lib: Library | None = None, mc: int = 0, seed: int = 12345) -> dict:
    """Rank single changes to `build` by how much cooler the hottest die gets."""
    lib = lib or get_library()
    base_sol = solve(build, lib)
    cands = candidates(build, lib)
    rows = []
    for cand in cands:
        try:
            sol = solve(cand.build, lib)
        except Exception as exc:  # a candidate the solver rejects is dropped, not fatal
            rows.append({"id": cand.id, "title": cand.title, "error": str(exc)})
            continue
        gain = base_sol.hottest_unthrottled - sol.hottest_unthrottled
        rows.append(
            {
                "id": cand.id,
                "title": cand.title,
                "detail": cand.detail,
                "note": cand.note,
                "framing": cand.framing,
                "effort": cand.effort,
                "effort_label": EFFORT_LABEL[cand.effort],
                "gain_c": round(gain, 2),
                "after": _summary(sol),
                "band_c": None,
                "build": cand.build.model_dump(mode="json"),
            }
        )
    rows = [r for r in rows if "error" not in r]
    if mc > 0 and rows:
        rng = np.random.default_rng(seed)
        builds = {c.id: c.build for c in cands}
        gains: dict[str, list[float]] = {r["id"]: [] for r in rows}
        for _ in range(mc):
            draw = sample_tuning(rng, build, lib)
            base_t = solve(build, lib, draw, outer=4, do_throttle=False).hottest_unthrottled
            for row in rows:
                variant = builds[row["id"]]
                t = solve(variant, lib, draw, outer=4, do_throttle=False).hottest_unthrottled
                gains[row["id"]].append(base_t - t)
        for row in rows:
            lo, hi = np.percentile(gains[row["id"]], [5, 95])
            row["band_c"] = [round(float(lo), 2), round(float(hi), 2)]
    for row in rows:
        band = row["band_c"]
        crosses = band is not None and band[0] <= 0.0 <= band[1]
        small = abs(row["gain_c"]) < NOISE_FLOOR_C
        row["inside_noise"] = bool(crosses or small)
        row["noise_reason"] = (
            "band crosses zero" if crosses else f"under {NOISE_FLOOR_C:.0f} °C" if small else ""
        )
    rows.sort(key=lambda r: r["gain_c"], reverse=True)
    return {
        "base": _summary(base_sol),
        "rows": rows,
        "mc": mc,
        "metric": "hottest die, unthrottled, °C",
        "noise_floor_c": NOISE_FLOOR_C,
        "noise_rule": NOISE_RULE,
    }
