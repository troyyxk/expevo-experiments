"""Fig.4 analysis v2: per-question paired statistics + plot (fwd and rev splits)."""
import json
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "out")


def load(name):
    p = os.path.join(OUT, name)
    return json.load(open(p)) if os.path.exists(p) else None


def paired(d, cond_a, cond_b):
    A = np.array(d["per_question"][cond_a], float)
    B = np.array(d["per_question"][cond_b], float)
    diff = A - B
    n = len(diff)
    se = diff.std(ddof=1) / np.sqrt(n)
    rng = np.random.default_rng(0)
    boots = [rng.choice(diff, n, replace=True).mean() for _ in range(2000)]
    lo, hi = np.percentile(boots, [2.5, 97.5])
    return {
        "delta": diff.mean() / np.sum(A[:1]) if False else diff.mean(),
        "se": se,
        "t": diff.mean() / se if se else 0,
        "ci": (lo, hi),
        "wins": int((diff > 0).sum()),
        "losses": int((diff < 0).sum()),
        "n": n,
    }


def main():
    rows = []
    for tag, fname in [("fwd", "fig4.json"), ("rev", "fig4_rev.json")]:
        d = load(fname)
        if not d:
            continue
        P = np.array([p["plain"] for p in d["passes"]])
        M = np.array([p["memory"] for p in d["passes"]])
        E = np.array([p["experience"] for p in d["passes"]])
        print(f"\n=== split={tag}  passes={len(d['passes'])}  "
              f"train={d['n_train']} test={d['n_test']} "
              f"memory={d['n_memory']} experience={d['n_experience']} ===")
        print(f"plain {P.mean():.1f}%  memory {M.mean():.1f}%  experience {E.mean():.1f}%")
        pq = d["per_question"]
        # scale counts (0..passes) to percent
        k = len(d["passes"])
        for a, b, label in [("experience", "memory", "exp-mem"),
                            ("experience", "plain", "exp-plain"),
                            ("memory", "plain", "mem-plain")]:
            A = np.array(pq[a], float) / k * 100
            B = np.array(pq[b], float) / k * 100
            diff = A - B
            se = diff.std(ddof=1) / np.sqrt(len(diff))
            rng = np.random.default_rng(0)
            boots = [rng.choice(diff, len(diff), replace=True).mean() for _ in range(2000)]
            lo, hi = np.percentile(boots, [2.5, 97.5])
            print(f"  {label:<10} {diff.mean():+5.2f} pts  se={se:.2f} t={diff.mean()/se:5.2f}  "
                  f"95%CI[{lo:+.2f},{hi:+.2f}]  per-question wins {int((diff>0).sum())}"
                  f"/{int((diff<0).sum())} losses")
            rows.append((tag, label, diff.mean(), se, lo, hi))
        # memory-only accuracy on the subset where an experience exists? (skipped)

    # quick plot for the fwd split
    d = load("fig4.json")
    if d:
        ps = d["passes"]
        x = np.arange(len(ps))
        P = [p["plain"] for p in ps]
        M = [p["memory"] for p in ps]
        E = [p["experience"] for p in ps]
        w = 0.27
        fig, ax = plt.subplots(figsize=(9.0, 4.2))
        ax.bar(x - w, P, w, label=f"Plain (Avg {np.mean(P) / 100:.3f})", color="#4C72B0")
        ax.bar(x, M, w, label=f"Memory (Avg {np.mean(M) / 100:.3f})", color="#DD8452")
        ax.bar(x + w, E, w, label=f"Experience (Avg {np.mean(E) / 100:.3f})", color="#55A868")
        ax.set_xticks(x)
        ax.set_xticklabels([f"Test {p['pass']}" for p in ps], rotation=60, fontsize=6)
        ax.set_ylabel("Accuracy (%)")
        ax.set_ylim(0, 100)
        ax.grid(axis="y", alpha=0.3)
        ax.legend(fontsize=8)
        ax.set_title("Fig.4 (v2, 80/20 fwd split, strict) — paper: 0.508 / 0.514 / 0.554", fontsize=9)
        fig.tight_layout()
        fig.savefig(os.path.join(OUT, "fig4_v2.png"), dpi=160)
        print("\nsaved out/fig4_v2.png")


if __name__ == "__main__":
    main()
