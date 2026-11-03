#!/usr/bin/env python3
"""Coverage sweep at FIXED entry count (375).

The matched pool is not 'sharing more' than local in bytes or entries -- both hold 375 entries. What
differs is how many of the 60 construction questions are represented. This script varies that coverage
(30/60 and 45/60; 15/60 = local and 60/60 = matched are already measured) while keeping 375 entries, and
asks every question to a non-owning client under the `####` contract.
"""
import argparse, collections, json, os, re, sys, threading, time
from concurrent.futures import ThreadPoolExecutor

import numpy as np
from rank_bm25 import BM25Okapi

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(os.path.dirname(HERE))
P7 = os.path.join(ROOT, "p7", "expevo_lifecycle", "runs", "p7_full100")
P10 = os.path.join(ROOT, "p7", "expevo_lifecycle", "runs", "p10_backend_refinement")
sys.path.insert(0, os.path.join(P10, "scripts"))
import evaluate_heldout as E

SUBJECT = "high_school_geography"
COVERAGE = (30, 45)
POOL_SIZE = 375
SEED = 20261121


def epoch_prompt(question, options, context):
    header = ("You are a helpful AI assistant. The final answer should be as short and percise as possible. "
              "Choose the answer from the options.")
    if context:
        header += " Use the provided context to answer."
    header += (" Answer the final answer in the end after #### End your reply with exactly one line of "
               "the form: #### <the chosen option text>. Choose the single best option and copy its text "
               "verbatim as the final line; never list or quote the other options.")
    user = f"Options: '{str(options)}'\n\n"
    if context:
        user += f"Context: '[{context}]'\n\n"
    user += f"Request: {question}"
    return header, user


def norm(s):
    return re.sub(r"[^a-z0-9 ]", "", s.lower()).strip()


def parse_epoch(text, options):
    t = norm(text.split("####")[-1])
    for i, o in enumerate(options):
        if t == norm(o):
            return "ABCD"[i]
    for i, o in enumerate(options):
        if len(norm(o)) > 4 and norm(o) in t:
            return "ABCD"[i]
    return None


def load_env(f=None):
    env, path = {}, f or os.environ.get("EXPEVO_ENV") or os.path.join(ROOT, "p7/expevo_lifecycle/.env")
    for line in open(path):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    for k in ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL"):
        if os.environ.get(k):
            env[k] = os.environ[k]
    return env


def read_jsonl(p):
    with open(p, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def build_pool(questions, n_cover, rng):
    """375 entries spread evenly over n_cover of the 60 questions."""
    byq = collections.defaultdict(list)
    for q in questions:
        byq[q["source_question_id"]].append(q["experience_id"])
    covered = sorted(rng.permutation(sorted(byq))[:n_cover].tolist())
    per = POOL_SIZE // n_cover
    ids = []
    for q in covered:
        pool = sorted(byq[q])
        take = sorted(rng.choice(len(pool), size=min(per, len(pool)), replace=False))
        ids.extend(pool[i] for i in take)
    # distribute the remainder (375 - per*n_cover) over covered questions
    rest = POOL_SIZE - len(ids)
    for i, q in enumerate(covered[:rest]):
        extra = [x for x in sorted(byq[q]) if x not in set(ids)]
        ids.append(extra[int(rng.integers(len(extra)))])
    assert len(ids) == POOL_SIZE and len(set(ids)) == POOL_SIZE, (n_cover, len(ids))
    return ids, covered


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", type=int, default=10)
    ap.add_argument("--concurrency", type=int, default=14)
    a = ap.parse_args()
    env = load_env()

    part = json.load(open(os.path.join(HERE, "config", "question_partition.json")))["questions_per_client"]
    owner_of = {q: int(c) for c, qs in part.items() for q in qs}

    all_exp = read_jsonl(os.path.join(HERE, "manifests", "shared_full_hetero.jsonl"))
    texts = {r["experience_id"]: r["text"] for r in read_jsonl(f"{P7}/full_repositories/{SUBJECT}.jsonl")}
    eps = {e["episode_id"]: e for e in read_jsonl(f"{P7}/episodes/{SUBJECT}.jsonl")}
    by_q = {}
    for e in eps.values():
        by_q.setdefault(e["source_question_id"], e)

    out = os.path.join(HERE, "predictions", "coverage_sweep.jsonl")
    done = {(r["coverage"], r["question_key"], r["sample_idx"]) for r in read_jsonl(out)} \
        if os.path.exists(out) else set()
    rng = np.random.default_rng(SEED)

    pools = {}
    for n in COVERAGE:
        ids, covered = build_pool(all_exp, n, rng)
        pools[n] = (ids, [texts[i] for i in ids],
                    BM25Okapi([E.tokenize(texts[i]) for i in ids], k1=1.5, b=0.75),
                    set(covered))
        print(f"[sweep] coverage {n}/60: {len(ids)} entries, {len(covered)} questions, "
              f"{len(ids)/len(covered):.1f} per covered question")

    tasks = []
    for q in sorted(owner_of):
        e = by_q[q]
        asker = (owner_of[q] + 1) % 4
        for n in COVERAGE:
            ids, txts, bm25, covered = pools[n]
            scores = bm25.get_scores(E.tokenize(f"{e['question']} {' '.join(e['choices'])}"))
            order = sorted(range(len(ids)), key=lambda i: (-scores[i], ids[i]))[:5]
            ctx = "\n".join(txts[i] for i in order)
            sysmsg, user = epoch_prompt(e["question"], e["choices"], ctx)
            for k in range(a.samples):
                if (n, q, k) in done:
                    continue
                tasks.append({"coverage": n, "covered": q in covered, "question_key": q, "asker": asker,
                              "gold": e["gold_answer"], "options": e["choices"], "sample_idx": k,
                              "system": sysmsg, "user": user,
                              "top5_ids": [ids[i] for i in order]})
    print(f"[sweep] {len(tasks)} samples")
    lock = threading.Lock(); c = collections.Counter()

    def work(t):
        resp, err = E.call_api(env, [{"role": "system", "content": t["system"]},
                                     {"role": "user", "content": t["user"]}], 0.7, 320)
        if resp is None:
            with lock:
                c["err"] += 1
            return
        text = resp["choices"][0]["message"]["content"]
        pred = parse_epoch(text, t["options"])
        u = resp.get("usage") or {}
        with lock:
            c["ok"] += 1; c["in"] += u.get("prompt_tokens") or 0; c["out"] += u.get("completion_tokens") or 0
            with open(out, "a") as f:
                f.write(json.dumps({**{k: t[k] for k in ("coverage", "covered", "question_key", "asker",
                                                          "sample_idx", "top5_ids")},
                                    "predicted_option": pred, "gold_option": t["gold"],
                                    "correct": (pred == t["gold"]) if pred else None,
                                    "model_id": resp.get("model"),
                                    "input_tokens": u.get("prompt_tokens"),
                                    "output_tokens": u.get("completion_tokens")},
                                   ensure_ascii=False) + "\n")

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=a.concurrency) as ex:
        list(ex.map(work, tasks))
    print(f"[sweep] done in {(time.time()-t0)/60:.1f} min: ok={c['ok']} err={c['err']} "
          f"est ${c['in']/1e6*0.05 + c['out']/1e6*0.08:.4f}")


if __name__ == "__main__":
    main()
