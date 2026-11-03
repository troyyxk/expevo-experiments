#!/usr/bin/env python3
"""The heterogeneous sharing comparison re-run under the OLD epoch prompt contract.

Same pools, same 55 unseen questions, same model/decoding; the only change is the answer contract:
instead of returning a JSON letter, the model must end with `#### <chosen option text>`.

Conditions: plain (no context), Local-only, Shared-matched x3, Shared-full-hetero.
"""
import argparse, collections, json, os, re, sys, threading, time
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
MATCHED_SEEDS = [20261109, 20261110, 20261111]


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
    tail = text.split("####")[-1]
    t = norm(tail)
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", type=int, default=10)
    ap.add_argument("--concurrency", type=int, default=14)
    a = ap.parse_args()
    env = load_env()

    questions = json.load(open(os.path.join(PREV, "config", "request_assignment.json")))["questions"]
    texts = {r["experience_id"]: r["text"] for r in read_jsonl(f"{P7}/full_repositories/{SUBJECT}.jsonl")}
    pools = {}
    names = ["shared_full_hetero"] + [f"local_client_{c}" for c in range(4)] + \
            [f"shared_matched_hetero_{s}" for s in MATCHED_SEEDS]
    for name in names:
        ids = sorted(r["experience_id"] for r in read_jsonl(os.path.join(HERE, "manifests", f"{name}.jsonl")))
        pools[name] = (ids, [texts[i] for i in ids], BM25Okapi([E.tokenize(texts[i]) for i in ids], k1=1.5, b=0.75))

    out = os.path.join(HERE, "predictions", "hetero_epoch_contract.jsonl")
    done = {(r["policy"], r["pool_seed"], r["question_key"], r["sample_idx"]) for r in read_jsonl(out)} \
        if os.path.exists(out) else set()

    tasks = []
    for q in questions:
        options = q["choices"]
        # plain
        sysmsg, user = epoch_prompt(q["question"], options, "")
        for k in range(a.samples):
            if ("plain", "", q["question_key"], k) in done:
                continue
            tasks.append({"policy": "plain", "pool": "", "pool_seed": "", "question_key": q["question_key"],
                          "question_set": q["question_set"], "qid": q["qid"], "gold": q["gold_answer"],
                          "client": q["requesting_client_id"], "sample_idx": k, "system": sysmsg, "user": user,
                          "options": options, "top5_ids": []})
        for policy, pname in ([("local_only", f"local_client_{q['requesting_client_id']}")] +
                              [("shared_matched", f"shared_matched_hetero_{s}") for s in MATCHED_SEEDS] +
                              [("shared_full_hetero", "shared_full_hetero")]):
            ids, txts, bm25 = pools[pname]
            query = f"{q['question']} {' '.join(options)}"
            scores = bm25.get_scores(E.tokenize(query))
            order = sorted(range(len(ids)), key=lambda i: (-scores[i], ids[i]))[:5]
            ctx = "\n".join(txts[i] for i in order)
            sysmsg, user = epoch_prompt(q["question"], options, ctx)
            seed = pname.split("_")[-1] if policy == "shared_matched" else ""
            for k in range(a.samples):
                if (policy, seed, q["question_key"], k) in done:
                    continue
                tasks.append({"policy": policy, "pool": pname, "pool_seed": seed,
                              "question_key": q["question_key"], "question_set": q["question_set"],
                              "qid": q["qid"], "gold": q["gold_answer"], "client": q["requesting_client_id"],
                              "sample_idx": k, "system": sysmsg, "user": user, "options": options,
                              "top5_ids": [ids[i] for i in order]})
    print(f"[epoch-hetero] {len(tasks)} samples to run")

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
        rec = {k: t[k] for k in ("policy", "pool", "pool_seed", "question_key", "question_set", "qid",
                                 "client", "sample_idx", "top5_ids")}
        rec.update({"predicted_option": pred, "gold_option": t["gold"],
                    "correct": (pred == t["gold"]) if pred else None,
                    "parse_status": "####" if pred else "unparsed",
                    "model_id": resp.get("model"), "temperature": 0.7, "max_tokens": 320,
                    "input_tokens": u.get("prompt_tokens"), "output_tokens": u.get("completion_tokens"),
                    "raw_text": text[-200:]})
        with lock:
            c["ok"] += 1; c["in"] += u.get("prompt_tokens") or 0; c["out"] += u.get("completion_tokens") or 0
            with open(out, "a") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            if c["ok"] % 300 == 0:
                print(f"  {c['ok']} done", flush=True)

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=a.concurrency) as ex:
        list(ex.map(work, tasks))
    print(f"[epoch-hetero] done in {(time.time()-t0)/60:.1f} min: ok={c['ok']} err={c['err']} "
          f"est ${c['in']/1e6*0.05 + c['out']/1e6*0.08:.4f}")


if __name__ == "__main__":
    main()
