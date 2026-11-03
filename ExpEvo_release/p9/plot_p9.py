"""Published-format figure for P9: modeled D/R vs measured upload completion time."""
import argparse, csv, os
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams.update({"font.family": "serif", "font.serif": ["Nimbus Roman", "Liberation Serif", "DejaVu Serif"],
    "font.size": 8, "axes.labelsize": 8, "xtick.labelsize": 7.4, "ytick.labelsize": 7.4,
    "axes.linewidth": 0.6, "mathtext.fontset": "custom", "mathtext.rm": "Nimbus Roman",
    "mathtext.it": "Nimbus Roman:italic", "pdf.fonttype": 42, "ps.fonttype": 42})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    out = a.out or os.path.join(a.dir, "fig_p9_upload_time_measured")
    trials = list(csv.DictReader(open(os.path.join(a.dir, "trial_summary.csv"))))
    cal = {int(r["rate_mbps"]): r for r in csv.DictReader(open(os.path.join(a.dir, "calibration.csv")))}

    rates = sorted({int(t["rate_mbps"]) for t in trials})
    def series(mode, key):
        m, s = [], []
        for r in rates:
            v = [float(t[key]) for t in trials if int(t["rate_mbps"]) == r and t["mode"] == mode]
            m.append(np.mean(v)); s.append(np.std(v, ddof=1) if len(v) > 1 else 0.0)
        return np.array(m), np.array(s)

    raw_m, raw_s = series("raw", "batch_ms_mean")
    dis_m, dis_s = series("distilled", "batch_ms_mean")
    p_raw, p_dis = series("raw", "amortized_ms_per_item")
    # modeled time for ONE 1,000-item batch = per-item modeled time x 1000
    mod_raw = np.array([8 * 22080160 / (24000 * r * 1e6) * 1000 * 1000 for r in rates])
    mod_dis = np.array([8 * 4970488 / (24000 * r * 1e6) * 1000 * 1000 for r in rates])

    fig, axes = plt.subplots(1, 2, figsize=(7.85, 3.30), gridspec_kw={"width_ratios": [1.2, 1]})
    fig.subplots_adjust(left=0.135, right=0.985, top=0.94, bottom=0.20, wspace=0.30)
    ax = axes[0]
    ax.plot(rates, mod_raw, "--", color="#3b6ea5", lw=1.2, label="Raw, modeled $D/R$")
    ax.plot(rates, mod_dis, "--", color="#4a8f5b", lw=1.2, label="Distilled, modeled $D/R$")
    ax.errorbar(rates, raw_m, yerr=raw_s, fmt="o", ms=4.2, mfc="#3b6ea5", mec="#1f3f5f", mew=0.7,
                color="#1f3f5f", lw=0.9, capsize=2, label="Raw, measured")
    ax.errorbar(rates, dis_m, yerr=dis_s, fmt="s", ms=4.2, mfc="#4a8f5b", mec="#244a2d", mew=0.7,
                color="#244a2d", lw=0.9, capsize=2, label="Distilled, measured")
    ax.set_xscale("log"); ax.set_yscale("log"); ax.set_xlim(min(rates) * 0.85, max(rates) * 1.6)
    ax.set_xticks(rates); ax.set_xticklabels([str(r) for r in rates])
    ax.set_xlabel("Configured uplink rate $R$ (Mbps)")
    ax.set_ylabel("Upload time per 1,000-item batch (ms)")
    ax.grid(ls=":", lw=0.45, alpha=0.7, which="both"); ax.set_axisbelow(True)
    ax.legend(frameon=False, loc="lower left", fontsize=6.6, handlelength=1.6)

    ax = axes[1]
    save_mod = [100 * (1 - m / r) for m, r in zip(mod_dis, mod_raw)]
    save_meas = [100 * (1 - d / r) for d, r in zip(dis_m, raw_m)]
    ax.plot(rates, save_mod, "--", color="#666666", lw=1.2, label="modeled $D/R$")
    ax.plot(rates, save_meas, "o-", ms=4.2, mfc="#d98b5f", mec="#8a4a20", mew=0.7, color="#8a4a20",
            lw=1.1, label="measured")
    for r, v in zip(rates, save_meas):
        ax.annotate(f"{v:.1f}", (r, v), textcoords="offset points", xytext=(0, 6), ha="center", fontsize=6)
    ax.set_xscale("log"); ax.set_xlim(min(rates) * 0.85, max(rates) * 1.6)
    lo = min(min(save_meas), min(save_mod)) - 2; hi = max(max(save_meas), max(save_mod)) + 2
    ax.set_ylim(lo, hi)
    ax.set_xticks(rates); ax.set_xticklabels([str(r) for r in rates])
    ax.set_xlabel("Configured uplink rate $R$ (Mbps)")
    ax.set_ylabel("Upload-time saving (%)")
    ax.grid(ls=":", lw=0.45, alpha=0.7, which="both"); ax.set_axisbelow(True)
    ax.legend(frameon=False, loc="lower left", fontsize=6.6, handlelength=1.6)

    for ext in ("pdf", "png"):
        fig.savefig(f"{out}.{ext}", dpi=300, bbox_inches="tight", pad_inches=0.02)
    print("figure ->", out + ".pdf/.png")
    for r, rm, dm, sm, sv in zip(rates, raw_m, dis_m, save_meas, save_mod):
        print(f"  {r:>2} Mbps: measured raw {rm:8.1f} ms, dist {dm:6.1f} ms, saving {sm:.1f}% (modeled {sv:.1f}%)")


if __name__ == "__main__":
    main()
