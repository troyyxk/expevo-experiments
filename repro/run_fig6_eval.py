"""Evaluate one or more experience DBs (Fig.6): 10 answers per test question,
disjoint test questions, same protocol as run_fig5.

  python run_fig6_eval.py full=out/fig6_db_full.json bm100=out/fig6_db_bm100.json ...
"""
import json
import os
import sys
import time

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

import engine  # noqa: E402
import runner  # noqa: E402

CONC = int(os.environ.get("ES_CONC", "16"))
ROUNDS = int(os.environ.get("ES_ROUNDS", "10"))
OFFSET = int(os.environ.get("ES_TEST_OFFSET", "100"))
NTEST = int(os.environ.get("ES_NTEST", "100"))
OUT = os.path.join(BASE, "out", "fig6_eval.json")

engine.CONC = CONC


def main():
    configs = []
    for a in sys.argv[1:]:
        name, path = a.split("=", 1)
        configs.append((name, os.path.abspath(path)))
    assert configs, "pass name=db.json args"

    all_q = engine.load_mmlu("high_school_biology")
    test_qs = all_q[OFFSET:OFFSET + NTEST]
    client = engine.ORClient(tag="fig6_eval")
    print(f"[eval] model={engine.MODEL} test questions={len(test_qs)} "
          f"rounds={ROUNDS} configs={[c[0] for c in configs]}", flush=True)

    result = {"model": engine.MODEL, "n_test": len(test_qs), "rounds": ROUNDS,
              "offset": OFFSET, "configs": {}}
    for name, path in configs:
        t0 = time.time()
        db = runner.open_db(client, port=4004)
        n = runner.load_db_into(db, path)
        contexts = runner.retrieve_batch(db, test_qs)
        per_q = runner.answer_batch(client, test_qs, contexts, ROUNDS, tag=f"eval/{name}")
        accs = [100 * sum(r["correct"] for r in p) / len(p) for p in per_q]
        accs_strict = [100 * sum(r["strict"] for r in p) / len(p) for p in per_q]
        result["configs"][name] = {
            "db_size": n,
            "acc": sum(accs) / len(accs),
            "acc_strict": sum(accs_strict) / len(accs_strict),
            "per_question": accs,
            "per_question_strict": accs_strict,
            "secs": round(time.time() - t0, 1),
        }
        print(f"[eval] {name:<8} db={n:<6} acc={result['configs'][name]['acc']:.1f}% "
              f"strict={result['configs'][name]['acc_strict']:.1f}% "
              f"({result['configs'][name]['secs']}s)", flush=True)
        with open(OUT, "w") as f:
            json.dump(result, f, indent=1)

    print("saved", OUT, flush=True)


if __name__ == "__main__":
    main()
