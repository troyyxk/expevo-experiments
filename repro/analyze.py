"""Make the figures + a short markdown summary from the reproduction runs."""
import glob
import json
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "out")


def load(name):
    p = os.path.join(OUT, name)
    if not os.path.exists(p):
        return None
    with open(p) as f:
        return json.load(f)


def fig5():
    d = load("fig5.json")
    if not d:
        return None
    h = d["history"]
    ep = [x["epoch"] for x in h]
    acc = [x["acc_strict"] for x in h]
    snap = [x["acc"] for x in h]
    cr = [x["conf_right"] for x in h]
    cw = [x["conf_wrong"] for x in h]

    fig, axes = plt.subplots(2, 1, figsize=(7.2, 6.2), sharex=True,
                             gridspec_kw={"height_ratios": [3, 2]})
    ax = axes[0]
    ax.plot(ep, acc, marker="o", color="#1f77b4", label="experience (strict exact-match)")
    ax.plot(ep, snap, marker="s", ls="--", color="#7fb3d5", label="experience (option-snap)")
    ax.set_ylabel("Accuracy (%)")
    ax.set_title(f"Fig.5 reproduction — MMLU high_school_biology "
                 f"({d['n_questions']} questions x {d['rounds']} answers/epoch, "
                 f"{d['model'].split('/')[-1]})", fontsize=9)
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8)
    ax2 = axes[1]
    ax2.plot(ep, cr, marker="^", color="#2ca02c", label="confidence on correct")
    ax2.plot(ep, cw, marker="v", color="#d62728", label="confidence on wrong")
    ax2.set_xlabel("Epoch")
    ax2.set_ylabel("Self-reported confidence")
    ax2.set_ylim(0, 100)
    ax2.grid(alpha=0.3)
    ax2.legend(fontsize=8)
    fig.tight_layout()
    p = os.path.join(OUT, "fig5.png")
    fig.savefig(p, dpi=160)
    plt.close(fig)
    return d, p


def fig6():
    d = load("fig6_eval.json")
    if not d:
        return None
    cfgs = d["configs"]
    order = ["full", "bm120", "bm100", "bm80", "bm60", "bm40", "bm30"]
    names = [c for c in order if c in cfgs]
    accs = [cfgs[c]["acc_strict"] for c in names]
    snaps = [cfgs[c]["acc"] for c in names]
    sizes = [cfgs[c]["db_size"] for c in names]

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2),
                             gridspec_kw={"width_ratios": [1, 1.5]})
    ax = axes[0]
    x = np.arange(len(names))
    ax.bar(x - 0.2, accs, 0.4, label="strict", color="#1f77b4")
    ax.bar(x + 0.2, snaps, 0.4, label="option-snap", color="#7fb3d5")
    ax.set_xticks(x)
    ax.set_xticklabels([f"{n}\n({s})" for n, s in zip(names, sizes)], fontsize=8)
    ax.set_ylabel("Accuracy (%)")
    ax.set_title("Full vs condensed experience DB", fontsize=9)
    ax.grid(axis="y", alpha=0.3)
    ax.legend(fontsize=8)

    ax = axes[1]
    full = np.array(cfgs["full"]["per_question_strict"])
    for name in names:
        if name == "full":
            continue
        cur = np.array(cfgs[name]["per_question_strict"])
        ax.plot(np.cumsum(cur - full), marker=".", ms=3, label=name)
    ax.axhline(0, color="k", lw=0.8)
    ax.set_xlabel("test question index")
    ax.set_ylabel("cumulative (condensed - full) accuracy")
    ax.set_title("Accumulated accuracy difference (paper Fig.6C metric)", fontsize=9)
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8)
    fig.tight_layout()
    p = os.path.join(OUT, "fig6.png")
    fig.savefig(p, dpi=160)
    plt.close(fig)
    return d, p


def main():
    r5 = fig5()
    r6 = fig6()
    lines = ["# Experience Scaling reproduction (high_school_biology)\n"]
    if r5:
        d, p = r5
        h = d["history"]
        lines.append(f"## Fig.5  ({d['n_questions']} q x {d['rounds']} ans, {d['model']})\n")
        lines.append("| epoch | acc strict % | acc snap % | conf(correct) | conf(wrong) | DB |")
        lines.append("|---|---|---|---|---|---|")
        for x in h:
            lines.append(f"| {x['epoch']} | {x['acc_strict']:.1f} | {x['acc']:.1f} | "
                         f"{x['conf_right']:.1f} | {x['conf_wrong']:.1f} | {x['db_size']} |")
        lines.append(f"\nplot: `{os.path.relpath(p, BASE)}`, data: `out/fig5.json`\n")
    if r6:
        d, p = r6
        lines.append(f"## Fig.6  (eval on {d['n_test']} held-out q, {d['rounds']} ans each)\n")
        lines.append("| config | DB size | acc strict % | acc snap % |")
        lines.append("|---|---|---|---|")
        for c, v in d["configs"].items():
            lines.append(f"| {c} | {v['db_size']} | {v['acc_strict']:.1f} | {v['acc']:.1f} |")
        lines.append(f"\nplot: `{os.path.relpath(p, BASE)}`, data: `out/fig6_eval.json`\n")
    if len(lines) > 1:
        with open(os.path.join(OUT, "summary.md"), "w") as f:
            f.write("\n".join(lines) + "\n")
        print("\n".join(lines))


if __name__ == "__main__":
    main()
