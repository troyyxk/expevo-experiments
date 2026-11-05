#!/usr/bin/env python3
"""Fig. 8 (revised): (a) storage vs refinement setting, (b) accuracy vs storage.

Uses only the frozen result tables (no experiment is re-run):
  tables/refinement_resource_by_subject.csv  -> per-subject storage for panel (a)
  tables/quality_resource_table2.csv         -> total storage and macro accuracy
  tables/accuracy_bootstrap_ci.csv           -> absolute accuracy 95% CI (paired question-level bootstrap)

Outputs the standalone accuracy-vs-storage figure and the combined two-panel figure.
"""
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

# label placement for panel (b): (dx, dy, ha)
# label placement for panel (b): (dx pt, dy pt), with a thin leader line so clusters stay readable
ANNOT = {"Full": (-12, 13), "100": (13, -12), "80": (-12, 12), "60": (14, -11), "40": (11, 12)}


def load():
    rows = list(csv.DictReader(open(os.path.join(OUT, "tables", "refinement_resource_by_subject.csv"))))
    per_subject = {(r["subject"], r["setting"]): r for r in rows}
    table = {r["setting"]: r for r in csv.DictReader(open(os.path.join(OUT, "tables", "quality_resource_table2.csv")))}
    ci = {r["setting"]: r for r in csv.DictReader(open(os.path.join(OUT, "tables", "accuracy_bootstrap_ci.csv")))}
    return per_subject, table, ci


def panel_accuracy_vs_storage(ax, table, ci):
    x = [float(table[s]["storage_total_mb"]) for s in SETTINGS]
    y = [float(table[s]["accuracy_macro_pct"]) for s in SETTINGS]
    lo = [float(ci[s]["ci95_low"]) for s in SETTINGS]
    hi = [float(ci[s]["ci95_high"]) for s in SETTINGS]
    yerr = [[y[i] - lo[i] for i in range(len(y))], [hi[i] - y[i] for i in range(len(y))]]

    ax.errorbar(x, y, yerr=yerr, fmt="none", ecolor="#404040", elinewidth=0.8,
                capsize=2.0, capthick=0.8, zorder=3)
    ax.plot(x, y, "-", color="#404040", lw=1.3, zorder=4)
    ax.plot(x, y, "o", ms=4.6, mfc="white", mec="#404040", mew=1.0, zorder=5)
    for s, xi, yi in zip(SETTINGS, x, y):
        lab = LABELS[SETTINGS.index(s)]
        dx, dy = ANNOT[lab]
        ax.annotate(lab, (xi, yi), textcoords="offset points", xytext=(dx, dy),
                    ha="left" if dx > 0 else "right", va="center", fontsize=8.6, color="#333333",
                    arrowprops=dict(arrowstyle="-", lw=0.4, color="#999999", shrinkA=0, shrinkB=3))
    ax.set_xlabel("Repository storage (MB)")
    ax.set_ylabel("Inference accuracy (%)")
    ax.set_xlim(1.25, 5.45)
    ax.set_ylim(67.5, 81.5)
    ax.grid(True, axis="y", ls=":", lw=0.4, alpha=0.55)
    ax.set_axisbelow(True)


def panel_storage(ax, per_subject):
    x = list(range(len(SETTINGS)))
    for s in SUBJECTS:
        y = [float(per_subject[(s, c)]["storage_mb"]) for c in SETTINGS]
        ax.plot(x, y, "-", marker=MARKERS[s], ms=4.6, lw=1.3, color=COLORS[s],
                mfc=COLORS[s], mec="white", mew=0.5, label=NICE[s])
    ax.set_xticks(x); ax.set_xticklabels(LABELS)
    ax.set_xlabel("Refinement setting")
    ax.set_ylabel("Repository storage (MB)")
    ax.set_ylim(0, 1.62)
    ax.grid(True, axis="y", ls=":", lw=0.4, alpha=0.55)
    ax.set_axisbelow(True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--outdir", default=os.path.join(OUT, "figures"))
    a = ap.parse_args()
    per_subject, table, ci = load()

    # standalone (b)
    fig, ax = plt.subplots(figsize=(3.45, 2.42))
    fig.subplots_adjust(left=0.175, right=0.975, top=0.965, bottom=0.175)
    panel_accuracy_vs_storage(ax, table, ci)
    for ext in ("pdf", "png"):
        fig.savefig(os.path.join(a.outdir, f"fig_accuracy_vs_storage.{ext}"), dpi=300,
                    bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)
    print("figure ->", os.path.join(a.outdir, "fig_accuracy_vs_storage.pdf/.png"))

    # combined (a)+(b)
    fig, axes = plt.subplots(1, 2, figsize=(7.16, 2.42))
    fig.subplots_adjust(left=0.095, right=0.985, top=0.845, bottom=0.175, wspace=0.26)
    panel_storage(axes[0], per_subject)
    panel_accuracy_vs_storage(axes[1], table, ci)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=4, frameon=False,
               bbox_to_anchor=(0.5, 0.995), handlelength=1.4, columnspacing=1.3,
               handletextpad=0.45, borderaxespad=0.1, borderpad=0.0)
    for ax, lab in zip(axes, ("(a)", "(b)")):
        ax.text(0.02, 1.03, lab, transform=ax.transAxes, fontsize=10, va="bottom", ha="left")
    for ext in ("pdf", "png"):
        fig.savefig(os.path.join(a.outdir, f"fig_backend_refinement_quality_resource_v2.{ext}"),
                    dpi=300, bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)
    print("figure ->", os.path.join(a.outdir, "fig_backend_refinement_quality_resource_v2.pdf/.png"))

    print("\nsetting  storage_MB  accuracy%  95% CI")
    for s in SETTINGS:
        print(f"{s:<9}{table[s]['storage_total_mb']:>10}  {table[s]['accuracy_macro_pct']:>8}  "
              f"[{ci[s]['ci95_low']}, {ci[s]['ci95_high']}]")


if __name__ == "__main__":
    main()
