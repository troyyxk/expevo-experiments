#!/usr/bin/env python3
"""Step 3: per-pool BM25 indices, Top-5 retrieval, prompt hashes and coverage diagnostics. No LLM."""
import csv
import hashlib
import json
import os
import sys
from collections import Counter

from rank_bm25 import BM25Okapi

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(os.path.dirname(HERE))
P7 = os.path.join(ROOT, "p7", "expevo_lifecycle", "runs", "p7_full100")
P10 = os.path.join(ROOT, "p7", "expevo_lifecycle", "runs", "p10_backend_refinement")
PREV = os.path.join(HERE, "..", "tsc_collaboration")
sys.path.insert(0, os.path.join(P10, "scripts"))
import evaluate_heldout as E

SUBJECT = "high_school_geography"
MATCHED_SEEDS = [20261109, 20261110, 20261111]


def read_jsonl(p):
    with open(p, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def main():
    assign = json.load(open(os.path.join(PREV, "config", "request_assignment.json")))["questions"]
    texts = {r["experience_id"]: r["text"] for r in read_jsonl(f"{P7}/full_repositories/{SUBJECT}.jsonl")}
    owner = {}
    for name in ["shared_full_hetero"] + [f"local_client_{c}" for c in range(4)] + \
                [f"shared_matched_hetero_{s}" for s in MATCHED_SEEDS]:
        meta = {r["experience_id"]: r for r in read_jsonl(os.path.join(HERE, "manifests", f"{name}.jsonl"))}
        owner[name] = meta

    pools = {}
    for name, meta in owner.items():
        ids = sorted(meta)
        pools[name] = {"ids": ids, "texts": [texts[i] for i in ids],
                       "bm25": BM25Okapi([E.tokenize(texts[i]) for i in ids], k1=1.5, b=0.75),
                       "hash": hashlib.sha256("\n".join(ids).encode()).hexdigest(),
                       "bytes": sum(len(texts[i].encode()) for i in ids)}

    rows = []
    top_by_setting = {}
    for q in assign:
        query = f"{q['question']} {' '.join(q['choices'])}"
        for policy, pname in ([("local_only", f"local_client_{q['requesting_client_id']}")] +
                              [("shared_matched", f"shared_matched_hetero_{s}") for s in MATCHED_SEEDS] +
                              [("shared_full_hetero", "shared_full_hetero")]):
            p = pools[pname]
            scores = p["bm25"].get_scores(E.tokenize(query))
            order = sorted(range(len(p["ids"])), key=lambda i: (-scores[i], p["ids"][i]))[:5]
            top = [{"id": p["ids"][i], "text": p["texts"][i], "score": float(scores[i])} for i in order]
            user = E.build_prompt(q, top)
            sha = hashlib.sha256((E.SYSTEM + "\n" + user).encode()).hexdigest()
            src_clients = [owner[pname][t["id"]]["client_id"] for t in top]
            src_qs = [owner[pname][t["id"]]["source_question_id"] for t in top]
            rows.append({"question_key": q["question_key"], "question_set": q["question_set"],
                         "requesting_client_id": q["requesting_client_id"], "policy": policy,
                         "pool": pname, "pool_seed": pname.split("_")[-1] if policy == "shared_matched" else "",
                         "pool_hash": p["hash"], "top5_ids": ";".join(t["id"] for t in top),
                         "top5_source_clients": ";".join(str(c) for c in src_clients),
                         "top5_source_questions": ";".join(src_qs),
                         "top5_from_other_clients": sum(1 for c in src_clients if c != q["requesting_client_id"]),
                         "n_distinct_source_questions": len(set(src_qs)),
                         "prompt_sha256": sha,
                         "retrieved_tokens": sum(len(E.tokenize(t["text"])) for t in top),
                         "repository_bytes": p["bytes"]})
            top_by_setting[(policy, q["question_key"])] = [t["id"] for t in top]

    os.makedirs(os.path.join(HERE, "retrieval"), exist_ok=True)
    with open(os.path.join(HERE, "retrieval", "retrieval_diagnostics.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)

    # summary: retrieval length, cross-client share, overlap between the two shared policies
    summ = []
    for policy in ["local_only", "shared_matched", "shared_full_hetero"]:
        sel = [r for r in rows if r["policy"] == policy]
        summ.append({"policy": policy, "n_queries": len(sel),
                     "mean_retrieved_tokens": round(sum(r["retrieved_tokens"] for r in sel) / len(sel), 2),
                     "mean_top5_other_clients": round(sum(r["top5_from_other_clients"] for r in sel) / len(sel), 2),
                     "mean_distinct_source_questions": round(sum(r["n_distinct_source_questions"] for r in sel) / len(sel), 2)})
    for r in summ:
        print(f"[retrieval] {r['policy']:<20} tokens={r['mean_retrieved_tokens']:>7} "
              f"top5_from_other_clients={r['mean_top5_other_clients']:.2f} "
              f"distinct_source_q={r['mean_distinct_source_questions']:.2f}")
    with open(os.path.join(HERE, "results", "retrieval_summary.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(summ[0].keys())); w.writeheader(); w.writerows(summ)

    for s in MATCHED_SEEDS:
        ov = sum(len(set(top_by_setting[("shared_matched", q)]) & set(top_by_setting[("shared_full_hetero", q)]))
                 for q in [x["question_key"] for x in assign]) / (5 * len(assign)) * 5
        print(f"[overlap] matched {s} vs full: {ov/5*100:.0f}% of Top-5 ids shared")


if __name__ == "__main__":
    main()
