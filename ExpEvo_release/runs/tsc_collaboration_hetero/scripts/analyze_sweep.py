#!/usr/bin/env python3
"""Coverage-accuracy curve at fixed 375 entries, plus the covered/uncovered decomposition."""
import collections, csv, json, os
import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
rows = [json.loads(l) for l in open(os.path.join(HERE, "predictions", "coverage_sweep.jsonl"))]
cov = [json.loads(l) for l in open(os.path.join(HERE, "predictions", "covered_questions.jsonl"))]
SEEDS = ("20261109", "20261110", "20261111")


def per_q(rs):
    d = collections.defaultdict(list)
    for r in rs:
        d[r["question_key"]].append(1 if r.get("correct") else 0)
    return {k: float(np.mean(v)) for k, v in d.items()}


loc = per_q([r for r in cov if r["policy"] == "local_only"])
m = {s: per_q([r for r in cov if r["policy"] == "shared_matched" and r["pool_seed"] == s]) for s in SEEDS}
matched = {k: float(np.mean([m[s][k] for s in SEEDS])) for k in loc}
rng = np.random.default_rng(20261122)
out = []


def add(n, d, label):
    keys = sorted(d)
    acc = 100 * np.mean([d[k] for k in keys])
    b = [100 * np.mean([d[k] for k in [keys[i] for i in rng.integers(0, len(keys), len(keys))]])
         for _ in range(5000)]
    out.append({"coverage_questions": n, "coverage_percent": f"{100*n/60:.0f}", "entries": 375,
                "entries_per_covered_question": f"{375/n:.1f}", "label": label,
                "accuracy_percent": f"{acc:.2f}",
                "ci_lower": f"{np.percentile(b,2.5):.2f}", "ci_upper": f"{np.percentile(b,97.5):.2f}"})


add(15, loc, "Local-only")
for n in (30, 45):
    add(n, per_q([r for r in rows if r["coverage"] == n]), f"shared coverage {n}/60")
add(60, matched, "Shared-matched")

with open(os.path.join(HERE, "results", "coverage_sweep.csv"), "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
    w.writeheader(); w.writerows(out)

# decomposition
dec = []
for n in (30, 45):
    for flag in (True, False):
        rs = [r for r in rows if r["coverage"] == n and r["covered"] == flag]
        dec.append({"coverage_questions": n, "subset": "covered" if flag else "not_covered",
                    "n_questions": len({r["question_key"] for r in rs}),
                    "accuracy_percent": f"{100*np.mean([1 if r['correct'] else 0 for r in rs]):.2f}"})
with open(os.path.join(HERE, "results", "coverage_sweep_decomposition.csv"), "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(dec[0].keys()))
    w.writeheader(); w.writerows(dec)

for r in out:
    print(f"{r['label']:<24}{r['coverage_questions']:>3}/60  {r['accuracy_percent']:>6}%  "
          f"[{r['ci_lower']}, {r['ci_upper']}]  ({r['entries_per_covered_question']} 条/题)")
print()
for r in dec:
    print(f"  {r['coverage_questions']}/60 {r['subset']:<12} n={r['n_questions']:>2}  {r['accuracy_percent']}%")
