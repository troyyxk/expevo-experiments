#!/usr/bin/env python3
"""Stratified paired bootstrap over held-out question IDs.

Each replicate resamples questions *within* every subject (stratified), recomputes every setting on the
same resample, and takes the macro average over subjects. The delta is Full-vs-setting on that same
resample, which is the paired comparison the paper needs.
"""
import csv, os, random, statistics as st

OUT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SETTINGS = ["Full", "BM25_100", "BM25_80", "BM25_60", "BM25_40"]
B = 5000
random.seed(20261028)

rows = list(csv.DictReader(open(os.path.join(OUT, "tables", "accuracy_by_question.csv"))))
q = {}
for r in rows:
    if r["question_accuracy"] != "":
        q.setdefault(r["setting"], {})[(r["subject"], r["question_id"])] = float(r["question_accuracy"])
subs = sorted({k[0] for k in q["Full"]})
by_sub = {s: sorted([k for k in q["Full"] if k[0] == s]) for s in subs}


def macro(setting, sample_by_sub):
    return 100 * sum(st.mean([q[setting][k] for k in sample_by_sub[s]]) for s in subs) / len(subs)


point = {s: macro(s, by_sub) for s in SETTINGS}
boots = {s: [] for s in SETTINGS}
paired = {s: [] for s in SETTINGS}
for _ in range(B):
    samp = {s: [by_sub[s][random.randrange(len(by_sub[s]))] for _ in by_sub[s]] for s in subs}
    vals = {s: macro(s, samp) for s in SETTINGS}
    for s in SETTINGS:
        boots[s].append(vals[s]); paired[s].append(vals[s] - vals["Full"])

out = []
for s in SETTINGS:
    b = sorted(boots[s]); d = sorted(paired[s])
    out.append({"setting": s, "accuracy_macro_pct": f"{point[s]:.2f}",
                "ci95_low": f"{b[int(0.025*B)]:.2f}", "ci95_high": f"{b[int(0.975*B)]:.2f}",
                "delta_pp": f"{point[s]-point['Full']:+.2f}",
                "delta_ci95_low": f"{d[int(0.025*B)]:+.2f}", "delta_ci95_high": f"{d[int(0.975*B)]:+.2f}",
                "paired_bootstrap": "true", "stratified_by_subject": "true",
                "n_questions": sum(len(by_sub[s]) for s in subs), "n_bootstrap": B})
with open(os.path.join(OUT, "tables", "accuracy_bootstrap_ci.csv"), "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(out[0].keys())); w.writeheader(); w.writerows(out)

half = max((float(r["ci95_high"]) - float(r["ci95_low"])) / 2 for r in out)
dhalf = max(abs(float(r["delta_ci95_high"])) for r in out)
print(f"stratified paired bootstrap over {out[0]['n_questions']} question IDs, {B} resamples")
print(f"marginal CI half-width up to {half:.1f} pp; delta CI to {dhalf:.1f} pp")
for r in out:
    print(f"{r['setting']:<9} {r['accuracy_macro_pct']:>6} [{r['ci95_low']}, {r['ci95_high']}]  "
          f"delta {r['delta_pp']} [{r['delta_ci95_low']}, {r['delta_ci95_high']}]")
