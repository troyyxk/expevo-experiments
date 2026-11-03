"""Reproduce Fig.5 (repetitive / multi-client experience growth) on
MMLU high_school_biology.

Protocol (mirrors client/retro_tester.py used by the authors):
  * every epoch, each question gets R=10 independent answers,
  * per-question accuracy = correct / 10, epoch accuracy = mean over questions,
  * retrieval uses question + cleaned options (trace_score path),
  * one experience per (question, epoch) is distilled and pushed to the DB.

Differences vs the original run (documented):
  * model served by OpenRouter (llama-3.1-8b-instruct) instead of a local
    Meta-Llama-3-8B-Instruct HF pipeline,
  * questions are answered concurrently and all see the DB snapshot taken at
    the beginning of the epoch (the paper's "multiple clients" setting),
  * confidence is sampled on 2 of the 10 answers per question.
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
NQ = int(os.environ.get("ES_NQ", "347"))
ROUNDS = int(os.environ.get("ES_ROUNDS", "10"))
CONC = int(os.environ.get("ES_CONC", "20"))
TAG = os.environ.get("ES_TAG", "fig5")
OUT = os.path.join(BASE, "out", f"{TAG}.json")

engine.CONC = CONC
runner.CONF_ROUNDS = int(os.environ.get("ES_CONF_ROUNDS", "2"))


def main():
    t0 = time.time()
    questions = engine.load_mmlu("high_school_biology")[:NQ]
    client = engine.ORClient(tag=TAG)
    db = runner.open_db(client, port=4001)

    print(f"[{TAG}] model={engine.MODEL} questions={len(questions)} "
          f"epochs={EPOCHS} rounds={ROUNDS} conc={CONC}", flush=True)

    history = []
    for ep in range(EPOCHS):
        ep_t = time.time()
        contexts = runner.retrieve_batch(db, questions)
        per_q = runner.answer_batch(client, questions, contexts, ROUNDS, tag=f"ep{ep + 1}/ans")
        confs = runner.confidence_batch(
            client, questions, contexts, per_q, tag=f"ep{ep + 1}/conf"
        )
        metrics = runner.epoch_metrics(per_q, confs)
        metrics["epoch"] = ep + 1
        metrics["db_size"] = len(db.db)
        metrics["secs"] = round(time.time() - ep_t, 1)
        metrics["conf_valid"] = sum(1 for c in confs if c["ok"])
        history.append(metrics)
        print(f"[{TAG}] epoch {ep + 1}: acc={metrics['acc']:.1f}% "
              f"strict={metrics['acc_strict']:.1f}% "
              f"conf_right={metrics['conf_right']} conf_wrong={metrics['conf_wrong']} "
              f"db={metrics['db_size']} ({metrics['secs']}s)", flush=True)

        exps = runner.distill_batch(client, questions, per_q, tag=f"ep{ep + 1}/distill")
        for e in exps:
            if e:
                db.put(e)
        runner.save_db(db, os.path.join(BASE, "out", f"{TAG}_db_ep{ep + 1}.json"))

        payload = {
            "tag": TAG,
            "model": engine.MODEL,
            "n_questions": len(questions),
            "rounds": ROUNDS,
            "history": history,
            "sample_answers": [
                {"q": questions[i]["question"][:80], "truth": questions[i]["truth"],
                 "answers": [r["answer"] for r in per_q[i]]}
                for i in range(min(5, len(questions)))
            ],
            "elapsed": round(time.time() - t0, 1),
        }
        with open(OUT, "w") as f:
            json.dump(payload, f, ensure_ascii=False, indent=1)

    print(f"[{TAG}] done in {time.time() - t0:.0f}s -> {OUT}", flush=True)


if __name__ == "__main__":
    main()
