"""Paper-sized variant of the lifecycle footprint figure.

Target geometry measured from the TMC manuscript (Fig. 1 / Fig. 2):
    3.45 in  x  2.29 in   (single column), tick/label fonts ~8 pt, no in-figure
    title, one compact legend, minimal per-bar annotation.
"""
import argparse
import csv
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from .common import load_config

SHORT = {
    "international_law": "International\nLaw",
    "college_medicine": "College\nMedicine",
    "college_biology": "College\nBiology",
    "high_school_geography": "High School\nGeography",
}
plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Nimbus Roman", "Liberation Serif", "DejaVu Serif"],
    "font.size": 9.0,
    "axes.labelsize": 9,
    "xtick.labelsize": 9.0,
    "ytick.labelsize": 9.0,
    "legend.fontsize": 8.6,
    "axes.linewidth": 0.6,
    "xtick.major.width": 0.5,
    "ytick.major.width": 0.5,
    "xtick.major.size": 2.2,
    "ytick.major.size": 2.2,
    "mathtext.fontset": "custom",
    "mathtext.rm": "Nimbus Roman",
    "mathtext.it": "Nimbus Roman:italic",
    "mathtext.bf": "Nimbus Roman:bold",
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--tau", type=int, default=60)
    args = ap.parse_args()
    cfg = load_config(args.config)
    run_dir = os.path.abspath(os.path.join(cfg["runtime"]["runs_dir"], cfg["run_id"]))
    tabs = os.path.join(run_dir, "tables")
    foot = {r["subject"]: r for r in csv.DictReader(open(os.path.join(tabs, "lifecycle_footprint.csv")))}
    ref = list(csv.DictReader(open(os.path.join(tabs, "refinement_metrics.csv"))))
    subjects = [s for s in cfg["data"]["subjects"] if s in foot]
    tau = args.tau
    ref_bytes = {}
    for s in subjects:
        row = next(r for r in ref if r["subject"] == s and int(float(r["threshold"])) == tau)
        ref_bytes[s] = float(row["refined_bytes"])

    raw = np.array([float(foot[s]["raw_total_bytes"]) for s in subjects]) / 1e6
    dis = np.array([float(foot[s]["distilled_total_bytes"]) for s in subjects]) / 1e6
    rfd = np.array([ref_bytes[s] for s in subjects]) / 1e6

    fig, ax = plt.subplots(figsize=(4.05, 2.16))
    fig.subplots_adjust(left=0.20, right=0.985, top=0.80, bottom=0.265)
    x = np.arange(len(subjects))
    w = 0.26
    ax.bar(x - w, raw, w, color="#8fb8d6", edgecolor="black", linewidth=0.35, label="Raw episodes")
    ax.bar(x, dis, w, color="#5d9c76", edgecolor="black", linewidth=0.35, label="Distilled")
    ax.bar(x + w, rfd, w, color="#d98b5f", edgecolor="black", linewidth=0.35,
           label=f"Refined ($\\tau$={tau})")
    ax.set_xticks(x)
    labels = [SHORT.get(s, s) for s in subjects]
    ax.set_xticklabels(labels)
    ax.set_ylabel("Serialized data (MB)", labelpad=3.2)
    ax.set_yticks([0, 2, 4, 6])
    ax.set_ylim(0, max(raw.max(), 6.0) * 1.10)
    ax.tick_params(pad=2.0)
    ax.grid(axis="y", ls=":", lw=0.4, alpha=0.7)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, ncol=3, loc="lower center", bbox_to_anchor=(0.5, 1.075),
              handlelength=1.0, handletextpad=0.4, columnspacing=1.1,
              borderaxespad=0.0, borderpad=0.0)
    for ext in ("pdf", "png"):
        out = os.path.join(run_dir, "figures",
                           f"fig_lifecycle_footprint_tau{tau}_paper.{ext}")
        fig.savefig(out, dpi=300, bbox_inches="tight", pad_inches=0.01)
    plt.close(fig)
    print(f"[paper] wrote fig_lifecycle_footprint_tau{tau}_paper.pdf/png")


if __name__ == "__main__":
    main()
