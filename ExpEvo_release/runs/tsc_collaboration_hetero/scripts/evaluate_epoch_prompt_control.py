#!/usr/bin/env python3
"""Why did the epoch curve rise while the current runs do not?

The epoch experiment used a different prompt contract: it forces the final line to be
`#### <option text>` and puts the retrieved experiences in a `Context:` block. This script re-asks 55
construction questions (for which the repository holds experiences distilled from the same question)
under BOTH prompt contracts, with and without context:

    p10_prompt x plain | p10_prompt x repo | epoch_prompt x plain | epoch_prompt x repo

If the gain only appears under the epoch contract, the old curve measures format compliance, not knowledge.
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
SEED = 20261115
N = 55


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


def parse_epoch(text, options):
    tail = text.split("####")[-1].strip().strip(".")
    for i, o in enumerate(options):
        if tail.lower() == str(o).lower():
            return "ABCD"[i]
    for i, o in enumerate(options):
        if str(o).lower() in tail.lower() and len(str(o)) > 3:
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


def call(env, system, user, temperature=0.7, max_tokens=320):
    import requests
    url = env["LLM_BASE_URL"].rstrip("/") + "/chat/completions"
    for attempt in range(3):
        try:
            r = requests.post(url, headers={"Authorization": f"Bearer {env['LLM_API_KEY']}",
                                            "Content-Type": "application/json"},
                              json={"model": env["LLM_MODEL"], "temperature": temperature,
                                    "max_tokens": max_tokens,
                                    "messages": [{"role": "system", "content": system},
                                                 {"role": "user", "content": user}]}, timeout=120)
            if r.status_code == 200:
                return r.json()
            time.sleep(2 * (attempt + 1))
        except Exception:
            time.sleep(2 * (attempt + 1))
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", type=int, default=10)
    ap.add_argument("--concurrency", type=int, default=14)
    a = ap.parse_args()
    env = load_env()

    exps = read_jsonl(f"{P7}/full_repositories/{SUBJECT}.jsonl")
    ids = [x["experience_id"] for x in exps]
    texts = [x["text"] for x in exps]
    bm25 = BM25Okapi([E.tokenize(t) for t in texts], k1=1.5, b=0.75)

    eps = {e["episode_id"]: e for e in read_jsonl(f"{P7}/episodes/{SUBJECT}.jsonl")}
    by_q = {}
    for e in eps.values():
        by_q.setdefault(e["source_question_id"], e)
    qids = sorted(by_q)
    rng = np.random.default_rng(SEED)
    picked = [qids[i] for i in rng.permutation(len(qids))[:N]]

    out = os.path.join(HERE, "predictions", "epoch_prompt_control.jsonl")
    done = {(r["question_key"], r["contract"], r["context"], r["sample_idx"]) for r in read_jsonl(out)} \
        if os.path.exists(out) else set()

    tasks = []
    for q in picked:
        e = by_q[q]
        options = e["choices"]
        gold_idx = "ABCD"[options.index(e["gold_answer"])] if e["gold_answer"] in options else None
        query = f"{e['question']} {' '.join(options)}"
        scores = bm25.get_scores(E.tokenize(query))
        order = sorted(range(len(ids)), key=lambda i: (-scores[i], ids[i]))[:5]
        ctx = "\n".join(texts[i] for i in order)
        for contract in ("p10", "epoch"):
            for use_ctx in (False, True):
                if contract == "p10":
                    sysmsg = E.SYSTEM
                    user = E.build_prompt({"subject": SUBJECT, "question": e["question"], "choices": options},
                                          [{"text": texts[i]} for i in order] if use_ctx else [])
                else:
                    sysmsg, user = epoch_prompt(e["question"], options, ctx if use_ctx else "")
                for k in range(a.samples):
                    key = (q, contract, "repo" if use_ctx else "plain", k)
                    if (q, contract, "repo" if use_ctx else "plain", k) in done:
                        continue
                    tasks.append({"question_key": q, "contract": contract,
                                  "context": "repo" if use_ctx else "plain", "sample_idx": k,
                                  "gold": gold_idx, "options": options,
                                  "system": sysmsg, "user": user})
    print(f"[epoch-ctl] {len(tasks)} samples")
    lock = threading.Lock(); c = collections.Counter()

    def work(t):
        resp = call(env, t["system"], t["user"])
        if resp is None:
            with lock:
                c["err"] += 1
            return
        text = resp["choices"][0]["message"]["content"]
        pred = parse_epoch(text, t["options"]) if t["contract"] == "epoch" else E.parse_answer(text)[0]
        u = resp.get("usage") or {}
        with lock:
            c["ok"] += 1; c["in"] += u.get("prompt_tokens") or 0; c["out"] += u.get("completion_tokens") or 0
            with open(out, "a") as f:
                f.write(json.dumps({**{k: t[k] for k in ("question_key", "contract", "context", "sample_idx", "gold")},
                                    "predicted_option": pred, "correct": (pred == t["gold"]) if pred else None,
                                    "model_id": resp.get("model"), "input_tokens": u.get("prompt_tokens"),
                                    "output_tokens": u.get("completion_tokens"), "raw_text": text[-160:]},
                                   ensure_ascii=False) + "\n")

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=a.concurrency) as ex:
        list(ex.map(work, tasks))
    print(f"[epoch-ctl] done in {(time.time()-t0)/60:.1f} min: ok={c['ok']} err={c['err']} "
          f"est ${c['in']/1e6*0.05 + c['out']/1e6*0.08:.4f}")


if __name__ == "__main__":
    main()
