"""Reproduce Fig.4 (generalized experience) on MMLU high_school_biology.

Protocol (mirrors client/experience_builder.py + client/tester.py):
  * split 347 questions 80/20 -> 277 train / 70 test,
  * build TWO databases from the train split:
      memory     = raw conversation string ("Question: ..., CORRECT answer: ...")
      experience = LLM-distilled one-sentence experience
    (only questions the student eventually answers within `max_round=3` are
     stored, matching save_false_experience=False in the repo),
  * evaluate the 70 test questions under plain / memory / experience,
    1 answer per question, prompt uses clean_options (as tester.py does),
  * repeat the whole test pass `PASSES` times (the paper's Fig.4 x-axis
    "Test 1..20").
"""
import json
import os
import sys
import time

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

import engine  # noqa: E402
import runner  # noqa: E402

CONC = int(os.environ.get("ES_CONC", "32"))
PASSES = int(os.environ.get("ES_PASSES", "20"))
MAX_ROUND = 3          # experience_constructor_meta["max_round"]
TRAIN_PERCENT = 0.8
SPLIT = os.environ.get("ES_SPLIT", "fwd")          # fwd | rev
SUFFIX = "" if SPLIT == "fwd" else "_rev"
OUT = os.path.join(BASE, "out", f"fig4{SUFFIX}.json")
DB_EXP = os.path.join(BASE, "out", f"fig4{SUFFIX}_db_experience.json")
DB_MEM = os.path.join(BASE, "out", f"fig4{SUFFIX}_db_memory.json")

engine.CONC = CONC


def build(client):
    qs = engine.load_mmlu("high_school_biology")
    n_train = int(len(qs) * TRAIN_PERCENT)
    if SPLIT == "rev":                      # hold out the FIRST 70 questions
        train, test = qs[-n_train:], qs[: len(qs) - n_train]
    else:
        train, test = qs[:n_train], qs[n_train:]
    if SPLIT == "rev":
        train, test = qs[-n_train:], qs[: len(qs) - n_train]
    print(f"[build] total={len(qs)} train={len(train)} test={len(test)}", flush=True)

    def one(q):
        opts_clean = [engine.clean_str(o) for o in q["options"]]
        correct, wrong = [], []
        for _ in range(MAX_ROUND):
            ctx = ""
            if correct or wrong:  # teacher.get_context()
                ctx = f"Question: '{q['question']}', "
                if correct:
                    ctx += f"CORRECT answer: '{correct[0]}', "
                if wrong:
                    ctx += f"WRONG answer: '{wrong}'. "
            prompt = engine.precise_question_prompt(q["question"], opts_clean, ctx)
            raw = client.clean_pipe(prompt, max_tokens=160)
            cand = engine.extract_answer(raw)
            if engine.is_correct(cand, opts_clean, q["truth"])[1]:
                correct.append(cand)
                break
            if cand not in wrong:
                wrong.append(cand)
        if not correct:
            return None
        full_conv = f"Question: '{q['question']}', CORRECT answer: '{correct[0]}', "
        if wrong:
            full_conv += f"WRONG answer: '{wrong}'. "
        exp = client.generate_QA_distillation(q["question"], correct, wrong)
        return full_conv, exp

    t0 = time.time()
    built = [r for r in engine.pmap(one, train, label="build") if r]
    print(f"[build] stored {len(built)}/{len(train)} "
          f"(answered within {MAX_ROUND} tries) in {time.time() - t0:.0f}s", flush=True)
    mem = [b[0] for b in built]
    exp = [b[1] for b in built if b[1]]
    return train, test, mem, exp


def main():
    t0 = time.time()
    client = engine.ORClient(tag="fig4")
    qs = engine.load_mmlu("high_school_biology")
    n_train = int(len(qs) * TRAIN_PERCENT)
    train, test = qs[:n_train], qs[n_train:]
    if SPLIT == "rev":
        train, test = qs[-n_train:], qs[: len(qs) - n_train]
    if os.environ.get("ES_RELOAD") == "1" and os.path.exists(DB_EXP) and os.path.exists(DB_MEM):
        mem = json.load(open(DB_MEM))["db"]
        exp = json.load(open(DB_EXP))["db"]
        print(f"[build] reloaded memory={len(mem)} experience={len(exp)}", flush=True)
    else:
        train, test, mem, exp = build(client)

    with open(DB_MEM, "w") as f:
        json.dump({"db": mem, "tokenized_corpus": [engine.tokenize_str(x) for x in mem]}, f)
    with open(DB_EXP, "w") as f:
        json.dump({"db": exp, "tokenized_corpus": [engine.tokenize_str(x) for x in exp]}, f)
    print(f"[build] memory db={len(mem)} experience db={len(exp)}", flush=True)

    db_mem = runner.open_db(None, port=4005)
    runner.load_db_into(db_mem, DB_MEM)
    db_exp = runner.open_db(None, port=4006)
    runner.load_db_into(db_exp, DB_EXP)

    ctx_mem = runner.retrieve_batch(db_mem, test)
    ctx_exp = runner.retrieve_batch(db_exp, test)
    ctx_plain = [""] * len(test)
    opts_clean = [[engine.clean_str(o) for o in q["options"]] for q in test]

    payload = {"model": engine.MODEL, "split": SPLIT, "n_train": len(train),
               "n_test": len(test), "n_memory": len(mem), "n_experience": len(exp),
               "passes": [], "per_question": {"plain": [0] * len(test),
                                              "memory": [0] * len(test),
                                              "experience": [0] * len(test)}}
    start = 0
    if os.environ.get("ES_CONTINUE") == "1" and os.path.exists(OUT):
        prev = json.load(open(OUT))
        payload["passes"] = prev["passes"]
        start = len(prev["passes"])
        print(f"[eval] continuing from pass {start}", flush=True)

    for p in range(start, start + PASSES):
        pt = time.time()
        jobs = [(cond, i, r) for cond in ("plain", "memory", "experience")
                for i in range(len(test)) for r in range(1)]

        def gen(job):
            cond, i, _ = job
            ctx = {"plain": ctx_plain, "memory": ctx_mem, "experience": ctx_exp}[cond][i]
            prompt = engine.precise_question_prompt(test[i]["question"], opts_clean[i], ctx)
            raw = client.clean_pipe(prompt, max_tokens=160)
            cand = engine.extract_answer(raw)
            cor, strict, _ = engine.is_correct(cand, opts_clean[i], test[i]["truth"])
            return cond, i, strict

        res = engine.pmap(gen, jobs, label=f"pass{p + 1}")
        acc = {c: 100 * sum(ok for cc, _i, ok in res if cc == c) /
                   sum(1 for cc, _i, _o in res if cc == c)
               for c in ("plain", "memory", "experience")}
        for cond, i, ok in res:
            payload["per_question"][cond][i] += int(ok)
        payload["passes"].append({"pass": p + 1, **acc, "secs": round(time.time() - pt, 1)})
        print(f"[eval] pass {p + 1}/{PASSES}: plain={acc['plain']:.1f} "
              f"memory={acc['memory']:.1f} experience={acc['experience']:.1f}", flush=True)
        with open(OUT, "w") as f:
            json.dump(payload, f, indent=1)

    print(f"saved {OUT} in {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
