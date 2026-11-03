#!/usr/bin/env python3
"""Final Fig. 6: P95 upload completion time under a shared uplink (trace-driven simulation)."""
import argparse, os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
plt.rcParams.update({"font.family": "serif", "font.serif": ["Nimbus Roman", "Liberation Serif", "DejaVu Serif"],
    "font.size": 10, "axes.labelsize": 10, "xtick.labelsize": 9.4, "ytick.labelsize": 9.4,
    "legend.fontsize": 9.2, "axes.linewidth": 0.6, "mathtext.fontset": "custom",
    "mathtext.rm": "Nimbus Roman", "mathtext.it": "Nimbus Roman:italic",
    "pdf.fonttype": 42, "ps.fonttype": 42})
C_RAW, C_DIS = "#3b6ea5", "#4a8f5b"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-run", default=os.path.join(ROOT, "results", "per_run.csv"))
    ap.add_argument("--out", default=os.path.join(ROOT, "images", "fig_upload_completion_simulation"))
    ap.add_argument("--layout", choices=["side", "stacked"], default="side")
    a = ap.parse_args()
    df = pd.read_csv(a.per_run)
    e1 = df[(df.experiment == "E1") & (df.overhead_bytes == 0)]
    e2 = df[(df.experiment == "E2") & (df.overhead_bytes == 0)]

    if a.layout == "stacked":
        plt.rcParams.update({"font.size": 8, "axes.labelsize": 8, "xtick.labelsize": 7.6,
                             "ytick.labelsize": 7.6, "legend.fontsize": 7.4})
    if a.layout == "side":
        fig, axes = plt.subplots(1, 2, figsize=(7.16, 2.72))
        fig.subplots_adjust(left=0.093, right=0.988, top=0.865, bottom=0.185, wspace=0.25)
    else:
        fig, axes = plt.subplots(2, 1, figsize=(3.47, 3.80))
        fig.subplots_adjust(left=0.175, right=0.985, top=0.975, bottom=0.105, hspace=0.42)

    # (a) P95 completion time vs clients
    ax = axes[0]
    for mode, color, lab, mk in (("raw", C_RAW, "Raw episodes", "o"),
                                 ("dist", C_DIS, "Distilled experiences", "s")):
        g = e1.groupby("M")[f"{mode}_p95_ms"].agg(["mean", "std"]).reset_index().sort_values("M")
        ax.errorbar(g["M"], g["mean"], yerr=g["std"], fmt=f"-{mk}", ms=4.4, lw=1.25,
                    color=color, mfc=color, mec="white", mew=0.5, capsize=2.2,
                    elinewidth=0.7, label=lab)
    ax.set_yscale("log"); ax.set_ylim(2.2, 450)
    ax.set_xlabel("Number of clients $M$")
    ax.grid(ls=":", lw=0.4, alpha=0.5); ax.set_axisbelow(True)

    # (b) paired P95 reduction vs offered load
    ax = axes[1]
    red = e2.assign(red=100 * (1 - e2.dist_p95_ms / e2.raw_p95_ms))
    g = red.groupby("target_rho_raw")["red"].agg(["mean", "std"]).reset_index().sort_values("target_rho_raw")
    ax.errorbar(g["target_rho_raw"], g["mean"], yerr=g["std"], fmt="-o", ms=4.4, lw=1.25,
                color="#8a4a20", mfc="#d98b5f", mec="#8a4a20", mew=0.6, capsize=2.2,
                elinewidth=0.7, label="P95 reduction")
    ax.axhline(77.5, ls="--", lw=0.9, color="#666666")
    ax.text(0.30, 78.6, "Payload reduction: 77.5%", fontsize=8, color="#666666", va="bottom")
    ax.set_ylim(74, 101)
    ax.set_xticks([0.3, 0.6, 0.85, 0.95]); ax.set_xticklabels(["0.30", "0.60", "0.85", "0.95"])
    ax.set_xlim(0.24, 1.0)
    ax.set_xlabel(r"Offered load of raw uploads $\rho_{\mathrm{raw}}$")
    ax.set_ylabel("P95 reduction (%)" if a.layout == "stacked" else "P95 completion-time reduction (%)")
    ax.grid(ls=":", lw=0.4, alpha=0.5); ax.set_axisbelow(True)

    axes[0].set_xscale("log")
    axes[0].set_xticks([10, 20, 50, 100])
    axes[0].set_xticklabels(["10", "20", "50", "100"])
    axes[0].set_xlim(8.5, 118)
    axes[0].set_ylabel("P95 completion time (ms)" if a.layout == "stacked" else "P95 upload completion time (ms)")
    h, l = axes[0].get_legend_handles_labels()
    if a.layout == "side":
        fig.legend(h, l, loc="upper center", ncol=2, frameon=False, bbox_to_anchor=(0.5, 1.0),
                   handlelength=1.6, columnspacing=2.0, handletextpad=0.5, borderaxespad=0.1)
        for ax, lab in zip(axes, ("(a)", "(b)")):
            ax.text(0.0, 1.015, lab, transform=ax.transAxes, fontsize=10, ha="left", va="bottom")
    else:
        axes[0].legend(handles=h, labels=l, loc="upper left", frameon=False, handlelength=1.5,
                       fontsize=8.4, borderaxespad=0.2)
        for ax, lab in zip(axes, ("(a)", "(b)")):
            ax.text(0.0, 1.015, lab, transform=ax.transAxes, fontsize=9.4, ha="left", va="bottom")
    for ext in ("pdf", "png"):
        fig.savefig(f"{a.out}.{ext}", dpi=300, bbox_inches="tight", pad_inches=0.02)
    print("figure ->", a.out + ".pdf/.png")


if __name__ == "__main__":
    main()
