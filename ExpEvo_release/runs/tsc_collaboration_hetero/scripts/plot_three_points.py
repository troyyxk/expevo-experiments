#!/usr/bin/env python3
"""Single-panel figure: Local-only (15/60), partial sharing (45/60), Shared-matched (60/60).

All three pools hold exactly 375 entries; only the number of construction questions they cover differs.
"""
import csv, os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
plt.rcParams.update({"font.family": "serif", "font.serif": ["Nimbus Roman", "Liberation Serif", "DejaVu Serif"],
                     "font.size": 10, "axes.labelsize": 10, "xtick.labelsize": 9.2, "ytick.labelsize": 9.4,
                     "axes.linewidth": 0.6, "pdf.fonttype": 42, "ps.fonttype": 42})

cov = {r["condition"]: r for r in csv.DictReader(open(os.path.join(HERE, "results", "covered_questions.csv")))}
sweep = {int(r["coverage_questions"]): r for r in csv.DictReader(open(os.path.join(HERE, "results", "coverage_sweep.csv")))}

points = [
    ("Local-only", float(cov["Local-only"]["accuracy_percent"]),
     float(cov["Local-only"]["ci_lower"]), float(cov["Local-only"]["ci_upper"]), "#3b6ea5"),
    ("Shared", float(sweep[45]["accuracy_percent"]),
     float(sweep[45]["ci_lower"]), float(sweep[45]["ci_upper"]), "#5f7f4a"),
    ("Shared-matched", float(cov["Shared-matched"]["accuracy_percent"]),
     float(cov["Shared-matched"]["ci_lower"]), float(cov["Shared-matched"]["ci_upper"]), "#4a8f5b"),
]

fig, ax = plt.subplots(figsize=(3.45, 2.45))
fig.subplots_adjust(left=0.175, right=0.975, top=0.955, bottom=0.165)
for x, (label, acc, lo, hi, col) in enumerate(points):
    ax.plot([x, x], [lo, hi], "-", color=col, lw=1.5)
    ax.plot([x - 0.11, x + 0.11], [lo, lo], "-", color=col, lw=1.0)
    ax.plot([x - 0.11, x + 0.11], [hi, hi], "-", color=col, lw=1.0)
    ax.plot(x, acc, "o", ms=6.0, mfc=col, mec="white", mew=0.7, zorder=5)
ax.set_xticks(range(len(points)))
ax.set_xticklabels([p[0] for p in points])
ax.set_ylabel("Accuracy (%)")
ax.set_xlim(-0.55, len(points) - 0.45)
ax.set_ylim(35, 90)
ax.grid(axis="y", ls=":", lw=0.4, alpha=0.55)
ax.set_axisbelow(True)

out = os.path.join(HERE, "figures", "fig_local_45_matched")
for ext in ("pdf", "png"):
    fig.savefig(f"{out}.{ext}", dpi=300, bbox_inches="tight", pad_inches=0.02)
print("figure ->", out + ".pdf/.png")
