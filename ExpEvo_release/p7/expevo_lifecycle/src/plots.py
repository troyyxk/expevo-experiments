"""Publication figures for the P7 lifecycle experiment (all values from CSVs)."""
import argparse
import csv
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from .common import load_config

SUB_SHORT = {
    "international_law": "International\nLaw",
    "college_medicine": "College\nMedicine",
    "college_biology": "College\nBiology",
    "high_school_geography": "High School\nGeography",
}
plt.rcParams.update({"font.family": "serif", "font.size": 9, "axes.linewidth": 0.8})


def read_csv(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--tau", type=int, default=100,
                    help="threshold used for the third bar; 100 = official main figure")
    args = ap.parse_args()
    cfg = load_config(args.config)
    run_dir = os.path.abspath(os.path.join(cfg["runtime"]["runs_dir"], cfg["run_id"]))
    fig_dir = os.path.join(run_dir, "figures")
    os.makedirs(fig_dir, exist_ok=True)
    tabs = os.path.join(run_dir, "tables")

    foot = read_csv(os.path.join(tabs, "lifecycle_footprint.csv"))
    ref = read_csv(os.path.join(tabs, "refinement_metrics.csv"))
    lat = read_csv(os.path.join(tabs, "upload_latency.csv"))
    subs = [r["subject"] for r in foot]
    labels = [SUB_SHORT.get(s, s) for s in subs]

    # ---- fig 1: lifecycle footprint (BM25 100) -------------------------
    raw = np.array([float(r["raw_total_bytes"]) / 1e6 for r in foot])
    dis = np.array([float(r["distilled_total_bytes"]) / 1e6 for r in foot])
    tau = int(args.tau)
    if tau == 100:
        ref_bytes = np.array([float(r.get("refined_bytes_bm100", r["distilled_total_bytes"])) for r in foot])
    else:
        by_sub = {r["subject"]: float(r["refined_bytes"]) for r in ref if int(float(r["threshold"])) == tau}
        ref_bytes = np.array([by_sub.get(r["subject"], float(r["distilled_total_bytes"])) for r in foot])
    ref100 = ref_bytes / 1e6
    fig, ax = plt.subplots(figsize=(7.2, 4.1))
    x = np.arange(len(subs)); w = 0.26
    ax.bar(x - w, raw, w, label="Raw episodes (counterfactual upload)", color="#4C72B0",
           edgecolor="k", linewidth=.4)
    ax.bar(x, dis, w, label="Distilled experiences (actual upload)", color="#55A868",
           edgecolor="k", linewidth=.4)
    ax.bar(x + w, ref100, w, label=f"Refined repository (BM25 = {tau}, backend)", color="#DD8452",
           edgecolor="k", linewidth=.4)
    for i in range(len(subs)):
        for xx, v in ((x[i] - w, raw[i]), (x[i], dis[i]), (x[i] + w, ref100[i])):
            ax.text(xx, v + max(raw) * 0.01, f"{v:.3f}", ha="center", va="bottom", fontsize=6.3)
        up = 100 * (1 - dis[i] / raw[i]) if raw[i] else 0
        st = 100 * (1 - ref100[i] / dis[i]) if dis[i] else 0
        ax.text(x[i], raw[i] * 1.09, f"upload −{up:.0f}%  ·  storage −{st:.0f}%",
                ha="center", fontsize=6.3, color="#333333")
    ax.set_xticks(x); ax.set_xticklabels(labels, fontsize=8)
    ax.set_ylabel("Total serialized data (MB)")
    ax.set_ylim(0, max(raw) * 1.24 if len(raw) else 1)
    ax.grid(axis="y", ls=":", lw=.5, alpha=.6); ax.set_axisbelow(True)
    ax.legend(fontsize=6.6, frameon=False, ncol=3, loc="upper center",
              bbox_to_anchor=(0.5, -0.17), handlelength=1.2, columnspacing=1.2)
    n_q = foot[0]["n_questions"] if foot else "?"
    ax.set_title("Experience lifecycle data footprint\n"
                 f"({n_q} construction questions per subject, "
                 f"{cfg['data']['repeats']} interactions each)", fontsize=8.8, pad=14)
    if tau != 100:
        ax.text(0.5, 1.015,
                f"Exploratory setting: BM25 $\\tau$ = {tau}  "
                f"(official main figure reports $\\tau$ = 100)",
                transform=ax.transAxes, ha="center", va="bottom",
                fontsize=7.2, style="italic", color="#B03030")
    fig.tight_layout()
    fname = "fig_lifecycle_footprint" if tau == 100 else f"fig_lifecycle_footprint_tau{tau}"
    for ext in ("png", "pdf"):
        fig.savefig(os.path.join(fig_dir, f"{fname}.{ext}"), dpi=300, bbox_inches="tight")
    plt.close(fig)

    # ---- fig 2: modeled upload latency --------------------------------
    fig, ax = plt.subplots(figsize=(4.6, 3.2))
    rates = sorted({int(r["rate_mbps"]) for r in lat})
    raw_ms = [np.mean([float(r["raw_avg_ms_per_episode"]) for r in lat if int(r["rate_mbps"]) == rr])
              for rr in rates]
    dis_ms = [np.mean([float(r["distilled_avg_ms_per_episode"]) for r in lat if int(r["rate_mbps"]) == rr])
              for rr in rates]
    ax.plot(rates, raw_ms, marker="o", ms=4, color="#4C72B0", label="Raw episode upload")
    ax.plot(rates, dis_ms, marker="s", ms=4, color="#55A868", label="Distilled experience upload")
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xticks(rates); ax.set_xticklabels([str(r) for r in rates])
    ax.set_xlabel("Uplink rate $R$ (Mbps)")
    ax.set_ylabel("Modeled upload time per episode (ms)")
    ax.grid(ls=":", lw=.5, alpha=.6, which="both"); ax.legend(fontsize=7, frameon=False)
    ax.set_title("Modeled upload time  $D/R$  (not measured network latency)", fontsize=8.5)
    fig.tight_layout()
    for ext in ("png", "pdf"):
        fig.savefig(os.path.join(fig_dir, f"fig_modeled_upload_latency.{ext}"), dpi=300)
    plt.close(fig)

    # ---- fig 3: refinement storage proxy ------------------------------
    fig, axs = plt.subplots(1, 2, figsize=(7.0, 2.8))
    ths = sorted({int(r["threshold"]) for r in ref}, reverse=True)
    for s in subs:
        y = [float(r["refined_bytes"]) / 1e6 for t in ths
             for r in ref if r["subject"] == s and int(r["threshold"]) == t]
        axs[0].plot(ths, y, marker="o", ms=3, lw=1, label=SUB_SHORT.get(s, s).replace("\n", " "))
    axs[0].set_xlabel("BM25 condensation threshold $\\tau$")
    axs[0].set_ylabel("Refined storage (MB)")
    axs[0].invert_xaxis(); axs[0].grid(ls=":", lw=.5, alpha=.6)
    axs[0].legend(fontsize=5.6, frameon=False)
    axs[0].set_title("(a) Backend storage", fontsize=8)
    for s in subs:
        y = [100 * float(r["normalized_entry_ratio"]) for t in ths
             for r in ref if r["subject"] == s and int(r["threshold"]) == t]
        axs[1].plot(ths, y, marker="s", ms=3, lw=1, label=SUB_SHORT.get(s, s).replace("\n", " "))
    axs[1].set_xlabel("BM25 condensation threshold $\\tau$")
    axs[1].set_ylabel("Entries remaining (%)")
    axs[1].invert_xaxis(); axs[1].grid(ls=":", lw=.5, alpha=.6); axs[1].set_ylim(0, 105)
    axs[1].set_title("(b) Indexed-entry ratio (retrieval-workload proxy)", fontsize=8)
    fig.tight_layout()
    for ext in ("png", "pdf"):
        fig.savefig(os.path.join(fig_dir, f"fig_refinement_storage_proxy.{ext}"), dpi=300)
    plt.close(fig)
    print("[plots] wrote", ", ".join(sorted(os.listdir(fig_dir))))


if __name__ == "__main__":
    main()
