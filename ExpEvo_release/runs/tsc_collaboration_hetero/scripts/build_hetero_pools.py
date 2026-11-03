#!/usr/bin/env python3
"""Step 2: build the retrospective heterogeneous client partition and its pools.

Partition the 60 construction questions into 4 disjoint sets of 15 (seed 20261108). Client c keeps only
its own 25 experiences on the questions in Q_c -> Local_c (375). Full-hetero is their union (1,500,
60 questions x 25). Shared-matched is a 375-entry subset covering all 60 questions (6 each + 15 extra).
"""
import argparse
import hashlib
import json
import os
from collections import Counter, defaultdict

import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(os.path.dirname(HERE))
P7 = os.path.join(ROOT, "p7", "expevo_lifecycle", "runs", "p7_full100")
SUBJECT = "high_school_geography"
N_PARTITION_SEED = 20261108
MATCHED_SEEDS = [20261109, 20261110, 20261111]
PER_Q_BASE = 6
EXTRA_QUESTIONS = 15


def read_jsonl(p):
    with open(p, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def sha(ids):
    h = hashlib.sha256()
    for i in sorted(ids):
        h.update(i.encode())
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--partition-seed", type=int, default=N_PARTITION_SEED)
    ap.add_argument("--matched-seeds", type=int, nargs="+", default=MATCHED_SEEDS)
    a = ap.parse_args()

    eps = {e["episode_id"]: e for e in read_jsonl(f"{P7}/episodes/{SUBJECT}.jsonl")}
    rows = []
    for x in read_jsonl(f"{P7}/experiences/{SUBJECT}.jsonl"):
        e = eps[x["source_episode_id"]]
        rows.append({"experience_id": x["experience_id"], "text": x["text"],
                     "client_id": e["client_id"], "source_question_id": e["source_question_id"],
                     "bytes": len(x["text"].encode())})
    rows.sort(key=lambda r: r["experience_id"])
    by_id = {r["experience_id"]: r for r in rows}
    questions = sorted({r["source_question_id"] for r in rows})

    # ---- partition -------------------------------------------------------
    rng = np.random.default_rng(a.partition_seed)
    order = [questions[i] for i in rng.permutation(len(questions))]
    Q = {c: sorted(order[c * 15:(c + 1) * 15]) for c in range(4)}
    assert sum(len(v) for v in Q.values()) == 60
    assert len(set().union(*[set(v) for v in Q.values()])) == 60
    json.dump({"partition_seed": a.partition_seed, "subject": SUBJECT,
               "questions_per_client": {str(c): Q[c] for c in range(4)}},
              open(os.path.join(HERE, "config", "question_partition.json"), "w"), indent=1)

    # ---- pools -----------------------------------------------------------
    def write_pool(name, ids):
        with open(os.path.join(HERE, "manifests", f"{name}.jsonl"), "w") as f:
            for i in sorted(ids):
                r = by_id[i]
                f.write(json.dumps({"experience_id": i, "client_id": r["client_id"],
                                    "source_question_id": r["source_question_id"],
                                    "bytes": r["bytes"]}) + "\n")

    local = {}
    for c in range(4):
        ids = [r["experience_id"] for r in rows if r["client_id"] == c and r["source_question_id"] in set(Q[c])]
        assert len(ids) == 375, (c, len(ids))
        qc = Counter(by_id[i]["source_question_id"] for i in ids)
        assert len(qc) == 15 and set(qc.values()) == {25}, (c, set(qc.values()))
        local[c] = sorted(ids)
        write_pool(f"local_client_{c}", ids)
        print(f"[local] client {c}: 375 entries, 15 questions x 25 (Q{c})")

    full_ids = sorted(i for c in range(4) for i in local[c])
    assert len(full_ids) == 1500 and len(set(full_ids)) == 1500
    qc = Counter(by_id[i]["source_question_id"] for i in full_ids)
    cc = Counter(by_id[i]["client_id"] for i in full_ids)
    assert len(qc) == 60 and set(qc.values()) == {25}, (len(qc), set(qc.values()))
    assert dict(sorted(cc.items())) == {0: 375, 1: 375, 2: 375, 3: 375}
    write_pool("shared_full_hetero", full_ids)
    print(f"[full] 1500 entries, 60 questions x 25, clients {dict(sorted(cc.items()))}")

    # ---- matched pools ---------------------------------------------------
    by_q = defaultdict(list)
    for i in full_ids:
        by_q[by_id[i]["source_question_id"]].append(i)
    for seed in a.matched_seeds:
        rng2 = np.random.default_rng(seed)
        picked = []
        for q in questions:
            ids = sorted(by_q[q])
            take = sorted(rng2.choice(len(ids), size=PER_Q_BASE, replace=False))
            picked.extend(ids[i] for i in take)
        # 15 extra entries, one per distinct question, owners forced to 4/4/4/3
        owner_quota = {0: 4, 1: 4, 2: 4, 3: 3}
        order_q = []
        for c in range(4):
            pool = sorted(Q[c])
            perm = rng2.permutation(len(pool))
            order_q += [pool[i] for i in perm[:owner_quota[c]]]
        assert len(order_q) == EXTRA_QUESTIONS and len(set(order_q)) == EXTRA_QUESTIONS
        order_q = [order_q[i] for i in rng2.permutation(len(order_q))]
        for q in order_q:
            chosen = {x for x in picked if by_id[x]["source_question_id"] == q}
            remaining = [x for x in sorted(by_q[q]) if x not in chosen]
            picked.append(remaining[int(rng2.integers(len(remaining)))])
        assert len(picked) == 375 and len(set(picked)) == 375, (seed, len(picked))
        qc = Counter(by_id[i]["source_question_id"] for i in picked)
        cc = Counter(by_id[i]["client_id"] for i in picked)
        assert len(qc) == 60 and set(qc.values()) == {6, 7}, (seed, set(qc.values()))
        assert sorted(cc.values()) == [93, 94, 94, 94], (seed, dict(cc))
        assert set(picked) <= set(full_ids)
        write_pool(f"shared_matched_hetero_{seed}", picked)
        print(f"[matched] seed {seed}: 375 entries, 60 questions (6/7), clients {dict(sorted(cc.items()))}")

    json.dump({"subject": SUBJECT, "partition_seed": a.partition_seed, "matched_seeds": a.matched_seeds,
               "counts": {"local": 375, "matched": 375, "full": 1500},
               "coverage": {"local": 15, "matched": 60, "full": 60},
               "hashes": {"full": sha(full_ids),
                          **{f"local_{c}": sha(local[c]) for c in range(4)},
                          **{f"matched_{s}": sha([r["experience_id"] for r in
                                                  read_jsonl(os.path.join(HERE, "manifests",
                                                                          f"shared_matched_hetero_{s}.jsonl"))])
                             for s in a.matched_seeds}},
               "bytes": {"local": {str(c): sum(by_id[i]["bytes"] for i in local[c]) for c in range(4)},
                         "full": sum(by_id[i]["bytes"] for i in full_ids)}},
              open(os.path.join(HERE, "manifests", "pool_validation.json"), "w"), indent=1)
    print("\n[ok] pools + manifests written")


if __name__ == "__main__":
    main()
