"""Fig.5, corrected run (v2).

Fixes vs run_fig5.py:
  1. experiences are distilled from STRICT exact-match correctness, exactly like
     `teacher_model.exam_result` in the repo (v1 wrongly used the lenient
     option-snap flag, which turned almost every question into a "positive"
     experience and suppressed the "The answer is NOT ..." ones);
  2. within-epoch accumulation: questions are processed in chunks and each
     chunk retrieves from the DB *as it is at that moment*, so later questions
     see the experiences written earlier in the same epoch (the repo's
     sequential loop; chunk=1 would be an exact replay).
"""
import json
import os
import sys
import time

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

import engine  # noqa: E402
import runner  # noqa: E402

EPOCHS = int(os.environ.get("ES_EPOCHS", "10"))
NQ = int(os.environ.get("ES_NQ", "200"))
ROUNDS = int(os.environ.get("ES_ROUNDS", "10"))
CONC = int(os.environ.get("ES_CONC", "32"))
CHUNK = int(os.environ.get("ES_CHUNK", "20"))
CONF_ROUNDS = int(os.environ.get("ES_CONF_ROUNDS", "0"))
TAG = os.environ.get("ES_TAG", "fig5_v2")
OUT = os.path.join(BASE, "out", f"{TAG}.json")

engine.CONC = CONC
runner.CONF_ROUNDS = CONF_ROUNDS


def distill_strict(client, questions, per_q):
    def gen(qi):
        q = questions[qi]
        correct = [r["answer"] for r in per_q[qi] if r["strict"]]
        wrong = list(dict.fromkeys(r["answer"] for r in per_q[qi] if not r["strict"]))
        return client.generate_QA_distillation(q["question"], correct, wrong)

    return engine.pmap(gen, list(range(len(questions))), label="distill", every=20)


def main():
    t0 = time.time()
    questions = engine.load_mmlu("high_school_biology")[:NQ]
    client = engine.ORClient(tag=TAG)
    db = runner.open_db(client, port=4001)
    print(f"[{TAG}] model={engine.MODEL} q={len(questions)} epochs={EPOCHS} "
          f"rounds={ROUNDS} chunk={CHUNK} conc={CONC} strict-distill", flush=True)

    history = []
    for ep in range(EPOCHS):
        ep_t = time.time()
        per_q = [None] * len(questions)
        confs = []
        for s in range(0, len(questions), CHUNK):
            idx = list(range(s, min(s + CHUNK, len(questions))))
            sub = [questions[i] for i in idx]
            ctxs = runner.retrieve_batch(db, sub)
            res = runner.answer_batch(client, sub, ctxs, ROUNDS, tag=f"ep{ep + 1}/ans")
            for k, i in enumerate(idx):
                per_q[i] = res[k]
            if CONF_ROUNDS:
                confs.extend(runner.confidence_batch(client, sub, ctxs, res, tag="conf"))
            exps = distill_strict(client, sub, res)
            for e in exps:
                if e:
                    db.put(e)
        acc = 100 * sum(r["strict"] for p in per_q for r in p) / (len(questions) * ROUNDS)
        acc_snap = 100 * sum(r["correct"] for p in per_q for r in p) / (len(questions) * ROUNDS)
        n_neg = sum(1 for p in per_q if not any(r["strict"] for r in p))
        history.append({"epoch": ep + 1, "acc_strict": acc, "acc_snap": acc_snap,
                        "db_size": len(db.db) - len(questions), "all_wrong_q": n_neg,
                        "secs": round(time.time() - ep_t, 1)})
        print(f"[{TAG}] epoch {ep + 1}: strict={acc:.1f}% snap={acc_snap:.1f}% "
              f"all-wrong-questions={n_neg} db={len(db.db)} ({history[-1]['secs']}s)", flush=True)
        with open(OUT, "w") as f:
            json.dump({"tag": TAG, "model": engine.MODEL, "n_questions": len(questions),
                       "rounds": ROUNDS, "chunk": CHUNK, "history": history,
                       "elapsed": round(time.time() - t0, 1)}, f, indent=1)
        runner.save_db(db, os.path.join(BASE, "out", f"{TAG}_db_ep{ep + 1}.json"))

    print(f"[{TAG}] done in {time.time() - t0:.0f}s -> {OUT}", flush=True)


if __name__ == "__main__":
    main()
