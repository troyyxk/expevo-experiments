#!/usr/bin/env python3
"""Phase C: held-out MMLU accuracy for the five repository settings.

For every held-out question (never a construction question) and every setting of that subject:
retrieve Top-K experiences with BM25 from that setting's repository, answer with the fixed P7-style
prompt, and record every sampled response. Cache key includes the repository hash and the retrieved
context, so one setting can never reuse another setting's answer.
"""
import argparse
import hashlib
import json
import os
import random
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import requests
from rank_bm25 import BM25Okapi

OUT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P7 = "/data/xingkun/exp_scale/p7/expevo_lifecycle/runs/p7_full100"
SUBJECTS = ["international_law", "college_medicine", "college_biology", "high_school_geography"]
SETTINGS = ["Full", "BM25_100", "BM25_80", "BM25_60", "BM25_40"]
TOKEN = re.compile(r"[a-z0-9]+")
SYSTEM = """You answer academic multiple choice questions.
Choose exactly one of A, B, C, or D.
You may use the retrieved experiences below as background knowledge when they are relevant, but the
question is self-contained and you should rely on your own reasoning if they are not.
Provide a short, plain-language explanation and the final answer.
Do not assume knowledge of any external answer key.
Return only a JSON object with keys "answer" and "explanation".
Example format: {"answer":"B","explanation":"..."}"""


def tokenize(text):
    return TOKEN.findall(text.lower())


def sha(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def load_env():
    env = {}
    for line in open("/data/xingkun/exp_scale/p7/expevo_lifecycle/.env"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def read_jsonl(p):
    with open(p, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def repository(subject, setting):
    if setting == "Full":
        p = os.path.join(P7, "full_repositories", f"{subject}.jsonl")
        items = [{"id": x["experience_id"], "text": x["text"]} for x in read_jsonl(p)]
    else:
        t = setting.split("_")[1]
        p = os.path.join(OUT, "refined", subject, f"bm25_{t}.jsonl")
        items = [{"id": x["refined_id"], "text": x["text"]} for x in read_jsonl(p)]
    h = hashlib.sha256()
    for x in items:
        h.update(x["id"].encode()); h.update(x["text"].encode())
    return items, h.hexdigest()


def build_prompt(q, retrieved):
    opts = "\n".join(f"{chr(65+i)}. {c}" for i, c in enumerate(q["choices"]))
    ctx = "\n".join(f"{i+1}. {r['text']}" for i, r in enumerate(retrieved)) or "(none)"
    user = (f"Subject: {q['subject']}\nQuestion: {q['question']}\n{opts}\n\n"
            f"RETRIEVED EXPERIENCES\n{ctx}")
    return user


def call_api(env, messages, temperature, max_tokens, retries=4):
    url = env["LLM_BASE_URL"].rstrip("/") + "/chat/completions"
    headers = {"Authorization": f"Bearer {env['LLM_API_KEY']}", "Content-Type": "application/json"}
    payload = {"model": env["LLM_MODEL"], "messages": messages, "temperature": temperature,
               "max_tokens": max_tokens}
    last = None
    for attempt in range(retries):
        try:
            r = requests.post(url, headers=headers, json=payload, timeout=120)
            if r.status_code == 429 or r.status_code >= 500:
                time.sleep(1.5 * (attempt + 1)); last = f"HTTP {r.status_code}"; continue
            r.raise_for_status()
            return r.json(), None
        except Exception as e:
            last = str(e); time.sleep(1.0 * (attempt + 1))
    return None, last


def parse_answer(text):
    s = (text or "").strip()
    s = re.sub(r"^```(?:json)?|```$", "", s, flags=re.MULTILINE).strip()
    for cand in (s, (re.search(r"\{.*\}", s, flags=re.DOTALL) or [None]) and
                 (re.search(r"\{.*\}", s, flags=re.DOTALL).group(0) if re.search(r"\{.*\}", s, flags=re.DOTALL) else None)):
        if not cand:
            continue
        try:
            obj = json.loads(cand)
        except Exception:
            continue
        a = str(obj.get("answer", "")).strip().upper()[:1]
        if a in "ABCD":
            return a, "json"
    m = re.search(r'"answer"\s*:\s*"\s*([ABCD])\s*"', s)
    if m:
        return m.group(1), "regex_field"
    m = re.search(r"\b([ABCD])\b\s*$", s)
    if m:
        return m.group(1), "regex_tail"
    return None, "unparsed"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", type=int, default=10)
    ap.add_argument("--top-k", type=int, default=5)
    ap.add_argument("--temperature", type=float, default=0.7)
    ap.add_argument("--max-tokens", type=int, default=320)
    ap.add_argument("--concurrency", type=int, default=12)
    ap.add_argument("--smoke", action="store_true", help="1 sample, 1 question per subject, all settings")
    ap.add_argument("--limit-questions", type=int, default=0)
    ap.add_argument("--question-set", choices=["original", "extended"], default="original",
                    help="original = the 15 P7 held-out questions; extended = the frozen 40-question set")
    a = ap.parse_args()
    samples = 1 if a.smoke else a.samples

    eval_dir = os.path.join(OUT, "eval"); os.makedirs(eval_dir, exist_ok=True)
    suffix = "" if a.question_set == "original" else "_extended"
    pred_path = os.path.join(eval_dir, f"predictions{suffix}.jsonl")
    err_path = os.path.join(eval_dir, f"errors{suffix}.jsonl")
    ret_path = os.path.join(eval_dir, f"retrieval_logs{suffix}.jsonl")
    usage_path = os.path.join(OUT, "reports", "api_usage.csv")
    os.makedirs(os.path.dirname(usage_path), exist_ok=True)

    env = load_env()
    done = set()
    if os.path.exists(pred_path):
        for r in read_jsonl(pred_path):
            done.add((r["subject"], r["setting"], r["question_id"], r["sample_idx"]))
        print(f"[eval] resuming: {len(done)} samples already recorded")

    # build retrieval once per subject/setting, then expand tasks
    tasks, retrieval_rows = [], []
    if a.question_set == "extended":
        ext = read_jsonl(os.path.join(eval_dir, "heldout_extended.jsonl"))
        ext_by_subject = {s: [q for q in ext if q["subject"] == s] for s in SUBJECTS}
    for s in SUBJECTS:
        held = ext_by_subject[s] if a.question_set == "extended" else read_jsonl(os.path.join(P7, "heldout", f"{s}.jsonl"))
        if a.smoke:
            held = held[:1]
        elif a.limit_questions:
            held = held[:a.limit_questions]
        for setting in SETTINGS:
            items, repo_sha = repository(s, setting)
            corpus = [tokenize(x["text"]) for x in items]
            bm25 = BM25Okapi(corpus, k1=1.5, b=0.75)
            for q in held:
                query = f"{q['question']} {' '.join(q['choices'])}"
                scores = bm25.get_scores(tokenize(query))
                order = sorted(range(len(items)), key=lambda i: (-scores[i], items[i]["id"]))[:a.top_k]
                retrieved = [{"id": items[i]["id"], "text": items[i]["text"], "score": float(scores[i])}
                             for i in order]
                user = build_prompt(q, retrieved)
                retrieval_rows.append({"subject": s, "question_id": q["qid"], "setting": setting,
                                       "repository_sha256": repo_sha, "top_k": a.top_k,
                                       "retrieved_ids": [r["id"] for r in retrieved],
                                       "retrieval_scores": [round(r["score"], 6) for r in retrieved],
                                       "query_hash": sha(query)})
                for r_idx in range(samples):
                    if (s, setting, q["qid"], r_idx) in done:
                        continue
                    key = sha("|".join([env["LLM_MODEL"], repo_sha, q["qid"], ",".join(r["id"] for r in retrieved),
                                        user, str(a.temperature), str(a.max_tokens), str(r_idx)]))
                    tasks.append({"subject": s, "setting": setting, "qid": q["qid"], "sample_idx": r_idx,
                                  "repo_sha": repo_sha, "prompt": user, "cache_key": key,
                                  "retrieved_ids": [r["id"] for r in retrieved],
                                  "retrieval_scores": [round(r["score"], 6) for r in retrieved],
                                  "gold": q["gold_answer"],
                                  "question_hash": sha(q["question"])})

    if not a.smoke:
        with open(ret_path, "w") as f:
            for r in retrieval_rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"[eval] {len(tasks)} samples to run ({samples}/question, top_k={a.top_k})")

    lock = threading.Lock()
    counters = {"ok": 0, "err": 0, "in": 0, "out": 0}

    def work(t):
        resp, err = call_api(env, [{"role": "system", "content": SYSTEM},
                                   {"role": "user", "content": t["prompt"]}],
                             a.temperature, a.max_tokens)
        if resp is None:
            with lock:
                counters["err"] += 1
                with open(err_path, "a") as f:
                    f.write(json.dumps({"subject": t["subject"], "setting": t["setting"],
                                        "question_id": t["qid"], "sample_idx": t["sample_idx"],
                                        "error": err}, ensure_ascii=False) + "\n")
            return
        text = resp["choices"][0]["message"]["content"]
        pred, how = parse_answer(text)
        u = resp.get("usage") or {}
        rec = {"run_id": "p10_backend_refinement", "question_set": a.question_set,
               "subject": t["subject"], "question_id": t["qid"],
               "setting": t["setting"], "sample_idx": t["sample_idx"], "predicted_option": pred,
               "gold_option": t["gold"], "correct": (pred == t["gold"]) if pred else None,
               "retrieved_experience_ids": t["retrieved_ids"], "retrieval_scores": t["retrieval_scores"],
               "model_id": resp.get("model") or env["LLM_MODEL"], "temperature": a.temperature,
               "max_tokens": a.max_tokens, "prompt_sha256": sha(SYSTEM + "\n" + t["prompt"]),
               "repository_sha256": t["repo_sha"], "parse_status": how,
               "input_tokens": u.get("prompt_tokens"), "output_tokens": u.get("completion_tokens"),
               "status": "ok" if pred else "unparsed", "raw_text": text[:400],
               "cache_key": t["cache_key"], "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")}
        with lock:
            counters["ok"] += 1
            counters["in"] += u.get("prompt_tokens") or 0
            counters["out"] += u.get("completion_tokens") or 0
            with open(pred_path, "a") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            if counters["ok"] % 100 == 0:
                print(f"[eval] {counters['ok']} done, {counters['err']} errors", flush=True)

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=a.concurrency) as ex:
        list(ex.map(work, tasks))
    dt = time.time() - t0

    total_calls = counters["ok"] + counters["err"]
    cost = counters["in"] / 1e6 * 0.05 + counters["out"] / 1e6 * 0.08
    with open(usage_path, "a") as f:
        if not os.path.exists(usage_path) or os.path.getsize(usage_path) == 0:
            f.write("stage,model,requests_ok,requests_err,input_tokens,output_tokens,seconds,est_cost_usd\n")
        f.write(f"heldout_eval,{env['LLM_MODEL']},{counters['ok']},{counters['err']},"
                f"{counters['in']},{counters['out']},{dt:.1f},{cost:.4f}\n")
    print(f"[eval] done in {dt/60:.1f} min: ok={counters['ok']} err={counters['err']} "
          f"tokens_in={counters['in']} tokens_out={counters['out']} est_cost=${cost:.4f}")


if __name__ == "__main__":
    main()
