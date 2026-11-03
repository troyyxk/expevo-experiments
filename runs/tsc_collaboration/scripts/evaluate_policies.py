#!/usr/bin/env python3
"""Phase 4: answer the 55 held-out questions under each candidate pool.

Local-only (4 client pools) + Shared-matched (3 pool seeds) are evaluated now; Shared-full reuses the
550 historical predictions once validate_reuse.py has certified them. Resume-safe: the cache key
contains model, config, pool hash, policy, seed, requesting client, question and sample index.
"""
import argparse
import collections
import hashlib
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from rank_bm25 import BM25Okapi

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(os.path.dirname(HERE))
P7 = os.path.join(ROOT, "p7", "expevo_lifecycle", "runs", "p7_full100")
P10 = os.path.join(ROOT, "p7", "expevo_lifecycle", "runs", "p10_backend_refinement")
sys.path.insert(0, os.path.join(P10, "scripts"))
import evaluate_heldout as E

SUBJECT = "high_school_geography"
MATCHED_SEEDS = [20261103, 20261104, 20261105]


def load_env(env_file=None):
    """API configuration: EXPEVO_ENV (or --env-file), else <release>/p7/expevo_lifecycle/.env."""
    env = {}
    path = env_file or os.environ.get("EXPEVO_ENV") or os.path.join(
        ROOT, "p7", "expevo_lifecycle", ".env")
    if os.path.exists(path):
        for line in open(path):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    for k in ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL"):
        if os.environ.get(k):
            env[k] = os.environ[k]
    if not env.get("LLM_API_KEY"):
        sys.exit(f"no API key: pass --env-file or set EXPEVO_ENV (looked in {path})")
    return env


def read_jsonl(p):
    with open(p, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def load_pool(name):
    if name == "shared_full":
        path = f"{HERE}/manifests/shared_full.jsonl"
    elif name.startswith("shared_matched"):
        path = f"{HERE}/manifests/{name}.jsonl"
    else:
        path = f"{HERE}/manifests/{name}.jsonl"
    sel = sorted(r["experience_id"] for r in read_jsonl(path))
    texts = {r["experience_id"]: r["text"] for r in read_jsonl(f"{P7}/full_repositories/{SUBJECT}.jsonl")}
    return sel, [texts[i] for i in sel]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", type=int, default=10)
    ap.add_argument("--temperature", type=float, default=0.7)
    ap.add_argument("--max-tokens", type=int, default=320)
    ap.add_argument("--concurrency", type=int, default=14)
    ap.add_argument("--limit", type=int, default=0, help="debug: cap number of tasks")
    ap.add_argument("--env-file", default=None)
    a = ap.parse_args()

    env = load_env(a.env_file)
    assign = json.load(open(f"{HERE}/config/request_assignment.json"))
    questions = assign["questions"]
    out_path = os.path.join(HERE, "predictions", "predictions.jsonl")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    err_path = os.path.join(HERE, "predictions", "errors.jsonl")

    done = set()
    if os.path.exists(out_path):
        for r in read_jsonl(out_path):
            done.add((r["policy"], r["pool_seed"], r["question_key"], r["sample_idx"]))
        print(f"[eval] resume: {len(done)} samples already present")

    # pools ---------------------------------------------------------------
    pools = {}
    for c in range(4):
        pools[(f"local_client_{c}", "")] = (f"local_only", f"local_client_{c}", load_pool(f"local_client_{c}"))
    for s in MATCHED_SEEDS:
        pools[(f"shared_matched_seed_{s}", str(s))] = (
            "shared_matched", f"shared_matched_seed_{s}", load_pool(f"shared_matched_seed_{s}"))
    pools[("shared_full", "")] = ("shared_full", "shared_full", load_pool("shared_full"))

    indexes, hashes = {}, {}
    for key, (policy, pname, (ids, texts)) in pools.items():
        indexes[key] = (BM25Okapi([E.tokenize(t) for t in texts], k1=1.5, b=0.75), ids, texts)
        hashes[key] = hashlib.sha256("\n".join(ids).encode()).hexdigest()

    reuse = json.load(open(f"{HERE}/manifests/validate_reuse.json"))["decision"]["reuse_shared_full"]
    tasks = []
    for key, (policy, pname, _) in pools.items():
        if policy == "shared_full" and reuse:
            continue
        bm25, ids, texts = indexes[key]
        for q in questions:
            if policy == "local_only" and key[0] != f"local_client_{q['requesting_client_id']}":
                continue
            query = f"{q['question']} {' '.join(q['choices'])}"
            scores = bm25.get_scores(E.tokenize(query))
            order = sorted(range(len(ids)), key=lambda i: (-scores[i], ids[i]))[:5]
            top = [{"id": ids[i], "text": texts[i], "score": float(scores[i])} for i in order]
            user = E.build_prompt(q, top)
            prompt_sha = hashlib.sha256((E.SYSTEM + "\n" + user).encode()).hexdigest()
            for r_idx in range(a.samples):
                if (policy, key[1], q["question_key"], r_idx) in done:
                    continue
                tasks.append({"policy": policy, "pool": pname, "pool_seed": key[1],
                              "question_key": q["question_key"], "question_set": q["question_set"],
                              "qid": q["qid"], "gold": q["gold_answer"],
                              "client": q["requesting_client_id"], "sample_idx": r_idx,
                              "prompt": user, "prompt_sha256": prompt_sha,
                              "top5_ids": [t["id"] for t in top],
                              "pool_hash": hashes[key]})
    if a.limit:
        tasks = tasks[:a.limit]
    print(f"[eval] tasks: {len(tasks)} (reuse_shared_full={reuse})")

    lock = threading.Lock()
    counters = collections.Counter()

    def work(t):
        resp, err = E.call_api(env, [{"role": "system", "content": E.SYSTEM},
                                     {"role": "user", "content": t["prompt"]}],
                               a.temperature, a.max_tokens)
        if resp is None:
            with lock:
                counters["err"] += 1
                with open(err_path, "a") as f:
                    f.write(json.dumps({k: t[k] for k in ("policy", "pool_seed", "question_key", "sample_idx")}
                                       | {"error": err}) + "\n")
            return
        text = resp["choices"][0]["message"]["content"]
        pred, how = E.parse_answer(text)
        u = resp.get("usage") or {}
        rec = {"policy": t["policy"], "pool": t["pool"], "pool_seed": t["pool_seed"],
               "requesting_client_id": t["client"], "question_key": t["question_key"],
               "question_set": t["question_set"], "qid": t["qid"], "sample_idx": t["sample_idx"],
               "predicted_option": pred, "gold_option": t["gold"],
               "correct": (pred == t["gold"]) if pred else None,
               "top5_ids": t["top5_ids"], "prompt_sha256": t["prompt_sha256"],
               "pool_hash": t["pool_hash"], "model_id": resp.get("model") or env["LLM_MODEL"],
               "temperature": a.temperature, "max_tokens": a.max_tokens, "parse_status": how,
               "input_tokens": u.get("prompt_tokens"), "output_tokens": u.get("completion_tokens"),
               "status": "ok" if pred else "unparsed", "reused": False,
               "raw_text": text[:400], "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")}
        with lock:
            counters["ok"] += 1
            counters["in"] += u.get("prompt_tokens") or 0
            counters["out"] += u.get("completion_tokens") or 0
            with open(out_path, "a") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            if counters["ok"] % 200 == 0:
                print(f"[eval] {counters['ok']} done, {counters['err']} errors", flush=True)

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=a.concurrency) as ex:
        list(ex.map(work, tasks))
    dt = time.time() - t0
    cost = counters["in"] / 1e6 * 0.05 + counters["out"] / 1e6 * 0.08
    print(f"[eval] finished in {dt/60:.1f} min: ok={counters['ok']} err={counters['err']} "
          f"tokens {counters['in']}/{counters['out']} est ${cost:.4f}")

    # shared-full reuse ----------------------------------------------------
    if reuse:
        hist = []
        for f in ("eval/predictions.jsonl", "eval/predictions_extended.jsonl"):
            for r in read_jsonl(os.path.join(P10, f)):
                if r["subject"] == SUBJECT and r["setting"] == "Full":
                    hist.append(r)
        by_q = collections.defaultdict(list)
        for r in hist:
            by_q[f"{r.get('question_set','original')}::{r['question_id']}"].append(r)
        with open(out_path, "a") as f:
            for q in questions:
                for r in sorted(by_q[q["question_key"]], key=lambda x: x["sample_idx"]):
                    f.write(json.dumps({"policy": "shared_full", "pool": "shared_full", "pool_seed": "",
                                        "requesting_client_id": q["requesting_client_id"],
                                        "question_key": q["question_key"], "question_set": q["question_set"],
                                        "qid": q["qid"], "sample_idx": r["sample_idx"],
                                        "predicted_option": r["predicted_option"], "gold_option": r["gold_option"],
                                        "correct": r["correct"], "top5_ids": r["retrieved_experience_ids"],
                                        "prompt_sha256": r["prompt_sha256"], "pool_hash": hashes[("shared_full", "")],
                                        "model_id": r["model_id"], "temperature": r["temperature"],
                                        "max_tokens": r["max_tokens"], "parse_status": r["parse_status"],
                                        "input_tokens": r["input_tokens"], "output_tokens": r["output_tokens"],
                                        "status": r["status"], "reused": True, "raw_text": r["raw_text"],
                                        "timestamp": r["timestamp"]}) + "\n")
        print(f"[eval] appended {len(hist)} reused shared-full records")


if __name__ == "__main__":
    main()
