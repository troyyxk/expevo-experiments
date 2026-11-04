#!/usr/bin/env python3
"""Optional figure (guide §7.2): full vs refined hot-index query latency, P50 and P95 on one axis.

Values come from results/retrieval_latency_summary.csv (median session of three measurement sessions).
"""
import csv, os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
plt.rcParams.update({"font.family": "serif", "font.serif": ["Nimbus Roman", "Liberation Serif", "DejaVu Serif"],
                     "font.size": 10, "axes.labelsize": 10, "xtick.labelsize": 10, "ytick.labelsize": 10,
                     "legend.fontsize": 9, "axes.linewidth": 0.6, "pdf.fonttype": 42, "ps.fonttype": 42})
COLUMN_PT = 251.0

rows = {r["repository"]: r for r in csv.DictReader(open(os.path.join(HERE, "results", "retrieval_latency_summary.csv")))}
labels = ["Full\n(6,000)", "Refined\n(942)"]
p50 = [float(rows["full"]["query_p50_ms"]), float(rows["refined"]["query_p50_ms"])]
p95 = [float(rows["full"]["query_p95_ms"]), float(rows["refined"]["query_p95_ms"])]

fig, ax = plt.subplots(figsize=(COLUMN_PT / 72.0, 150.0 / 72.0))
fig.subplots_adjust(left=0.145, right=0.985, top=0.86, bottom=0.20)

x = [0, 1]
w = 0.34
b1 = ax.bar([i - w / 2 for i in x], p50, width=w, color="#9db9d6", edgecolor="white", linewidth=0.6, label="P50")
b2 = ax.bar([i + w / 2 for i in x], p95, width=w, color="#3b6ea5", edgecolor="white", linewidth=0.6, label="P95")
for bars in (b1, b2):
    for b in bars:
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.8, f"{b.get_height():.2f}",
                ha="center", va="bottom", fontsize=8.6)
ax.set_xticks(x)
ax.set_xticklabels(labels)
ax.set_ylabel("Query latency (ms)")
ax.set_ylim(0, 46)
ax.grid(axis="y", ls=":", lw=0.4, alpha=0.55)
ax.set_axisbelow(True)
ax.legend(loc="upper right", frameon=False, ncol=2, handlelength=1.4, columnspacing=1.0,
          bbox_to_anchor=(1.0, 1.02))
# the reduction is stated in the caption, not on the canvas

out = os.path.join(HERE, "figures", "query_latency_comparison")
for ext in ("pdf", "png"):
    fig.savefig(f"{out}.{ext}", dpi=300)
print("figure ->", out + ".pdf/.png")
