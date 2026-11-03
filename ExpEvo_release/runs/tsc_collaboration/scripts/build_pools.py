#!/usr/bin/env python3
"""Phase 1-2: build the three candidate-pool families and the request assignment.

Local-only  : each client's own 1,500 experiences (1 source client).
Shared-matched: 1,500 entries balanced 375/375/375/375, 25 per construction question, per pool seed.
Shared-full : all 6,000 experiences (4 source clients).

No LLM calls. Everything is written to manifests/ with hashes, and every assertion in the guide is
checked before anything downstream runs.
"""
import argparse
import hashlib
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(os.path.dirname(HERE))          # ExpEvo_release/
P7 = os.path.join(ROOT, "p7", "expevo_lifecycle", "runs", "p7_full100")
SUBJECT = "high_school_geography"
POOL_SEEDS = [20261103, 20261104, 20261105]
ASSIGN_SEED = 20261106
PER_CLIENT_PER_Q = 6
POOL_SIZE = 1500


def read_jsonl(p):
    with open(p, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def sha(ids):
    h = hashlib.sha256()
    for i in sorted(ids):
        h.update(i.encode())
    return h.hexdigest()


def load_experiences():
    eps = {e["episode_id"]: e for e in read_jsonl(f"{P7}/episodes/{SUBJECT}.jsonl")}
    rows = []
    for x in read_jsonl(f"{P7}/experiences/{SUBJECT}.jsonl"):
        e = eps[x["source_episode_id"]]
        rows.append({"experience_id": x["experience_id"], "text": x["text"],
                     "client_id": e["client_id"], "source_question_id": e["source_question_id"],
                     "source_episode_id": x["source_episode_id"],
                     "bytes": x["distilled_payload_bytes"]})
    rows.sort(key=lambda r: r["experience_id"])          # stable order, never filesystem order
    return rows


def build_matched(rows, seed):
    by_cq = {}
    for r in rows:
        by_cq.setdefault((r["client_id"], r["source_question_id"]), []).append(r["experience_id"])
    questions = sorted({r["source_question_id"] for r in rows})
    rng = np.random.default_rng(seed)
    picked = []
    for q in questions:
        for c in range(4):
            ids = sorted(by_cq[(c, q)])
            take = sorted(rng.choice(len(ids), size=PER_CLIENT_PER_Q, replace=False))
            picked.extend(ids[i] for i in take)
    # the 60 extra entries: each client gets exactly 15 questions
    order = list(rng.permutation(questions))
    for i, q in enumerate(order):
        c = i % 4
        used = {x for x in picked if x in set(by_cq[(c, q)])}
        remaining = [x for x in sorted(by_cq[(c, q)]) if x not in used]
        picked.append(remaining[int(rng.integers(len(remaining)))])
    return sorted(picked)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "manifests"))
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    rows = load_experiences()
    ids = [r["experience_id"] for r in rows]
    assert len(rows) == 6000 and len(set(ids)) == 6000
    by_id = {r["experience_id"]: r for r in rows}

    # ---- local pools -----------------------------------------------------
    for c in range(4):
        sel = [r["experience_id"] for r in rows if r["client_id"] == c]
        assert len(sel) == 1500, (c, len(sel))
        per_q = {}
        for i in sel:
            per_q[by_id[i]["source_question_id"]] = per_q.get(by_id[i]["source_question_id"], 0) + 1
        assert set(per_q.values()) == {25} and len(per_q) == 60, (c, set(per_q.values()))
        with open(f"{a.out}/local_client_{c}.jsonl", "w") as f:
            for i in sel:
                r = by_id[i]
                f.write(json.dumps({"experience_id": i, "client_id": c,
                                    "source_question_id": r["source_question_id"],
                                    "bytes": r["bytes"], "sha256": sha([i])}) + "\n")
        print(f"[local] client {c}: {len(sel)} entries, 60 questions x 25")

    # ---- matched pools ---------------------------------------------------
    for seed in POOL_SEEDS:
        sel = build_matched(rows, seed)
        assert len(sel) == POOL_SIZE and len(set(sel)) == POOL_SIZE, (seed, len(sel))
        from collections import Counter
        cc = Counter(by_id[i]["client_id"] for i in sel)
        qq = Counter(by_id[i]["source_question_id"] for i in sel)
        assert dict(sorted(cc.items())) == {0: 375, 1: 375, 2: 375, 3: 375}, (seed, dict(cc))
        assert len(qq) == 60 and set(qq.values()) == {25}, (seed, set(qq.values()))
        path = f"{a.out}/shared_matched_seed_{seed}.jsonl"
        with open(path, "w") as f:
            for i in sel:
                r = by_id[i]
                f.write(json.dumps({"experience_id": i, "client_id": r["client_id"],
                                    "source_question_id": r["source_question_id"],
                                    "bytes": r["bytes"]}) + "\n")
        print(f"[matched] seed {seed}: {len(sel)} entries, clients {dict(sorted(cc.items()))}, "
              f"60 questions x 25, hash {sha(sel)[:16]}")

    # ---- full pool -------------------------------------------------------
    with open(f"{a.out}/shared_full.jsonl", "w") as f:
        for r in rows:
            f.write(json.dumps({"experience_id": r["experience_id"], "client_id": r["client_id"],
                                "source_question_id": r["source_question_id"],
                                "bytes": r["bytes"]}) + "\n")

    # ---- request assignment ---------------------------------------------
    held = read_jsonl(f"{P7}/heldout/{SUBJECT}.jsonl")
    ext = [q for q in read_jsonl(os.path.join(ROOT, "p7", "expevo_lifecycle", "runs",
                                             "p10_backend_refinement", "eval", "heldout_extended.jsonl"))
           if q["subject"] == SUBJECT]
    questions = [{"question_key": f"original::{q['qid']}", "question_set": "original", "subject": SUBJECT,
                  "qid": q["qid"],
                  "question": q["question"], "choices": q["choices"], "gold_answer": q["gold_answer"]}
                 for q in held]
    questions += [{"question_key": f"extended::{q['qid']}", "question_set": "extended", "subject": SUBJECT,
                   "qid": q["qid"],
                   "question": q["question"], "choices": q["choices"], "gold_answer": q["gold_answer"]}
                  for q in ext]
    assert len(questions) == 55, len(questions)
    rng = np.random.default_rng(ASSIGN_SEED)
    order = list(rng.permutation(len(questions)))
    for rank, idx in enumerate(order):
        questions[idx]["requesting_client_id"] = rank % 4
    counts = {c: sum(1 for q in questions if q["requesting_client_id"] == c) for c in range(4)}
    assert sorted(counts.values()) == [13, 14, 14, 14], counts
    json.dump({"assign_seed": ASSIGN_SEED, "subject": SUBJECT, "n_questions": len(questions),
               "client_counts": counts, "questions": questions},
              open(os.path.join(HERE, "config", "request_assignment.json"), "w"), indent=1)
    print(f"[assign] 55 questions -> clients {counts}")

    json.dump({"subject": SUBJECT, "pool_seeds": POOL_SEEDS, "assign_seed": ASSIGN_SEED,
               "n_experiences": len(rows), "client_counts": {"0": 1500, "1": 1500, "2": 1500, "3": 1500},
               "hashes": {"full": sha(ids),
                          **{f"matched_{s}": sha(build_matched(rows, s)) for s in POOL_SEEDS}},
               "per_construction_question": {"local": 25, "matched": 25, "full": 100}},
              open(os.path.join(a.out, "pool_validation.json"), "w"), indent=1)
    print("[ok] manifests written")


if __name__ == "__main__":
    main()
