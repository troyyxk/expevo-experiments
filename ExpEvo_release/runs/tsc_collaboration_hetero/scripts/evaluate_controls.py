#!/usr/bin/env python3
"""Control baselines for the sharing experiments, on the same 55 questions.

plain   : no retrieved context at all (build_prompt with an empty list -> "(none)")
placebo : Top-5 retrieved from a DIFFERENT subject's repository (International Law), i.e. context that
          is on-topic for MMLU but unrelated to High School Geography

Same model, temperature, max_tokens, 10 samples per question, same scoring as the main runs.
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
PREV = os.path.join(HERE, "..", "tsc_collaboration")
sys.path.insert(0, os.path.join(P10, "scripts"))
import evaluate_heldout as E

SUBJECT = "high_school_geography"
PLACEBO_SUBJECT = "international_law"


def load_env(env_file=None):
    env, path = {}, env_file or os.environ.get("EXPEVO_ENV") or os.path.join(
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
        sys.exit(f"no API key (looked in {path})")
    return env


def read_jsonl(p):
    with open(p, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["plain", "placebo", "both"], default="both")
    ap.add_argument("--samples", type=int, default=10)
    ap.add_argument("--temperature", type=float, default=0.7)
    ap.add_argument("--max-tokens", type=int, default=320)
    ap.add_argument("--concurrency", type=int, default=14)
    ap.add_argument("--env-file", default=None)
    a = ap.parse_args()

    env = load_env(a.env_file)
    questions = json.load(open(os.path.join(PREV, "config", "request_assignment.json")))["questions"]
    out_path = os.path.join(HERE, "predictions", "controls.jsonl")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    done = {(r["mode"], r["question_key"], r["sample_idx"]) for r in read_jsonl(out_path)} \
        if os.path.exists(out_path) else set()

    modes = ["plain", "placebo"] if a.mode == "both" else [a.mode]
    contexts = {m: None for m in modes}
    if "placebo" in modes:
        items = [(x["experience_id"], x["text"]) for x in
                 read_jsonl(f"{P7}/full_repositories/{PLACEBO_SUBJECT}.jsonl")]
        ids = [i for i, _ in items]
        bm25 = BM25Okapi([E.tokenize(t) for _, t in items], k1=1.5, b=0.75)
        contexts["placebo"] = (ids, [t for _, t in items], bm25)

    tasks = []
    for m in modes:
        for q in questions:
            if m == "plain":
                top = []
            else:
                ids, texts, bm25 = contexts[m]
                query = f"{q['question']} {' '.join(q['choices'])}"
                scores = bm25.get_scores(E.tokenize(query))
                order = sorted(range(len(ids)), key=lambda i: (-scores[i], ids[i]))[:5]
                top = [{"id": ids[i], "text": texts[i], "score": float(scores[i])} for i in order]
            user = E.build_prompt(q, top)
            prompt_sha = hashlib.sha256((E.SYSTEM + "\n" + user).encode()).hexdigest()
            for k in range(a.samples):
                if (m, q["question_key"], k) in done:
                    continue
                tasks.append({"mode": m, "question_key": q["question_key"], "qid": q["qid"],
                              "question_set": q["question_set"], "gold": q["gold_answer"], "sample_idx": k,
                              "prompt": user, "prompt_sha256": prompt_sha,
                              "top5_ids": [t["id"] for t in top]})
    print(f"[controls] {len(tasks)} samples to run ({', '.join(modes)})")

    lock = threading.Lock()
    counters = collections.Counter()

    def work(t):
        resp, err = E.call_api(env, [{"role": "system", "content": E.SYSTEM},
                                     {"role": "user", "content": t["prompt"]}], a.temperature, a.max_tokens)
        if resp is None:
            with lock:
                counters["err"] += 1
            return
        text = resp["choices"][0]["message"]["content"]
        pred, how = E.parse_answer(text)
        u = resp.get("usage") or {}
        rec = {"mode": t["mode"], "question_key": t["question_key"], "question_set": t["question_set"],
               "qid": t["qid"], "sample_idx": t["sample_idx"], "predicted_option": pred,
               "gold_option": t["gold"], "correct": (pred == t["gold"]) if pred else None,
               "top5_ids": t["top5_ids"], "prompt_sha256": t["prompt_sha256"],
               "model_id": resp.get("model") or env["LLM_MODEL"], "temperature": a.temperature,
               "max_tokens": a.max_tokens, "parse_status": how,
               "input_tokens": u.get("prompt_tokens"), "output_tokens": u.get("completion_tokens"),
               "status": "ok" if pred else "unparsed", "raw_text": text[:400],
               "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")}
        with lock:
            counters["ok"] += 1
            counters["in"] += u.get("prompt_tokens") or 0
            counters["out"] += u.get("completion_tokens") or 0
            with open(out_path, "a") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=a.concurrency) as ex:
        list(ex.map(work, tasks))
    dt = time.time() - t0
    cost = counters["in"] / 1e6 * 0.05 + counters["out"] / 1e6 * 0.08
    print(f"[controls] done in {dt/60:.1f} min: ok={counters['ok']} err={counters['err']} est ${cost:.4f}")


if __name__ == "__main__":
    main()
