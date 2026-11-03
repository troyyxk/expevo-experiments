#!/usr/bin/env python3
"""Is 'no same-question experience' a retrieval failure or a coverage gap?

Compares the BM25 score distribution of construction questions (whose experiences are in the pool)
with the 55 evaluation questions (which have none), and asks how many of the latter a simple
score threshold would have flagged as "no relevant experience in the repository".
"""
import json, os, sys
import numpy as np
from rank_bm25 import BM25Okapi

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(os.path.dirname(HERE))
P7 = os.path.join(ROOT, "p7", "expevo_lifecycle", "runs", "p7_full100")
P10 = os.path.join(ROOT, "p7", "expevo_lifecycle", "runs", "p10_backend_refinement")
sys.path.insert(0, os.path.join(P10, "scripts"))
import evaluate_heldout as E

man = [json.loads(l) for l in open(os.path.join(HERE, "manifests", "shared_full_hetero.jsonl"))]
ids = [r["experience_id"] for r in man]
owner = {r["experience_id"]: r["source_question_id"] for r in man}
txt = {r["experience_id"]: r["text"]
       for r in (json.loads(l) for l in open(f"{P7}/full_repositories/high_school_geography.jsonl"))}
bm = BM25Okapi([E.tokenize(txt[i]) for i in ids], k1=1.5, b=0.75)

eps = {e["episode_id"]: e for e in (json.loads(l) for l in open(f"{P7}/episodes/high_school_geography.jsonl"))}
by_q = {}
for e in eps.values():
    by_q.setdefault(e["source_question_id"], e)
con = [dict(by_q[q], qid=q) for q in sorted(by_q)]
hed = [dict(q) for q in (json.loads(l) for l in open(f"{P7}/heldout/high_school_geography.jsonl"))]
hed += [q for q in (json.loads(l) for l in open(f"{P10}/eval/heldout_extended.jsonl"))
        if q["subject"] == "high_school_geography"]
for q in hed:
    q.setdefault("qid", q.get("question_id"))


def stats(qs):
    t1, m5, hit = [], [], []
    for q in qs:
        s = bm.get_scores(E.tokenize(f"{q['question']} {' '.join(q['choices'])}"))
        order = np.argsort(-s)[:5]
        t1.append(s[order[0]])
        m5.append(float(np.mean([s[i] for i in order])))
        hit.append(any(owner[ids[i]] == q["qid"] for i in order))
    return np.array(t1), np.array(m5), np.array(hit)


c1, c5, ch = stats(con)
h1, h5, hh = stats(hed)
tau = float(np.percentile(c1, 5))
rows = [
    {"group": "construction", "n": len(con), "top1_mean": f"{c1.mean():.2f}",
     "top5_mean": f"{c5.mean():.2f}", "own_experience_rate": f"{100*ch.mean():.0f}"},
    {"group": "held_out", "n": len(hed), "top1_mean": f"{h1.mean():.2f}",
     "top5_mean": f"{h5.mean():.2f}", "own_experience_rate": f"{100*hh.mean():.0f}"},
]
import csv
with open(os.path.join(HERE, "results", "coverage_gap.csv"), "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader(); w.writerows(rows)
    f.write(f"\n# threshold tau={tau:.2f} (5th percentile of construction top-1); "
            f"share flagged 'no relevant experience': construction {100*(c1<tau).mean():.0f}%, "
            f"held-out {100*(h1<tau).mean():.0f}%\n")
print(f"construction: top1={c1.mean():.2f} top5={c5.mean():.2f} own={100*ch.mean():.0f}%")
print(f"held-out    : top1={h1.mean():.2f} top5={h5.mean():.2f} own={100*hh.mean():.0f}%")
print(f"tau={tau:.2f} -> abstain-worthy: construction {100*(c1<tau).mean():.0f}%, "
      f"held-out {100*(h1<tau).mean():.0f}%")
