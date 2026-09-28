"""Draw the flow network. Graphviz when it imports, otherwise matplotlib."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from gpusim.library import get_library
from gpusim.network import build_network
from gpusim.solve import prepare_sample, solve


def draw_schematic(build, path: str | Path, library=None) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lib = library or get_library()
    sample = prepare_sample(build)
    duties = {gpu.id: 0.7 for gpu in build.gpus}
    case = None if build.open_air else lib.cases[build.case]
    net = build_network(
        build, case, lib.fans, lib.cards, lib.radiators, duties, {}, sample
    )
    sol = solve(build, lib, do_throttle=False, outer=5)
    flow = {br["id"]: br for br in sol.branches}
    if _try_graphviz(net, flow, path, build.name):
        return path
    _matplotlib(net, flow, path, build.name)
    return path


def _try_graphviz(net, flow, path: Path, title: str) -> bool:
    try:
        import graphviz
    except ImportError:
        return False
    dot = graphviz.Digraph(comment=title)
    dot.attr(rankdir="LR", label=title, labelloc="t")
    nodes = set()
    for br in net.branches:
        if br.kind == "bleed":
            continue
        nodes.add(br.a)
        nodes.add(br.b)
    for node in sorted(nodes):
        dot.node(node)
    for br in net.branches:
        if br.kind == "bleed":
            continue
        info = flow.get(br.id, {})
        cfm = info.get("flow_cfm", 0.0)
        label = f"{br.kind}\n{cfm:.0f} CFM"
        if cfm >= 0:
            dot.edge(br.a, br.b, label=label)
        else:
            dot.edge(br.b, br.a, label=label)
    try:
        dot.render(path.with_suffix(""), format="png", cleanup=True)
    except Exception:
        return False
    rendered = path.with_suffix(".png")
    return rendered.exists()


def _matplotlib(net, flow, path: Path, title: str) -> None:
    nodes = []
    for br in net.branches:
        if br.kind == "bleed":
            continue
        for name in (br.a, br.b):
            if name not in nodes:
                nodes.append(name)
    # Lay the chain out in a readable column groups.
    groups = {
        "amb": (0, 0),
        "plume": (0, -1.2),
        "plenum": (0, 1.2),
        "case": (2, 0.4),
        "gpu": (2, -0.8),
    }
    pos = {}
    card_ids = []
    for name in nodes:
        if name.startswith("cin-") or name.startswith("cex-"):
            gid = name.split("-", 1)[1]
            if gid not in card_ids:
                card_ids.append(gid)
    for name in nodes:
        if name in groups:
            pos[name] = groups[name]
        elif name.startswith("cin-"):
            i = card_ids.index(name.split("-", 1)[1])
            pos[name] = (3.3, 1.2 - i * 0.9)
        elif name.startswith("cex-"):
            i = card_ids.index(name.split("-", 1)[1])
            pos[name] = (4.6, 1.2 - i * 0.9)
        else:
            pos[name] = (1, len(pos) * 0.3)
    fig, ax = plt.subplots(figsize=(11, 7))
    for br in net.branches:
        if br.kind == "bleed" or br.a not in pos or br.b not in pos:
            continue
        info = flow.get(br.id, {})
        cfm = info.get("flow_cfm", 0.0)
        x0, y0 = pos[br.a]
        x1, y1 = pos[br.b]
        if cfm < 0:
            x0, y0, x1, y1 = x1, y1, x0, y0
        color = "#c4473a" if cfm < 0 else "#2f6f9f"
        ax.annotate(
            "",
            xy=(x1, y1),
            xytext=(x0, y0),
            arrowprops={"arrowstyle": "->", "color": color, "lw": 1.0 + min(abs(cfm) / 40, 2.5)},
        )
        ax.text(
            (x0 + x1) / 2,
            (y0 + y1) / 2,
            f"{abs(cfm):.0f}",
            fontsize=7,
            color="#333",
            ha="center",
            va="center",
        )
    for name, (x, y) in pos.items():
        ax.scatter([x], [y], s=280, c="#f4f1ea", edgecolors="#222", zorder=3)
        ax.text(x, y, name, ha="center", va="center", fontsize=7, zorder=4)
    ax.set_title(title + "\narrow labels are CFM, colour follows solved direction")
    ax.axis("off")
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def write_tornado(build, path: Path, library=None) -> None:
    """One-at-a-time kicks of the stock configuration."""
    from gpusim.calib import GLOBAL

    lib = library or get_library()
    base = solve(build, lib, do_throttle=False, outer=5)
    nominal = base.hottest_unthrottled
    kicks = {
        "nu_C ×1.2": {"nu_C": GLOBAL["nu_C"] * 1.2},
        "nu_C ×0.8": {"nu_C": GLOBAL["nu_C"] * 0.8},
        "TIM ×1.2": {"cards": {build.gpus[0].card: {"r_tim": None}}},  # filled below
        "blower flow ×1.1": {"cards": {build.gpus[0].card: {"qmax_m3s": None}}},
        "blower flow ×0.9": {"cards": {build.gpus[0].card: {"qmax_m3s": None}}},
        "orifice k ×1.25": {"k_scale": 1.25},
        "orifice k ×0.8": {"k_scale": 0.8},
        "seal area ×1.25": {"seal_scale": 1.25},
        "seal area ×0.8": {"seal_scale": 0.8},
        "ambient +1.5 °C": {"ambient_offset": 1.5},
        "ambient −1.5 °C": {"ambient_offset": -1.5},
        "recirc area ×1.5": {"recirc_area_m2": GLOBAL["recirc_area_m2"] * 1.5},
    }
    # Fill card-relative kicks from the calibrated baseline via prepare? Easier to
    # re-specify absolute values from calib.
    from gpusim.calib import card_tuning

    tuned = card_tuning(build.gpus[0].card)
    cid = build.gpus[0].card
    kicks["TIM ×1.2"] = {"cards": {cid: {"r_tim": tuned["r_tim"] * 1.2}}}
    kicks["TIM ×0.8"] = {"cards": {cid: {"r_tim": tuned["r_tim"] * 0.8}}}
    kicks["blower flow ×1.1"] = {"cards": {cid: {"qmax_m3s": tuned["qmax_m3s"] * 1.1}}}
    kicks["blower flow ×0.9"] = {"cards": {cid: {"qmax_m3s": tuned["qmax_m3s"] * 0.9}}}
    deltas = []
    for name, sample in kicks.items():
        sol = solve(build, lib, sample=sample, do_throttle=False, outer=4)
        deltas.append((name, sol.hottest_unthrottled - nominal))
    deltas.sort(key=lambda item: abs(item[1]))
    fig, ax = plt.subplots(figsize=(9, 6))
    labels = [name for name, _ in deltas]
    values = [value for _, value in deltas]
    colors = ["#c4473a" if value > 0 else "#2f6f9f" for value in values]
    ax.barh(labels, values, color=colors)
    ax.axvline(0, color="#222", lw=0.8)
    ax.set_xlabel("Change in hottest unthrottled die (°C)")
    ax.set_title(f"Stock sensitivity  (nominal {nominal:.1f} °C)")
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)
