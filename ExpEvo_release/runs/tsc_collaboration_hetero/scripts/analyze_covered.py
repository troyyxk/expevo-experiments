#!/usr/bin/env python3
"""Statistics + figure for the covered-question experiment (same 60 questions, non-owning asker)."""
import collections, csv, json, os
import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEEDS = ("20261109", "20261110", "20261111")
rows = [json.loads(l) for l in open(os.path.join(HERE, "predictions", "covered_questions.jsonl"))]
owner = {r["experience_id"]: r["source_question_id"]
         for r in (json.loads(l) for l in open(os.path.join(HERE, "manifests", "shared_full_hetero.jsonl")))}


def per_q(rs):
    d = collections.defaultdict(list)
    for r in rs:
        d[r["question_key"]].append(1 if r.get("correct") else 0)
    return {k: float(np.mean(v)) for k, v in d.items()}


S = {"plain": per_q([r for r in rows if r["policy"] == "plain"]),
     "local_only": per_q([r for r in rows if r["policy"] == "local_only"]),
     "shared_full_hetero": per_q([r for r in rows if r["policy"] == "shared_full_hetero"])}
for s in SEEDS:
    S[f"m{s}"] = per_q([r for r in rows if r["policy"] == "shared_matched" and r["pool_seed"] == s])
S["shared_matched"] = {k: float(np.mean([S[f"m{s}"][k] for s in SEEDS])) for k in S["plain"]}
keys = sorted(S["plain"])
rng = np.random.default_rng(20261120)

out = []
for name, label, entries, cover in (("plain", "No experience", 0, 0),
                                    ("local_only", "Local-only", 375, 15),
                                    ("shared_matched", "Shared-matched", 375, 60),
                                    ("shared_full_hetero", "Shared-full", 1500, 60)):
    d = S[name]
    acc = 100 * np.mean([d[k] for k in keys])
    delta = np.array([100 * (d[k] - S["plain"][k]) for k in keys])
    b = [delta[rng.integers(0, len(keys), len(keys))].mean() for _ in range(5000)]
    ab = [100 * np.mean([d[k] for k in [keys[i] for i in rng.integers(0, len(keys), len(keys))]])
          for _ in range(5000)]
    rs = [r for r in rows if r["policy"] == name]
    hit = np.mean([sum(1 for i in r["top5_ids"] if owner[i] == r["question_key"]) for r in rs]) / 5 * 100 if rs else 0
    out.append({"condition": label, "entries": entries, "construction_questions": cover,
                "accuracy_percent": f"{acc:.2f}", "ci_lower": f"{np.percentile(ab,2.5):.2f}",
                "ci_upper": f"{np.percentile(ab,97.5):.2f}", "delta_vs_plain_pp": f"{delta.mean():+.2f}",
                "delta_ci_lower": f"{np.percentile(b,2.5):+.2f}", "delta_ci_upper": f"{np.percentile(b,97.5):+.2f}",
                "top5_own_question_percent": f"{hit:.0f}"})
with open(os.path.join(HERE, "results", "covered_questions.csv"), "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
    w.writeheader(); w.writerows(out)
for r in out:
    print(f"{r['condition']:<16}{r['accuracy_percent']:>7}%  [{r['ci_lower']}, {r['ci_upper']}]  "
          f"Δ {r['delta_vs_plain_pp']:>7}  own-in-top5 {r['top5_own_question_percent']:>3}%")
