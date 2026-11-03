#!/usr/bin/env python3
"""Step 6: per-question accuracy, per-pool accuracy, paired differences, question-level bootstrap.

Statistical unit: the question (55). Matched = three pools averaged within question.
"""
import argparse
import collections
import csv
import json
import os

import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MATCHED_SEEDS = ["20261109", "20261110", "20261111"]


def read_jsonl(p):
    with open(p, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bootstrap", type=int, default=5000)
    ap.add_argument("--seed", type=int, default=20261112)
    a = ap.parse_args()
    rng = np.random.default_rng(a.seed)

    assign = json.load(open(os.path.join(HERE, "..", "tsc_collaboration", "config", "request_assignment.json")))
    qkeys = [q["question_key"] for q in assign["questions"]]
    preds = read_jsonl(os.path.join(HERE, "predictions", "predictions.jsonl"))
    by = collections.defaultdict(list)
    for r in preds:
        by[(r["policy"], str(r["pool_seed"]), r["question_key"])].append(r)

    series = {}
    for name, policy, seed in ([("local_only", "local_only", "")] +
                               [(f"shared_matched_{s}", "shared_matched", s) for s in MATCHED_SEEDS] +
                               [("shared_full_hetero", "shared_full_hetero", "")]):
        per_q = {}
        for q in qkeys:
            rs = by[(policy, seed, q)]
            assert len(rs) == 10, (name, q, len(rs))
            per_q[q] = sum(1 for r in rs if r.get("correct")) / 10.0
        series[name] = per_q
    series["shared_matched"] = {q: float(np.mean([series[f"shared_matched_{s}"][q] for s in MATCHED_SEEDS]))
                                for q in qkeys}

    rows = []
    for q in qkeys:
        for name in list(series):
            rows.append({"question_key": q, "series": name,
                         "accuracy_fraction": f"{series[name][q]:.4f}"})
    with open(os.path.join(HERE, "results", "accuracy_by_question.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)

    names = ["local_only", "shared_matched", "shared_full_hetero"] + [f"shared_matched_{s}" for s in MATCHED_SEEDS]
    X = {n: np.array([series[n][q] for q in qkeys]) for n in names}
    point = {n: 100 * X[n].mean() for n in names}
    absb = {n: [] for n in names}
    difb = {k: [] for k in ("matched_minus_local", "full_minus_matched", "full_minus_local")}
    for _ in range(a.bootstrap):
        idx = rng.integers(0, len(qkeys), len(qkeys))
        m = {n: 100 * X[n][idx].mean() for n in names}
        for n in names:
            absb[n].append(m[n])
        difb["matched_minus_local"].append(m["shared_matched"] - m["local_only"])
        difb["full_minus_matched"].append(m["shared_full_hetero"] - m["shared_matched"])
        difb["full_minus_local"].append(m["shared_full_hetero"] - m["local_only"])

    retr = list(csv.DictReader(open(os.path.join(HERE, "retrieval", "retrieval_diagnostics.csv"))))
    tok = collections.defaultdict(list)
    for r in retr:
        tok[(r["policy"], r["pool"])].append(int(r["retrieved_tokens"]))
    pool_key = {"local_only": "local_client_0", "shared_full_hetero": "shared_full_hetero",
                "shared_matched": "shared_matched_hetero_20261109"}
    prow = []
    for name in names:
        key = ({"local_only": "local_only", "shared_full_hetero": "shared_full_hetero"}.get(name, "shared_matched"),
               pool_key.get(name, f"shared_matched_hetero_{name.split('_')[-1]}"))
        b = np.array(absb[name])
        prow.append({"policy": name, "n_questions": len(qkeys), "n_responses": len(qkeys) * 10,
                     "accuracy_percent": f"{point[name]:.3f}",
                     "ci_lower_percent": f"{np.percentile(b, 2.5):.3f}",
                     "ci_upper_percent": f"{np.percentile(b, 97.5):.3f}",
                     "mean_retrieved_tokens": f"{np.mean(tok.get(key, [0])):.1f}"})
    with open(os.path.join(HERE, "results", "accuracy_by_pool.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(prow[0].keys())); w.writeheader(); w.writerows(prow)

    drow = []
    for key, label, obs in (("matched_minus_local", "Matched − Local", point["shared_matched"] - point["local_only"]),
                            ("full_minus_matched", "Full − Matched", point["shared_full_hetero"] - point["shared_matched"]),
                            ("full_minus_local", "Full − Local", point["shared_full_hetero"] - point["local_only"])):
        d = np.array(difb[key])
        drow.append({"comparison": label, "delta_pp": f"{obs:+.3f}",
                     "ci_lower_pp": f"{np.percentile(d, 2.5):+.3f}",
                     "ci_upper_pp": f"{np.percentile(d, 97.5):+.3f}",
                     "n_questions": len(qkeys), "bootstrap_seed": a.seed, "bootstrap_reps": a.bootstrap,
                     "pool_aggregation": "three fixed pools averaged within question"})
    for s in MATCHED_SEEDS:
        nm = f"shared_matched_{s}"
        d1 = np.array(absb[nm]) - np.array(absb["local_only"])
        d2 = np.array(absb["shared_full_hetero"]) - np.array(absb[nm])
        drow.append({"comparison": f"Matched[{s}] − Local", "delta_pp": f"{point[nm]-point['local_only']:+.3f}",
                     "ci_lower_pp": f"{np.percentile(d1,2.5):+.3f}", "ci_upper_pp": f"{np.percentile(d1,97.5):+.3f}",
                     "n_questions": len(qkeys), "bootstrap_seed": a.seed, "bootstrap_reps": a.bootstrap,
                     "pool_aggregation": "single pool"})
        drow.append({"comparison": f"Full − Matched[{s}]",
                     "delta_pp": f"{point['shared_full_hetero']-point[nm]:+.3f}",
                     "ci_lower_pp": f"{np.percentile(d2,2.5):+.3f}", "ci_upper_pp": f"{np.percentile(d2,97.5):+.3f}",
                     "n_questions": len(qkeys), "bootstrap_seed": a.seed, "bootstrap_reps": a.bootstrap,
                     "pool_aggregation": "single pool"})
    with open(os.path.join(HERE, "results", "paired_differences.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(drow[0].keys())); w.writeheader(); w.writerows(drow)

    with open(os.path.join(HERE, "results", "bootstrap_replicates.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["replicate"] + names + ["matched_minus_local", "full_minus_matched", "full_minus_local"])
        for i in range(a.bootstrap):
            w.writerow([i] + [f"{absb[n][i]:.4f}" for n in names] +
                       [f"{difb[k][i]:.4f}" for k in ("matched_minus_local", "full_minus_matched", "full_minus_local")])

    table = []
    for label, name, entries, sources, cover in (("Local-only", "local_only", 375, 1, 15),
                                                 ("Shared-matched", "shared_matched", 375, 4, 60),
                                                 ("Shared-full-hetero", "shared_full_hetero", 1500, 4, 60)):
        b = np.array(absb[name])
        table.append({"setting": label, "entries": entries, "sources": sources,
                      "construction_questions": cover,
                      "accuracy_percent": f"{point[name]:.2f}",
                      "ci_lower": f"{np.percentile(b, 2.5):.2f}",
                      "ci_upper": f"{np.percentile(b, 97.5):.2f}"})
    with open(os.path.join(HERE, "results", "table_hetero.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(table[0].keys())); w.writeheader(); w.writerows(table)

    print(f"bootstrap {a.bootstrap} over {len(qkeys)} questions (seed {a.seed})")
    for r in table:
        print(f"  {r['setting']:<20}{r['accuracy_percent']:>7}%  [{r['ci_lower']}, {r['ci_upper']}]  "
              f"entries={r['entries']:>4} sources={r['sources']} Q={r['construction_questions']}")
    for r in drow[:3]:
        print(f"  {r['comparison']:<18}{r['delta_pp']:>8} pp  [{r['ci_lower_pp']}, {r['ci_upper_pp']}]")
    print("per-seed matched:", {s: round(point[f'shared_matched_{s}'], 2) for s in MATCHED_SEEDS})


if __name__ == "__main__":
    main()
