#!/usr/bin/env python3
"""Figure for the cross-client sharing experiment (V.C of the TSC revision).

Three modes:
  template : layout only, no data, clearly marked "TEMPLATE - NO RESULTS"   (safe to ship before the run)
  mock     : neutral illustrative positions, watermarked "DESIGN MOCK"      (layout review only)
  real     : reads results/*.csv produced by aggregate_stats.py             (the paper figure)

Panel (a): absolute accuracy with question-level 95% CI, plus the three matched-pool points.
Panel (b): paired accuracy differences with 95% CI (forest plot).
"""
import argparse
import csv
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
plt.rcParams.update({"font.family": "serif", "font.serif": ["Nimbus Roman", "Liberation Serif", "DejaVu Serif"],
    "font.size": 10, "axes.labelsize": 10, "xtick.labelsize": 9.4, "ytick.labelsize": 9.4,
    "legend.fontsize": 9, "axes.linewidth": 0.6, "mathtext.fontset": "custom",
    "mathtext.rm": "Nimbus Roman", "mathtext.it": "Nimbus Roman:italic",
    "pdf.fonttype": 42, "ps.fonttype": 42})

C_LOCAL, C_MATCH, C_FULL = "#3b6ea5", "#4a8f5b", "#c07a3a"


def panel_a(ax, rows, banner, seeds=None):
    xs = [0, 1, 2]
    for x, (name, mean, lo, hi, color) in zip(xs, rows):
        ax.plot([x, x], [lo, hi], "-", color=color, lw=1.6, solid_capstyle="butt")
        ax.plot([x - 0.13, x + 0.13], [lo, lo], "-", color=color, lw=1.0)
        ax.plot([x - 0.13, x + 0.13], [hi, hi], "-", color=color, lw=1.0)
        ax.plot(x, mean, "o", ms=6.2, mfc=color, mec="white", mew=0.7, zorder=5)
    if seeds:
        for i, v in enumerate(seeds):
            ax.plot(1 + (i - 1) * 0.13, v, "o", ms=3.4, mfc="white", mec=C_MATCH, mew=0.9, zorder=4)
    ax.set_xticks(xs)
    ax.set_xticklabels(["Local-only", "Shared-matched", "Shared-full\n(hetero)"])
    ax.set_ylabel("Accuracy (%)")
    ax.grid(axis="y", ls=":", lw=0.4, alpha=0.55)
    ax.set_axisbelow(True)


def panel_b(ax, diffs, banner):
    labels = [d[0] for d in diffs]
    ys = list(range(len(diffs)))[::-1]
    ax.axvline(0, ls="--", lw=0.9, color="#666666")
    for y, (name, mean, lo, hi) in zip(ys, diffs):
        col = C_MATCH if "Matched" in name.split("−")[0] else C_FULL
        ax.plot([lo, hi], [y, y], "-", color=col, lw=1.6)
        ax.plot([lo, lo], [y - 0.12, y + 0.12], "-", color=col, lw=1.0)
        ax.plot([hi, hi], [y - 0.12, y + 0.12], "-", color=col, lw=1.0)
        ax.plot(mean, y, "o", ms=6.2, mfc=col, mec="white", mew=0.7, zorder=5)
    ax.set_yticks(ys)
    ax.set_yticklabels(labels, fontsize=8.8)
    ax.set_xlabel("Paired accuracy difference (pp)")
    ax.grid(axis="x", ls=":", lw=0.4, alpha=0.55)
    ax.set_axisbelow(True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["template", "mock", "real"], default="template")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    seed_pts = None
    if a.mode == "real":
        pool = {r["policy"]: r for r in csv.DictReader(open(os.path.join(HERE, "results", "accuracy_by_pool.csv")))}
        diffs_csv = {r["comparison"]: r for r in
                     csv.DictReader(open(os.path.join(HERE, "results", "paired_differences.csv")))}
        seed_pts = [float(pool[f"shared_matched_{s}"]["accuracy_percent"])
                    for s in ("20261109", "20261110", "20261111")]
        acc = [(lab, float(pool[key]["accuracy_percent"]), float(pool[key]["ci_lower_percent"]),
                float(pool[key]["ci_upper_percent"]), col)
               for lab, key, col in (("Local-only", "local_only", C_LOCAL),
                                     ("Shared-matched", "shared_matched", C_MATCH),
                                     ("Shared-full (hetero)", "shared_full_hetero", C_FULL))]
        diffs = [(k, float(diffs_csv[k]["delta_pp"]), float(diffs_csv[k]["ci_lower_pp"]),
                  float(diffs_csv[k]["ci_upper_pp"]))
                 for k in ("Matched − Local", "Full − Matched", "Full − Local")]
        banner = None
    else:
        base, half = 70.0, 4.0
        acc = [(lab, base, base - half, base + half, col)
               for lab, col in (("Local-only", C_LOCAL), ("Shared-matched", C_MATCH),
                                ("Shared-full (hetero)", C_FULL))]
        diffs = [(k, 0.0, -3.5, 3.5) for k in ("Matched − Local", "Full − Matched", "Full − Local")]
        banner = ("TEMPLATE — NO RESULTS" if a.mode == "template"
                  else "DESIGN MOCK — ILLUSTRATIVE POSITIONS, NOT RESULTS")

    fig, axes = plt.subplots(1, 2, figsize=(7.05, 2.75), gridspec_kw={"width_ratios": [1, 1]})
    fig.subplots_adjust(left=0.075, right=0.985, top=0.855, bottom=0.175, wspace=0.42)

    if a.mode == "template":
        for ax in axes:
            ax.grid(ls=":", lw=0.4, alpha=0.55)
            ax.set_axisbelow(True)
            ax.text(0.5, 0.5, "no data yet", transform=ax.transAxes, ha="center", va="center",
                    fontsize=11, color="#999999", style="italic")
        axes[0].set_xlim(-0.5, 2.5); axes[0].set_ylim(60, 80)
        axes[0].set_xticks([0, 1, 2])
        axes[0].set_xticklabels(["Local-only", "Shared-matched", "Shared-full\n(hetero)"])
        axes[0].set_ylabel("Accuracy (%)")
        axes[1].set_xlim(-6, 6); axes[1].set_ylim(-0.6, 2.6)
        axes[1].set_yticks([2, 1, 0])
        axes[1].set_yticklabels(["Matched − Local", "Full − Matched", "Full − Local"])
        axes[1].set_xlabel("Paired accuracy difference (pp)")
        axes[1].axvline(0, ls="--", lw=0.9, color="#666666")
    else:
        panel_a(axes[0], acc, banner, seeds=seed_pts if a.mode == "real" else [base - 0.6, base, base + 0.5])
        panel_b(axes[1], diffs, banner)
        axes[0].set_xlim(-0.55, 2.55)
        if a.mode == "real":
            axes[0].set_ylim(min(x[2] for x in acc) - 2, max(x[3] for x in acc) + 2)
            axes[1].set_xlim(min(d[2] for d in diffs) - 1, max(d[3] for d in diffs) + 1)
        else:
            axes[0].set_ylim(60, 80); axes[1].set_xlim(-6, 6)

    for ax, lab in zip(axes, ("(a)", "(b)")):
        ax.text(0.0, 1.015, lab, transform=ax.transAxes, fontsize=10, ha="left", va="bottom")
    if banner:
        fig.text(0.5, 0.945, banner, ha="center", va="bottom", fontsize=8.4, color="#b03030", style="italic")

    out = a.out or os.path.join(HERE, "figures", ("fig_hetero_sharing" if a.mode == "real" else f"fig_hetero_sharing_{a.mode}"))
    for ext in ("pdf", "png"):
        fig.savefig(f"{out}.{ext}", dpi=300, bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)
    print("figure ->", out + ".pdf/.png")


if __name__ == "__main__":
    main()
