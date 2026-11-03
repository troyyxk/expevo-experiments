#!/usr/bin/env python3
"""Coverage test: ask the SAME 60 construction questions, to a NON-OWNING client.

Design
  - the 60 construction questions Q000-Q059 are split 15 per client (partition seed 20261108);
  - each question is asked by the client one step to the right of its owner, so the requesting
    client's own 375-experience pool contains NO experience about that question;
  - three pools: Local-only (375, 15/60 coverage), Shared-matched (375, 60/60), Shared-full (1,500, 60/60);
  - answer contract: `#### <option text>`, the contract used by the original epoch experiment.

If coverage is what matters, Local-only must be clearly worse than both shared pools here.
"""
import argparse, collections, json, os, re, sys, threading, time
from concurrent.futures import ThreadPoolExecutor

from rank_bm25 import BM25Okapi

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(os.path.dirname(HERE))
P7 = os.path.join(ROOT, "p7", "expevo_lifecycle", "runs", "p7_full100")
P10 = os.path.join(ROOT, "p7", "expevo_lifecycle", "runs", "p10_backend_refinement")
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", type=int, default=10)
    ap.add_argument("--concurrency", type=int, default=14)
    a = ap.parse_args()
    env = load_env()

    part = json.load(open(os.path.join(HERE, "config", "question_partition.json")))["questions_per_client"]
    owner_of = {q: int(c) for c, qs in part.items() for q in qs}
    assert len(owner_of) == 60

    eps = {e["episode_id"]: e for e in read_jsonl(f"{P7}/episodes/{SUBJECT}.jsonl")}
    by_q = {}
    for e in eps.values():
        by_q.setdefault(e["source_question_id"], e)

    texts = {r["experience_id"]: r["text"] for r in read_jsonl(f"{P7}/full_repositories/{SUBJECT}.jsonl")}
    pools = {}
    for name in ["shared_full_hetero"] + [f"local_client_{c}" for c in range(4)] + \
                [f"shared_matched_hetero_{s}" for s in MATCHED_SEEDS]:
        ids = sorted(r["experience_id"] for r in read_jsonl(os.path.join(HERE, "manifests", f"{name}.jsonl")))
        pools[name] = (ids, [texts[i] for i in ids], BM25Okapi([E.tokenize(texts[i]) for i in ids], k1=1.5, b=0.75))

    out = os.path.join(HERE, "predictions", "covered_questions.jsonl")
    done = {(r["policy"], r["pool_seed"], r["question_key"], r["sample_idx"]) for r in read_jsonl(out)} \
        if os.path.exists(out) else set()

    tasks = []
    for q in sorted(owner_of):
        e = by_q[q]
        asker = (owner_of[q] + 1) % 4          # NON-OWNER: its own pool has no experience about q
        options = e["choices"]
        gold = e["gold_answer"]
        sysmsg, user = epoch_prompt(e["question"], options, "")
        for k in range(a.samples):
            if ("plain", "", q, k) in done:
                continue
            tasks.append({"policy": "plain", "pool": "", "pool_seed": "", "question_key": q,
                          "gold": gold, "options": options, "owner": owner_of[q], "asker": asker,
                          "sample_idx": k, "system": sysmsg, "user": user, "top5_ids": []})
        for policy, pname in ([("local_only", f"local_client_{asker}")] +
                              [("shared_matched", f"shared_matched_hetero_{s}") for s in MATCHED_SEEDS] +
                              [("shared_full_hetero", "shared_full_hetero")]):
            ids, txts, bm25 = pools[pname]
            scores = bm25.get_scores(E.tokenize(f"{e['question']} {' '.join(options)}"))
            order = sorted(range(len(ids)), key=lambda i: (-scores[i], ids[i]))[:5]
            ctx = "\n".join(txts[i] for i in order)
            sysmsg, user = epoch_prompt(e["question"], options, ctx)
            seed = pname.split("_")[-1] if policy == "shared_matched" else ""
            for k in range(a.samples):
                if (policy, seed, q, k) in done:
                    continue
                tasks.append({"policy": policy, "pool": pname, "pool_seed": seed, "question_key": q,
                              "gold": gold, "options": options, "owner": owner_of[q], "asker": asker,
                              "sample_idx": k, "system": sysmsg, "user": user,
                              "top5_ids": [ids[i] for i in order]})
    print(f"[covered] {len(tasks)} samples")

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
        rec = {k: t[k] for k in ("policy", "pool", "pool_seed", "question_key", "gold", "owner",
                                 "asker", "sample_idx", "top5_ids")}
        rec.update({"predicted_option": pred, "correct": (pred == t["gold"]) if pred else None,
                    "model_id": resp.get("model"), "input_tokens": u.get("prompt_tokens"),
                    "output_tokens": u.get("completion_tokens"), "raw_text": text[-160:]})
        with lock:
            c["ok"] += 1; c["in"] += u.get("prompt_tokens") or 0; c["out"] += u.get("completion_tokens") or 0
            with open(out, "a") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            if c["ok"] % 400 == 0:
                print(f"  {c['ok']} done", flush=True)

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=a.concurrency) as ex:
        list(ex.map(work, tasks))
    print(f"[covered] done in {(time.time()-t0)/60:.1f} min: ok={c['ok']} err={c['err']} "
          f"est ${c['in']/1e6*0.05 + c['out']/1e6*0.08:.4f}")


if __name__ == "__main__":
    main()
