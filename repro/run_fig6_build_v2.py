"""Fig.6 database build, corrected (v2).

Same protocol as run_fig6_build.py but:
  * experiences are distilled from STRICT exact-match correctness (repo's
    `teacher_model.exam_result`), not the lenient option-snap flag;
  * questions are processed in chunks so that a question can see the
    experiences written earlier in the same iteration (repo's sequential loop).
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
ITERS = int(os.environ.get("ES_ITERS", "30"))
ROUNDS = int(os.environ.get("ES_ROUNDS", "3"))
CONC = int(os.environ.get("ES_CONC", "32"))
CHUNK = int(os.environ.get("ES_CHUNK", "10"))
TAG = os.environ.get("ES_TAG", "fig6_build_v2")
OUT_JSON = os.path.join(BASE, "out", f"{TAG}.json")
OUT_DB = os.path.join(BASE, "out", "fig6_v2_db_full.json")

engine.CONC = CONC


def main():
    t0 = time.time()
    questions = engine.load_mmlu("high_school_biology")[:NQ]
    client = engine.ORClient(tag=TAG)
    db = runner.open_db(client, port=4002)
    print(f"[{TAG}] q={len(questions)} iters={ITERS} rounds={ROUNDS} "
          f"chunk={CHUNK} conc={CONC} strict-distill", flush=True)

    stats = []
    for it in range(ITERS):
        it_t = time.time()
        n_correct = n_total = n_all_wrong = 0
        for s in range(0, len(questions), CHUNK):
            sub = questions[s : s + CHUNK]
            ctxs = runner.retrieve_batch(db, sub)
            per_q = runner.answer_batch(client, sub, ctxs, ROUNDS, tag=f"it{it + 1}/ans")
            exps = runner.distill_batch(client, sub, per_q, tag=f"it{it + 1}/distill",
                                        strict=True)
            for e in exps:
                if e:
                    db.put(e)
            for p in per_q:
                n_correct += sum(1 for r in p if r["strict"])
                n_total += len(p)
                if not any(r["strict"] for r in p):
                    n_all_wrong += 1
        acc = 100 * n_correct / n_total
        stats.append({"iter": it + 1, "acc_strict": acc, "db": len(db.db),
                      "all_wrong_q": n_all_wrong, "secs": round(time.time() - it_t, 1)})
        print(f"[{TAG}] iter {it + 1}/{ITERS} strict={acc:.1f}% db={len(db.db)} "
              f"all-wrong={n_all_wrong} ({stats[-1]['secs']}s)", flush=True)
        if (it + 1) % 5 == 0:
            runner.save_db(db, OUT_DB)
        with open(OUT_JSON, "w") as f:
            json.dump({"tag": TAG, "model": engine.MODEL, "chunk": CHUNK,
                       "stats": stats, "elapsed": round(time.time() - t0, 1)}, f, indent=1)

    n = runner.save_db(db, OUT_DB)
    print(f"[{TAG}] final db={n} in {time.time() - t0:.0f}s -> {OUT_DB}", flush=True)


if __name__ == "__main__":
    main()
