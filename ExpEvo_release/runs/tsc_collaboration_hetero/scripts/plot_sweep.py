#!/usr/bin/env python3
"""Coverage-accuracy curve: accuracy is a function of how many questions are covered, not of how much
experience is shared per question."""
import csv, os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
plt.rcParams.update({"font.family": "serif", "font.serif": ["Nimbus Roman", "Liberation Serif", "DejaVu Serif"],
                     "font.size": 10, "axes.labelsize": 10, "xtick.labelsize": 9.4, "ytick.labelsize": 9.4,
                     "axes.linewidth": 0.6, "pdf.fonttype": 42, "ps.fonttype": 42})

rows = list(csv.DictReader(open(os.path.join(HERE, "results", "coverage_sweep.csv"))))
dec = list(csv.DictReader(open(os.path.join(HERE, "results", "coverage_sweep_decomposition.csv"))))
x = [100 * int(r["coverage_questions"]) / 60 for r in rows]
y = [float(r["accuracy_percent"]) for r in rows]
lo = [float(r["ci_lower"]) for r in rows]
hi = [float(r["ci_upper"]) for r in rows]

fig, ax = plt.subplots(figsize=(3.9, 2.75))
fig.subplots_adjust(left=0.155, right=0.975, top=0.90, bottom=0.185)

ax.axhspan(76, 80, color="#4a8f5b", alpha=0.10, lw=0)
ax.axhspan(42, 46, color="#b03030", alpha=0.08, lw=0)

for xx, yy, l, h in zip(x, y, lo, hi):
    ax.plot([xx, xx], [l, h], "-", color="#3b6ea5", lw=1.2, alpha=0.8)
ax.plot(x, y, "-o", color="#3b6ea5", lw=1.6, ms=5.5, mfc="white", mew=1.4, zorder=5)

ax.text(62, 78.2, "covered questions ≈ 78 %", fontsize=8, color="#3d7a4d", ha="right", va="bottom")
ax.text(62, 43.4, "uncovered questions ≈ 44 %", fontsize=8, color="#a04030", ha="right", va="top")

ax.set_xlabel("Construction questions covered by the shared pool (%)")
ax.set_ylabel("Accuracy (%)")
ax.set_xlim(10, 105)
ax.set_ylim(35, 90)
ax.set_xticks([25, 50, 75, 100])
ax.grid(ls=":", lw=0.4, alpha=0.55)
ax.set_axisbelow(True)
ax.text(0.0, 1.015, "(a)", transform=ax.transAxes, fontsize=10, ha="left", va="bottom")

out = os.path.join(HERE, "figures", "fig_coverage_curve")
for ext in ("pdf", "png"):
    fig.savefig(f"{out}.{ext}", dpi=300, bbox_inches="tight", pad_inches=0.02)
print("figure ->", out + ".pdf/.png")
