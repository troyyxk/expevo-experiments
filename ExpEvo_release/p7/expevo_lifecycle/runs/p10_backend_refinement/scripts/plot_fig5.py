#!/usr/bin/env python3
"""Figure 5: backend storage and normalized indexed entries across refinement settings."""
import argparse
import csv
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SETTINGS = ["Full", "BM25_100", "BM25_80", "BM25_60", "BM25_40"]
LABELS = ["Full", "100", "80", "60", "40"]
SUBJECTS = ["international_law", "college_medicine", "college_biology", "high_school_geography"]
NICE = {"international_law": "International Law", "college_medicine": "College Medicine",
        "college_biology": "College Biology", "high_school_geography": "High School Geography"}
COLORS = {"international_law": "#3b6ea5", "college_medicine": "#4a8f5b",
          "college_biology": "#c07a3a", "high_school_geography": "#8a5a9a"}
MARKERS = {"international_law": "o", "college_medicine": "s", "college_biology": "^", "high_school_geography": "D"}

plt.rcParams.update({
    "font.family": "serif", "font.serif": ["Nimbus Roman", "Liberation Serif", "DejaVu Serif"],
    "font.size": 10, "axes.labelsize": 10, "xtick.labelsize": 9.4, "ytick.labelsize": 9.4,
    "legend.fontsize": 9.2, "axes.linewidth": 0.6,
    "mathtext.fontset": "custom", "mathtext.rm": "Nimbus Roman", "mathtext.it": "Nimbus Roman:italic",
    "pdf.fonttype": 42, "ps.fonttype": 42,
})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(OUT, "figures", "fig_backend_refinement_quality_resource"))
    a = ap.parse_args()
    rows = list(csv.DictReader(open(os.path.join(OUT, "tables", "refinement_resource_by_subject.csv"))))
    data = {(r["subject"], r["setting"]): r for r in rows}

    fig, axes = plt.subplots(1, 2, figsize=(7.16, 2.42))
    fig.subplots_adjust(left=0.082, right=0.988, top=0.915, bottom=0.175, wspace=0.17)
    x = list(range(len(SETTINGS)))

    ax = axes[0]
    for s in SUBJECTS:
        y = [float(data[(s, c)]["storage_mb"]) for c in SETTINGS]
        ax.plot(x, y, "-", marker=MARKERS[s], ms=4.6, lw=1.3, color=COLORS[s],
                mfc=COLORS[s], mec="white", mew=0.5, label=NICE[s])
    ax.set_xticks(x); ax.set_xticklabels(LABELS)
    ax.set_xlabel("Refinement setting")
    ax.set_ylabel("Repository storage (MB)")
    ax.set_ylim(0, 1.62)
    ax.grid(True, axis="y", ls=":", lw=0.4, alpha=0.55)
    ax.set_axisbelow(True)

    ax = axes[1]
    for s in SUBJECTS:
        y = [float(data[(s, c)]["normalized_entry_ratio"]) for c in SETTINGS]
        ax.plot(x, y, "-", marker=MARKERS[s], ms=4.6, lw=1.3, color=COLORS[s],
                mfc=COLORS[s], mec="white", mew=0.5, label=NICE[s])
    ax.set_xticks(x); ax.set_xticklabels(LABELS)
    ax.set_xlabel("Refinement setting")
    ax.set_ylabel("Normalized entries")
    ax.set_ylim(0, 1.06)
    ax.grid(True, axis="y", ls=":", lw=0.4, alpha=0.55)
    ax.set_axisbelow(True)

    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=4, frameon=False,
               bbox_to_anchor=(0.5, 1.0), handlelength=1.4, columnspacing=1.3,
               handletextpad=0.45, borderaxespad=0.1, borderpad=0.0)
    for ax, lab in zip(axes, ("(a)", "(b)")):
        ax.text(0.03, 0.055, lab, transform=ax.transAxes, fontsize=10, va="bottom", ha="left")

    for ext in ("pdf", "png"):
        fig.savefig(f"{a.out}.{ext}", dpi=300, bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)
    print("figure ->", a.out + ".pdf/.png")


if __name__ == "__main__":
    main()
