#!/usr/bin/env python3
"""No-context baseline for every subject, on the same 55 questions used by the P10 evaluation.

Same SYSTEM prompt and build_prompt, but an empty retrieved list. Lets us compare "model prior" against
the already measured "full 6,000-entry repository" numbers per subject.
"""
import argparse, collections, hashlib, json, os, sys, threading, time
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(os.path.dirname(HERE))
P7 = os.path.join(ROOT, "p7", "expevo_lifecycle", "runs", "p7_full100")
P10 = os.path.join(ROOT, "p7", "expevo_lifecycle", "runs", "p10_backend_refinement")
sys.path.insert(0, os.path.join(P10, "scripts"))
import evaluate_heldout as E

SUBJECTS = ["high_school_geography", "college_biology", "college_medicine", "international_law"]


def load_env(env_file=None):
    env, path = {}, env_file or os.environ.get("EXPEVO_ENV") or os.path.join(ROOT, "p7/expevo_lifecycle/.env")
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
        sys.exit("no API key")
    return env


def read_jsonl(p):
    with open(p, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def questions_for(subject):
    held = read_jsonl(f"{P7}/heldout/{subject}.jsonl")
    ext = [q for q in read_jsonl(os.path.join(P10, "eval", "heldout_extended.jsonl")) if q["subject"] == subject]
    qs = [{"question_key": f"original::{q['qid']}", "subject": subject, "qid": q["qid"],
           "question": q["question"], "choices": q["choices"], "gold_answer": q["gold_answer"]} for q in held]
    qs += [{"question_key": f"extended::{q['qid']}", "subject": subject, "qid": q["qid"],
            "question": q["question"], "choices": q["choices"], "gold_answer": q["gold_answer"]} for q in ext]
    assert len(qs) == 55, (subject, len(qs))
    return qs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", type=int, default=10)
    ap.add_argument("--temperature", type=float, default=0.7)
    ap.add_argument("--max-tokens", type=int, default=320)
    ap.add_argument("--concurrency", type=int, default=14)
    ap.add_argument("--subjects", nargs="+", default=SUBJECTS)
    ap.add_argument("--env-file", default=None)
    a = ap.parse_args()
    env = load_env(a.env_file)
    out_path = os.path.join(HERE, "predictions", "plain_all_subjects.jsonl")
    done = set()
    if os.path.exists(out_path):
        for r in read_jsonl(out_path):
            done.add((r["subject"], r["question_key"], r["sample_idx"]))

    tasks = []
    for s in a.subjects:
        for q in questions_for(s):
            user = E.build_prompt(q, [])
            sha = hashlib.sha256((E.SYSTEM + "\n" + user).encode()).hexdigest()
            for k in range(a.samples):
                if (s, q["question_key"], k) in done:
                    continue
                tasks.append({"subject": s, "question_key": q["question_key"], "qid": q["qid"],
                              "gold": q["gold_answer"], "sample_idx": k, "prompt": user, "prompt_sha256": sha})
    print(f"[plain] {len(tasks)} samples across {len(a.subjects)} subjects")

    lock = threading.Lock(); c = collections.Counter()

    def work(t):
        resp, err = E.call_api(env, [{"role": "system", "content": E.SYSTEM},
                                     {"role": "user", "content": t["prompt"]}], a.temperature, a.max_tokens)
        if resp is None:
            with lock:
                c["err"] += 1
            return
        text = resp["choices"][0]["message"]["content"]
        pred, how = E.parse_answer(text)
        u = resp.get("usage") or {}
        rec = {"subject": t["subject"], "question_key": t["question_key"], "qid": t["qid"],
               "sample_idx": t["sample_idx"], "predicted_option": pred, "gold_option": t["gold"],
               "correct": (pred == t["gold"]) if pred else None, "parse_status": how,
               "model_id": resp.get("model") or env["LLM_MODEL"], "temperature": a.temperature,
               "max_tokens": a.max_tokens, "input_tokens": u.get("prompt_tokens"),
               "output_tokens": u.get("completion_tokens"), "prompt_sha256": t["prompt_sha256"],
               "status": "ok" if pred else "unparsed", "raw_text": text[:300]}
        with lock:
            c["ok"] += 1; c["in"] += u.get("prompt_tokens") or 0; c["out"] += u.get("completion_tokens") or 0
            with open(out_path, "a") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=a.concurrency) as ex:
        list(ex.map(work, tasks))
    dt = time.time() - t0
    print(f"[plain] done in {dt/60:.1f} min: ok={c['ok']} err={c['err']} est ${c['in']/1e6*0.05 + c['out']/1e6*0.08:.4f}")


if __name__ == "__main__":
    main()
