"""Plot Fig.4 (plain vs memory vs experience) from out/fig4.json."""
import json
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "out")


def main():
    d = json.load(open(os.path.join(OUT, "fig4.json")))
    ps = d["passes"]
    x = np.arange(len(ps))
    plain = np.array([p["plain"] for p in ps])
    mem = np.array([p["memory"] for p in ps])
    exp = np.array([p["experience"] for p in ps])
    w = 0.27

    fig, ax = plt.subplots(figsize=(9.2, 4.4))
    ax.bar(x - w, plain, w, label=f"Plain (Avg {plain.mean() / 100:.3f})", color="#4C72B0")
    ax.bar(x, mem, w, label=f"Memory (Avg {mem.mean() / 100:.3f})", color="#DD8452")
    ax.bar(x + w, exp, w, label=f"Experience (Avg {exp.mean() / 100:.3f})", color="#55A868")
    ax.set_xticks(x)
    ax.set_xticklabels([f"Test {p['pass']}" for p in ps], rotation=60, fontsize=7)
    ax.set_ylabel("Accuracy (%)")
    ax.set_ylim(0, 100)
    ax.set_title(f"Fig.4 reproduction — MMLU high_school_biology, 80/20 split "
                 f"({d['n_train']} train / {d['n_test']} test, "
                 f"memory={d['n_memory']}, experience={d['n_experience']}, "
                 f"{d['model'].split('/')[-1]})", fontsize=8)
    ax.grid(axis="y", alpha=0.3)
    ax.legend(fontsize=8, loc="upper right")
    fig.tight_layout()
    p = os.path.join(OUT, "fig4.png")
    fig.savefig(p, dpi=160)
    plt.close(fig)

    print(f"plain      {plain.mean():.1f}%  (paper 50.8%)")
    print(f"memory     {mem.mean():.1f}%  (paper 51.4%)")
    print(f"experience {exp.mean():.1f}%  (paper 55.4%)")
    print(f"experience - plain    : {exp.mean() - plain.mean():+.1f} pts (paper +4.6)")
    print(f"experience - memory   : {exp.mean() - mem.mean():+.1f} pts (paper +4.0)")
    print(f"memory - plain        : {mem.mean() - plain.mean():+.1f} pts (paper +0.6)")
    print("plot:", p)


if __name__ == "__main__":
    main()
