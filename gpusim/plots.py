"""PNG charts for a sweep."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from gpusim.factors import STOCK, apply_cell
from gpusim.schematic import draw_schematic, write_tornado


def write_plots(frame, directory: Path, build, library) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    _die_chart(frame, directory / "die_temp.png")
    _flow_chart(frame, directory / "flow.png")
    _pressure_chart(frame, directory / "case_pressure.png")
    stock = apply_cell(build, library=library, **STOCK)
    draw_schematic(stock, directory / "schematic.png", library)
    write_tornado(stock, directory / "tornado_stock.png", library)


def _labels(frame):
    return list(frame["config"])


def _die_chart(frame, path: Path) -> None:
    labels = _labels(frame)
    x = np.arange(len(labels))
    fig, ax = plt.subplots(figsize=(14, 6))
    hottest = frame["hottest_unthrottled_c"].to_numpy()
    ax.bar(x, hottest, color="#c47b3a", width=0.7, label="Hottest unthrottled die")
    if "mc_p05_hottest_c" in frame.columns and frame["mc_p05_hottest_c"].notna().any():
        low = hottest - frame["mc_p05_hottest_c"].to_numpy()
        high = frame["mc_p95_hottest_c"].to_numpy() - hottest
        ax.errorbar(x, hottest, yerr=np.vstack([low, high]), fmt="none", ecolor="#222", capsize=3)
    # Per-card markers.
    card_cols = [c for c in frame.columns if c.startswith("t_die_unthrottled_") and c.endswith("_c")]
    for col in card_cols:
        ax.scatter(x, frame[col], s=18, zorder=3)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=70, ha="right", fontsize=7)
    ax.set_ylabel("Die temperature (°C)")
    ax.set_title("Hottest die by configuration (error bars are 5th–95th percentile when MC ran)")
    ax.axhline(90, color="#c4473a", ls="--", lw=0.8, label="90 °C cutoff")
    ax.legend(loc="upper right", fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def _flow_chart(frame, path: Path) -> None:
    labels = _labels(frame)
    cols = [c for c in frame.columns if c.startswith("flow_cfm_")]
    x = np.arange(len(labels))
    fig, ax = plt.subplots(figsize=(14, 6))
    width = 0.8 / max(len(cols), 1)
    for i, col in enumerate(cols):
        ax.bar(x + i * width, frame[col], width=width, label=col.replace("flow_cfm_", "card "))
    ax.set_xticks(x + width * (len(cols) - 1) / 2)
    ax.set_xticklabels(labels, rotation=70, ha="right", fontsize=7)
    ax.set_ylabel("Blower flow (CFM)")
    ax.set_title("Per-card blower flow")
    ax.legend(fontsize=8, ncol=min(4, len(cols)))
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def _pressure_chart(frame, path: Path) -> None:
    labels = _labels(frame)
    values = frame["case_pressure_pa"].to_numpy()
    colors = ["#2f6f9f" if v >= 0 else "#c4473a" for v in values]
    fig, ax = plt.subplots(figsize=(14, 5))
    ax.bar(np.arange(len(labels)), values, color=colors)
    ax.axhline(0, color="#222", lw=0.8)
    ax.set_xticks(np.arange(len(labels)))
    ax.set_xticklabels(labels, rotation=70, ha="right", fontsize=7)
    ax.set_ylabel("Case pressure (Pa gauge)")
    ax.set_title("Case pressure relative to ambient  (positive = more intake than the leaks can dump)")
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)
