#!/usr/bin/env python3
"""Two-panel figure: accuracy vs coverage for the same-question experiment."""
import argparse, csv, os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
plt.rcParams.update({"font.family": "serif", "font.serif": ["Nimbus Roman", "Liberation Serif", "DejaVu Serif"],
                     "font.size": 10, "axes.labelsize": 10, "xtick.labelsize": 9.4, "ytick.labelsize": 9.4,
                     "axes.linewidth": 0.6, "pdf.fonttype": 42, "ps.fonttype": 42})
C = {"No experience": "#7a7a7a", "Local-only": "#3b6ea5", "Shared-matched": "#4a8f5b", "Shared-full": "#c07a3a"}
ap = argparse.ArgumentParser()
ap.add_argument("--drop", default="", help="comma-separated condition labels to omit")
ap.add_argument("--out", default="fig_coverage_same_question")
a = ap.parse_args()
drop = {x.strip() for x in a.drop.split(",") if x.strip()}
rows = [r for r in csv.DictReader(open(os.path.join(HERE, "results", "covered_questions.csv")))
        if r["condition"] not in drop]
fig, axes = plt.subplots(1, 2, figsize=(7.0, 2.6), gridspec_kw={"width_ratios": [1.25, 1]})
fig.subplots_adjust(left=0.075, right=0.985, top=0.84, bottom=0.20, wspace=0.34)

ax = axes[0]
xs = list(range(len(rows)))
for x, r in zip(xs, rows):
    lo, hi = float(r["ci_lower"]), float(r["ci_upper"])
    acc = float(r["accuracy_percent"])
    col = C[r["condition"]]
    ax.plot([x, x], [lo, hi], "-", color=col, lw=1.6)
    ax.plot([x - 0.12, x + 0.12], [lo, lo], "-", color=col, lw=1.0)
    ax.plot([x - 0.12, x + 0.12], [hi, hi], "-", color=col, lw=1.0)
    ax.plot(x, acc, "o", ms=6.2, mfc=col, mec="white", mew=0.7, zorder=5)
ax.set_xticks(xs)
ax.set_xticklabels([r["condition"].replace(" ", "\n") for r in rows], fontsize=8.8)
ax.set_ylabel("Accuracy (%)")
ax.set_ylim(min(float(r["ci_lower"]) for r in rows) - 4, max(float(r["ci_upper"]) for r in rows) + 4)
ax.grid(axis="y", ls=":", lw=0.4, alpha=0.55)
ax.set_axisbelow(True)

ax = axes[1]
cov = [float(r["top5_own_question_percent"]) for r in rows]
ax.bar(xs, cov, color=[C[r["condition"]] for r in rows], width=0.62, edgecolor="white", linewidth=0.6)
for x, v in zip(xs, cov):
    ax.text(x, v + 2, f"{v:.0f}%", ha="center", fontsize=8.6)
ax.set_xticks(xs)
ax.set_xticklabels([{"Local-only": "Local", "Shared-matched": "Matched",
                     "Shared-full": "Full", "No experience": "None"}.get(r["condition"], r["condition"])
                    for r in rows], fontsize=8.8)
ax.set_ylabel("Top-5 from the asked question (%)")
ax.set_ylim(0, 112)
ax.grid(axis="y", ls=":", lw=0.4, alpha=0.55)
ax.set_axisbelow(True)

for ax, lab in zip(axes, ("(a)", "(b)")):
    ax.text(0.0, 1.015, lab, transform=ax.transAxes, fontsize=10, ha="left", va="bottom")
out = os.path.join(HERE, "figures", a.out)
for ext in ("pdf", "png"):
    fig.savefig(f"{out}.{ext}", dpi=300, bbox_inches="tight", pad_inches=0.02)
print("figure ->", out + ".pdf/.png")
