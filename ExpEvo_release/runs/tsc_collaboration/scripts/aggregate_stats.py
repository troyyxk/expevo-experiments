#!/usr/bin/env python3
"""Phase 5: per-question accuracy, per-pool accuracy, paired differences and question-level bootstrap.

The statistical unit is the question (55 of them), never the 550 responses or the 3 pools.
"""
import argparse
import collections
import csv
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MATCHED_SEEDS = ["20261103", "20261104", "20261105"]


def read_jsonl(p):
    with open(p, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bootstrap", type=int, default=5000)
    ap.add_argument("--seed", type=int, default=20261107)
    a = ap.parse_args()

    assign = json.load(open(f"{HERE}/config/request_assignment.json"))
    questions = assign["questions"]
    qkeys = [q["question_key"] for q in questions]
    assert len(qkeys) == 55 and len(set(qkeys)) == 55

    preds = read_jsonl(f"{HERE}/predictions/predictions.jsonl")
    by = collections.defaultdict(list)
    for r in preds:
        by[(r["policy"], str(r["pool_seed"]), r["question_key"])].append(r)

    series = {}   # name -> {qkey: accuracy}
    counts = {}
    for name, policy, seed in ([("local_only", "local_only", "")] +
                               [(f"shared_matched_{s}", "shared_matched", s) for s in MATCHED_SEEDS] +
                               [("shared_full", "shared_full", "")]):
        per_q = {}
        for q in qkeys:
            rs = by[(policy, seed, q)]
            assert len(rs) == 10, (name, q, len(rs))
            per_q[q] = sum(1 for r in rs if r.get("correct")) / 10.0
        series[name] = per_q
        counts[name] = len(by[(policy, seed, qkeys[0])])

    # shared_matched summary = average the three pools within each question
    matched = {q: np.mean([series[f"shared_matched_{s}"][q] for s in MATCHED_SEEDS]) for q in qkeys}
    series["shared_matched"] = matched

    qrows = []
    for q in qkeys:
        for name in ["local_only", "shared_matched"] + [f"shared_matched_{s}" for s in MATCHED_SEEDS] + ["shared_full"]:
            qrows.append({"question_key": q, "policy": name, "pool_seed": name.split("_")[-1]
                          if name.startswith("shared_matched_") else "",
                          "accuracy_fraction": f"{series[name][q]:.4f}"})
    with open(f"{HERE}/results/accuracy_by_question.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(qrows[0].keys())); w.writeheader(); w.writerows(qrows)

    # point estimates
    point = {name: 100 * np.mean([series[name][q] for q in qkeys]) for name in series}

    # question-level paired bootstrap
    rng = np.random.default_rng(a.seed)
    names = ["local_only", "shared_matched", "shared_full"] + [f"shared_matched_{s}" for s in MATCHED_SEEDS]
    X = {n: np.array([series[n][q] for q in qkeys]) for n in names}
    absb = {n: [] for n in names}
    difb = {"matched_minus_local": [], "full_minus_matched": [], "full_minus_local": []}
    for _ in range(a.bootstrap):
        idx = rng.integers(0, len(qkeys), len(qkeys))
        m = {n: 100 * X[n][idx].mean() for n in names}
        for n in names:
            absb[n].append(m[n])
        difb["matched_minus_local"].append(m["shared_matched"] - m["local_only"])
        difb["full_minus_matched"].append(m["shared_full"] - m["shared_matched"])
        difb["full_minus_local"].append(m["shared_full"] - m["local_only"])

    pool_rows = []
    diag = json.load(open(f"{HERE}/retrieval/retrieval_diagnostics.csv")) if False else None
    retr = list(csv.DictReader(open(f"{HERE}/retrieval/retrieval_diagnostics.csv")))
    retr_tok = collections.defaultdict(list)
    for r in retr:
        retr_tok[r["pool"]].append(int(r["retrieved_tokens"]))
    for name in names:
        b = np.array(absb[name])
        key = {"local_only": "local_client_0", "shared_full": "shared_full"}.get(name)
        if name.startswith("shared_matched_"):
            key = f"shared_matched_seed_{name.split('_')[-1]}"
        elif name == "shared_matched":
            key = "shared_matched_seed_20261103"
        pool_rows.append({"policy": name, "pool_seed": name.split("_")[-1] if name.startswith("shared_matched_") else "",
                          "n_questions": len(qkeys), "n_responses": len(qkeys) * 10,
                          "accuracy_percent": f"{point[name]:.3f}",
                          "ci_lower_percent": f"{np.percentile(b, 2.5):.3f}",
                          "ci_upper_percent": f"{np.percentile(b, 97.5):.3f}",
                          "pool_hash": "", "repository_bytes": "",
                          "mean_retrieved_tokens": f"{np.mean(retr_tok.get(key, [0])):.1f}"})
    with open(f"{HERE}/results/accuracy_by_pool.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(pool_rows[0].keys())); w.writeheader(); w.writerows(pool_rows)

    prow = []
    for name, key in (("matched_minus_local", "Matched − Local"),
                      ("full_minus_matched", "Full − Matched"),
                      ("full_minus_local", "Full − Local")):
        d = np.array(difb[name])
        obs = {"matched_minus_local": point["shared_matched"] - point["local_only"],
               "full_minus_matched": point["shared_full"] - point["shared_matched"],
               "full_minus_local": point["shared_full"] - point["local_only"]}[name]
        prow.append({"comparison": key, "delta_pp": f"{obs:+.3f}",
                     "ci_lower_pp": f"{np.percentile(d, 2.5):+.3f}",
                     "ci_upper_pp": f"{np.percentile(d, 97.5):+.3f}",
                     "n_questions": len(qkeys), "bootstrap_seed": a.seed, "bootstrap_reps": a.bootstrap,
                     "pool_aggregation": "three fixed pools averaged within question"})
    # per-seed comparisons
    for s in MATCHED_SEEDS:
        nm = f"shared_matched_{s}"
        d1 = np.array(absb[nm]) - np.array(absb["local_only"])
        d2 = np.array(absb["shared_full"]) - np.array(absb[nm])
        prow.append({"comparison": f"Matched[{s}] − Local", "delta_pp": f"{point[nm]-point['local_only']:+.3f}",
                     "ci_lower_pp": f"{np.percentile(d1,2.5):+.3f}", "ci_upper_pp": f"{np.percentile(d1,97.5):+.3f}",
                     "n_questions": len(qkeys), "bootstrap_seed": a.seed, "bootstrap_reps": a.bootstrap,
                     "pool_aggregation": "single pool"})
        prow.append({"comparison": f"Full − Matched[{s}]", "delta_pp": f"{point['shared_full']-point[nm]:+.3f}",
                     "ci_lower_pp": f"{np.percentile(d2,2.5):+.3f}", "ci_upper_pp": f"{np.percentile(d2,97.5):+.3f}",
                     "n_questions": len(qkeys), "bootstrap_seed": a.seed, "bootstrap_reps": a.bootstrap,
                     "pool_aggregation": "single pool"})
    with open(f"{HERE}/results/paired_differences.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(prow[0].keys())); w.writeheader(); w.writerows(prow)

    with open(f"{HERE}/results/bootstrap_replicates.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["replicate", "local_only", "shared_matched", "shared_full",
                    "matched_minus_local", "full_minus_matched", "full_minus_local"])
        for i in range(a.bootstrap):
            w.writerow([i, f"{absb['local_only'][i]:.4f}", f"{absb['shared_matched'][i]:.4f}",
                        f"{absb['shared_full'][i]:.4f}", f"{difb['matched_minus_local'][i]:.4f}",
                        f"{difb['full_minus_matched'][i]:.4f}", f"{difb['full_minus_local'][i]:.4f}"])

    t2 = []
    for name, label, entries, src in (("local_only", "Local-only", 1500, 1),
                                      ("shared_matched", "Shared-matched", 1500, 4),
                                      ("shared_full", "Shared-full", 6000, 4)):
        t2.append({"setting": label, "entries": entries, "sources": src,
                   "accuracy_percent": f"{point[name]:.2f}",
                   "ci_lower": f"{np.percentile(absb[name], 2.5):.2f}",
                   "ci_upper": f"{np.percentile(absb[name], 97.5):.2f}"})
    with open(f"{HERE}/results/table_collaborative_sharing.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(t2[0].keys())); w.writeheader(); w.writerows(t2)

    print(f"bootstrap {a.bootstrap} reps over {len(qkeys)} questions (seed {a.seed})")
    for r in t2:
        print(f"  {r['setting']:<15} {r['accuracy_percent']:>6}%  [{r['ci_lower']}, {r['ci_upper']}]  "
              f"entries={r['entries']} sources={r['sources']}")
    for r in prow[:3]:
        print(f"  {r['comparison']:<18} {r['delta_pp']} pp  [{r['ci_lower_pp']}, {r['ci_upper_pp']}]")
    print("\nper-seed matched:", {s: round(point[f'shared_matched_{s}'], 2) for s in MATCHED_SEEDS})


if __name__ == "__main__":
    main()
