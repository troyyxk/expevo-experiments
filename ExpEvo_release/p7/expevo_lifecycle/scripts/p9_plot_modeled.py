"""Figure for the modeled upload time (Scheme A). Kept separate so it can be re-used."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Nimbus Roman", "Liberation Serif", "DejaVu Serif"],
    "font.size": 10, "axes.labelsize": 10, "xtick.labelsize": 10, "ytick.labelsize": 10,
    "legend.fontsize": 10, "axes.linewidth": 0.6,
    "mathtext.fontset": "custom", "mathtext.rm": "Nimbus Roman", "mathtext.it": "Nimbus Roman:italic",
    "pdf.fonttype": 42, "ps.fonttype": 42,
})


def plot_modeled(by_rate, out_base):
    rates = [r["rate_mbps"] for r in by_rate]
    raw = [r["raw_avg_ms_per_item"] for r in by_rate]
    dis = [r["distilled_avg_ms_per_item"] for r in by_rate]

    fig, ax = plt.subplots(figsize=(3.86, 3.05))
    fig.subplots_adjust(left=0.245, right=0.975, top=0.965, bottom=0.215)

    ax.plot(rates, raw, "-o", color="#3b6ea5", mfc="#3b6ea5", mec="#1f3f5f", mew=0.6,
            ms=4.4, lw=1.2, label="Raw episodes")
    ax.plot(rates, dis, "-s", color="#4a8f5b", mfc="#4a8f5b", mec="#244a2d", mew=0.6,
            ms=4.4, lw=1.2, label="Distilled experiences")

    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlim(min(rates) * 0.85, max(rates) * 1.45)
    ax.set_xticks(rates); ax.set_xticklabels([str(r) for r in rates])
    ax.set_xlabel("Effective uplink rate $R$ (Mbps)")
    ax.set_ylabel("Modeled upload time\n(ms/experience)", fontsize=10, labelpad=2)
    ticks = [0.03, 0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10]
    ax.set_yticks(ticks)
    ax.set_yticklabels(["0.03", "0.05", "0.1", "0.2", "0.5", "1", "2", "5", "10"])
    ax.set_ylim(0.025, 11)
    ax.grid(False)
    ax.legend(frameon=False, loc="upper right", handlelength=1.5, handletextpad=0.5, borderaxespad=0.2)

    for ext in ("pdf", "png"):
        fig.savefig(f"{out_base}.{ext}", dpi=300, bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)
    print("figure ->", out_base + ".pdf/.png")
