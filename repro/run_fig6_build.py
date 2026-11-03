"""Saturate an experience DB for Fig.6 (MMLU high_school_biology).

Protocol mirrors the authors' "first100" runs:
  * 100 train questions, ITERS iterations each,
  * ROUNDS answers per (question, iteration); every iteration appends exactly
    one distilled experience, so the DB grows by one item per question/iteration.
"""
import json
import os
import sys
import time

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

import engine  # noqa: E402
import runner  # noqa: E402

NQ = int(os.environ.get("ES_NQ", "100"))
ITERS = int(os.environ.get("ES_ITERS", "50"))
ROUNDS = int(os.environ.get("ES_ROUNDS", "3"))
CONC = int(os.environ.get("ES_CONC", "16"))
TAG = os.environ.get("ES_TAG", "fig6_build")
OUT_JSON = os.path.join(BASE, "out", f"{TAG}.json")
OUT_DB = os.path.join(BASE, "out", "fig6_db_full.json")

engine.CONC = CONC


def main():
    t0 = time.time()
    questions = engine.load_mmlu("high_school_biology")[:NQ]
    client = engine.ORClient(tag=TAG)
    db = runner.open_db(client, port=4002)
    print(f"[{TAG}] model={engine.MODEL} q={len(questions)} iters={ITERS} "
          f"rounds={ROUNDS} conc={CONC}", flush=True)

    stats = []
    for it in range(ITERS):
        it_t = time.time()
        contexts = runner.retrieve_batch(db, questions, workers=8)
        per_q = runner.answer_batch(client, questions, contexts, ROUNDS,
                                    tag=f"it{it + 1}/ans")
        acc = 100 * sum(r["correct"] for p in per_q for r in p) / (len(questions) * ROUNDS)
        exps = runner.distill_batch(client, questions, per_q, tag=f"it{it + 1}/distill")
        added = 0
        for e in exps:
            if e:
                db.put(e)
                added += 1
        stats.append({"iter": it + 1, "acc": acc, "db": len(db.db), "added": added,
                      "secs": round(time.time() - it_t, 1)})
        print(f"[{TAG}] iter {it + 1}/{ITERS} acc={acc:.1f}% db={len(db.db)} "
              f"({stats[-1]['secs']}s)", flush=True)
        if (it + 1) % 10 == 0:
            runner.save_db(db, OUT_DB)
        with open(OUT_JSON, "w") as f:
            json.dump({"tag": TAG, "model": engine.MODEL, "stats": stats,
                       "elapsed": round(time.time() - t0, 1)}, f, indent=1)

    n = runner.save_db(db, OUT_DB)
    print(f"[{TAG}] final db={n} in {time.time() - t0:.0f}s -> {OUT_DB}", flush=True)


if __name__ == "__main__":
    main()
