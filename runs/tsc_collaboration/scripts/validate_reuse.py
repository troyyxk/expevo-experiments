#!/usr/bin/env python3
"""Phase 3: build every pool's BM25 index, retrieve Top-5 for all 55 questions, and decide whether the
historical Shared-full predictions can be reused.

Writes retrieval/retrieval_diagnostics.csv and manifests/validate_reuse.json. No LLM calls.
"""
import csv
import hashlib
import json
import os
import sys

from rank_bm25 import BM25Okapi

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(os.path.dirname(HERE))
P7 = os.path.join(ROOT, "p7", "expevo_lifecycle", "runs", "p7_full100")
P10 = os.path.join(ROOT, "p7", "expevo_lifecycle", "runs", "p10_backend_refinement")
sys.path.insert(0, os.path.join(P10, "scripts"))
import evaluate_heldout as E  # tokenize / build_prompt / SYSTEM

SUBJECT = "high_school_geography"


def read_jsonl(p):
    with open(p, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def pool_items(name):
    """Return [(id, text)] for a pool manifest name."""
    if name == "full":
        path = f"{HERE}/manifests/shared_full.jsonl"
    elif name.startswith("matched_"):
        path = f"{HERE}/manifests/shared_matched_seed_{name.split('_')[1]}.jsonl"
    else:
        path = f"{HERE}/manifests/local_client_{name.split('_')[1]}.jsonl"
    sel = {r["experience_id"] for r in read_jsonl(path)}
    texts = {r["experience_id"]: r["text"] for r in read_jsonl(f"{P7}/full_repositories/{SUBJECT}.jsonl")}
    return [(i, texts[i]) for i in sorted(sel)]


def main():
    assign = json.load(open(f"{HERE}/config/request_assignment.json"))
    questions = assign["questions"]
    pools = ["full"] + [f"matched_{s}" for s in (20261103, 20261104, 20261105)] + \
            [f"local_{c}" for c in range(4)]

    # historical Shared-full evidence
    hist = {}
    for f in ("eval/predictions.jsonl", "eval/predictions_extended.jsonl"):
        for r in read_jsonl(os.path.join(P10, f)):
            if r["subject"] == SUBJECT and r["setting"] == "Full":
                qset = r.get("question_set", "original")
                hist[f"{qset}::{r['question_id']}"] = r

    rows, diag = [], {}
    for pool in pools:
        items = pool_items(pool)
        ids = [i for i, _ in items]
        bm25 = BM25Okapi([E.tokenize(t) for _, t in items], k1=1.5, b=0.75)
        pool_hash = hashlib.sha256("\n".join(ids).encode()).hexdigest()
        diffs = []
        for q in questions:
            query = f"{q['question']} {' '.join(q['choices'])}"
            scores = bm25.get_scores(E.tokenize(query))
            order = sorted(range(len(items)), key=lambda i: (-scores[i], ids[i]))[:5]
            top = [{"id": ids[i], "text": items[i][1], "score": float(scores[i])} for i in order]
            user = E.build_prompt(q, top)
            prompt_sha = hashlib.sha256((E.SYSTEM + "\n" + user).encode()).hexdigest()
            top_ids = [t["id"] for t in top]
            rec = {"question_key": q["question_key"], "policy": pool.split("_")[0],
                   "pool": pool, "pool_seed": pool.split("_")[1] if pool.startswith("matched") else "",
                   "requesting_client_id": q["requesting_client_id"], "pool_hash": pool_hash,
                   "top5_ids": ";".join(top_ids), "prompt_sha256": prompt_sha,
                   "retrieved_tokens": sum(len(E.tokenize(t["text"])) for t in top),
                   "repository_bytes": sum(len(t.encode()) for _, t in items)}
            rows.append(rec)
            if pool == "full":
                h = hist.get(q["question_key"])
                same_top = h is not None and h["retrieved_experience_ids"] == top_ids
                same_prompt = h is not None and h["prompt_sha256"] == prompt_sha
                diffs.append({"question_key": q["question_key"], "has_history": h is not None,
                              "top5_match": bool(same_top), "prompt_match": bool(same_prompt)})
        if pool == "full":
            diag["shared_full"] = {
                "pool_hash": pool_hash, "n_questions": len(questions),
                "n_with_history": sum(1 for d in diffs if d["has_history"]),
                "n_top5_match": sum(1 for d in diffs if d["top5_match"]),
                "n_prompt_match": sum(1 for d in diffs if d["prompt_match"]),
                "details": diffs}
        print(f"[retrieval] {pool:<18} entries={len(items):>5} pool_hash={pool_hash[:12]} "
              f"mean_retrieved_tokens={sum(r['retrieved_tokens'] for r in rows[-55:])/55:.0f}")

    os.makedirs(f"{HERE}/retrieval", exist_ok=True)
    with open(f"{HERE}/retrieval/retrieval_diagnostics.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)

    sf = diag["shared_full"]
    reuse = (sf["n_with_history"] == 55 and sf["n_top5_match"] == 55 and sf["n_prompt_match"] == 55
             and all(h["model_id"] == "meta-llama/llama-3.1-8b-instruct"
                     and h["temperature"] == 0.7 and h["max_tokens"] == 320 for h in hist.values())
             and len({h["repository_sha256"] for h in hist.values()}) == 1)
    diag["decision"] = {"reuse_shared_full": bool(reuse),
                        "new_calls_needed": 550 + 550 * (3 + (0 if reuse else 1)),   # local + matched x3 + full
                        "reason": ("all 55 questions reproduce the historical Top-5 and prompt hash, "
                                   "same model/decoding/repository" if reuse else
                                   "reproduction failed; Shared-full must be re-evaluated")}
    json.dump(diag, open(f"{HERE}/manifests/validate_reuse.json", "w"), indent=1)
    print(f"\n[reuse] history={sf['n_with_history']}/55 top5_match={sf['n_top5_match']}/55 "
          f"prompt_match={sf['n_prompt_match']}/55 -> reuse={reuse}, new calls={diag['decision']['new_calls_needed']}")


if __name__ == "__main__":
    main()
