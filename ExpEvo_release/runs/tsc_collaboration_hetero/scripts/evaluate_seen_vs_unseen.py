#!/usr/bin/env python3
"""Is the epoch-experiment gain answer recall rather than transfer?

2x2 control on MMLU High School Geography, same model/prompt/decoding as every other run:

  SEEN questions   (the 60 construction questions, which have their own experiences in the repository)
  UNSEEN questions (the 55 held-out questions, which have none)
  x plain (empty retrieved list) / repository (Top-5 from the full 6,000-entry repository)

Also reports the leakage rate: share of retrieved Top-5 entries that were distilled from the very
question being asked.
"""
import argparse, collections, hashlib, json, os, sys, threading, time
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
N_SEEN = 55
SEED = 20261115


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
    while env["LLM_BASE_URL"].endswith("/"):
        env["LLM_BASE_URL"] = env["LLM_BASE_URL"][:-1]
    return env


def read_jsonl(p):
    with open(p, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", type=int, default=10)
    ap.add_argument("--concurrency", type=int, default=14)
    a = ap.parse_args()
    env = load_env()

    # corpus
    exps = read_jsonl(f"{P7}/full_repositories/{SUBJECT}.jsonl")
    ids = [x["experience_id"] for x in exps]
    texts = [x["text"] for x in exps]
    src_q = {x["experience_id"]: x["source_episode_id"].split("/")[1] for x in exps}
    bm25 = BM25Okapi([E.tokenize(t) for t in texts], k1=1.5, b=0.75)

    # seen questions: construction questions (they own experiences in the repository)
    eps = {e["episode_id"]: e for e in read_jsonl(f"{P7}/episodes/{SUBJECT}.jsonl")}
    by_q = {}
    for e in eps.values():
        by_q.setdefault(e["source_question_id"], e)
    qids = sorted(by_q)
    rng = np.random.default_rng(SEED)
    seen_ids = [qids[i] for i in rng.permutation(len(qids))[:N_SEEN]]
    seen = [{"question_key": f"seen::{q}", "subject": SUBJECT, "qid": q,
             "question": by_q[q]["question"], "choices": by_q[q]["choices"],
             "gold_answer": by_q[q]["gold_answer"], "source_question": q} for q in seen_ids]

    held = read_jsonl(f"{P7}/heldout/{SUBJECT}.jsonl")
    ext = [q for q in read_jsonl(os.path.join(P10, "eval/heldout_extended.jsonl")) if q["subject"] == SUBJECT]
    unseen = [{"question_key": f"unseen::{q['qid']}", "subject": SUBJECT, "qid": q["qid"],
               "question": q["question"], "choices": q["choices"], "gold_answer": q["gold_answer"],
               "source_question": q["qid"]} for q in (held + ext)]
    assert len(seen) == N_SEEN and len(unseen) == 55

    out = os.path.join(HERE, "predictions", "seen_vs_unseen.jsonl")
    done = {(r["question_key"], r["condition"], r["sample_idx"]) for r in read_jsonl(out)} \
        if os.path.exists(out) else set()
    tasks, leak = [], collections.defaultdict(list)
    for group, qs in (("seen", seen), ("unseen", unseen)):
        for q in qs:
            query = f"{q['question']} {' '.join(q['choices'])}"
            scores = bm25.get_scores(E.tokenize(query))
            order = sorted(range(len(ids)), key=lambda i: (-scores[i], ids[i]))[:5]
            top = [{"id": ids[i], "text": texts[i], "score": float(scores[i])} for i in order]
            leak[group].append(sum(1 for t in top if src_q[t["id"]] == q["source_question"]))
            for cond in ("plain", "repo"):
                user = E.build_prompt(q, [] if cond == "plain" else top)
                sha = hashlib.sha256((E.SYSTEM + "\n" + user).encode()).hexdigest()
                for k in range(a.samples):
                    if (q["question_key"], cond, k) in done:
                        continue
                    tasks.append({"group": group, "condition": cond, "question_key": q["question_key"],
                                  "qid": q["qid"], "gold": q["gold_answer"], "sample_idx": k,
                                  "prompt": user, "prompt_sha256": sha,
                                  "top5_ids": [t["id"] for t in top]})
    print(f"[2x2] {len(tasks)} samples; leakage rate (top-5 from the same question): "
          f"seen {np.mean(leak['seen'])/5*100:.0f}% vs unseen {np.mean(leak['unseen'])/5*100:.0f}%")

    lock = threading.Lock(); c = collections.Counter()

    def work(t):
        resp, err = E.call_api(env, [{"role": "system", "content": E.SYSTEM},
                                     {"role": "user", "content": t["prompt"]}], 0.7, 320)
        if resp is None:
            with lock:
                c["err"] += 1
            return
        txt = resp["choices"][0]["message"]["content"]
        pred, how = E.parse_answer(txt)
        u = resp.get("usage") or {}
        rec = {**t, "predicted_option": pred, "correct": (pred == t["gold"]) if pred else None,
               "parse_status": how, "model_id": resp.get("model"), "temperature": 0.7, "max_tokens": 320,
               "input_tokens": u.get("prompt_tokens"), "output_tokens": u.get("completion_tokens")}
        with lock:
            c["ok"] += 1; c["in"] += u.get("prompt_tokens") or 0; c["out"] += u.get("completion_tokens") or 0
            with open(out, "a") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=a.concurrency) as ex:
        list(ex.map(work, tasks))
    print(f"[2x2] done in {(time.time()-t0)/60:.1f} min: ok={c['ok']} err={c['err']} "
          f"est ${c['in']/1e6*0.05 + c['out']/1e6*0.08:.4f}")


if __name__ == "__main__":
    main()
