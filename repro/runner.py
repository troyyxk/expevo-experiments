"""Core loops shared by the Fig.5 / Fig.6 reproduction scripts."""
import json
import os
import time

import engine
from engine import (
    FastVectorDB,
    ORClient,
    clean_str,
    confidence_prompt,
    extract_answer,
    is_correct,
    pmap,
    precise_question_prompt,
)


def open_db(lm, port=4001):
    db = FastVectorDB(port, lm)
    db.fileIO.close()
    db.fileIO = open(os.devnull, "w")  # silence per-query logging
    return db


def retrieval_query(q, clean_opts):
    return " ".join([q["question"]] + clean_opts)


def retrieve_batch(db, questions, workers=8):
    db.ensure()
    qs = [retrieval_query(q, [clean_str(o) for o in q["options"]]) for q in questions]
    docs = pmap(lambda s: db.get(s)[1], qs, workers=workers)
    return [" --- ".join(d) for d in docs]


def answer_batch(client, questions, contexts, rounds, tag, max_tokens=160):
    tasks = [(qi, r) for qi in range(len(questions)) for r in range(rounds)]

    def gen(t):
        qi, _ = t
        q = questions[qi]
        prompt = precise_question_prompt(q["question"], q["options"], contexts[qi])
        raw = client.clean_pipe(prompt, max_tokens=max_tokens)
        cand = extract_answer(raw)
        cor, strict, norm = is_correct(cand, q["options"], q["truth"])
        return {"qi": qi, "correct": cor, "strict": strict, "answer": norm}

    res = pmap(gen, tasks, label=tag)
    per_q = [[] for _ in questions]
    for r in res:
        per_q[r["qi"]].append(r)
    return per_q


def confidence_batch(client, questions, contexts, per_question, tag, max_tokens=120):
    """per_question[i][ri] = {"answer":..., "correct":...} for question i round ri."""
    tasks = [
        (qi, ri)
        for qi in range(len(questions))
        for ri in range(min(len(per_question[qi]), CONF_ROUNDS))
    ]

    def gen(t):
        qi, ri = t
        q = questions[qi]
        target = per_question[qi][ri]["answer"]
        prompt = confidence_prompt(q["question"], target, q["options"], contexts[qi])
        raw = client.clean_pipe(prompt, max_tokens=max_tokens)
        txt = extract_answer(raw).strip().rstrip("%").strip()
        try:
            val = int(float(txt))
            ok = 0 <= val <= 100
        except Exception:
            val, ok = -1, False
        return {
            "qi": qi,
            "conf": val,
            "ok": ok,
            "correct": per_question[qi][ri]["correct"],
            "raw": extract_answer(raw)[:40],
        }

    return pmap(gen, tasks, label=tag)


CONF_ROUNDS = 2


def distill_batch(client, questions, per_question, tag, strict=False):
    """strict=True mirrors teacher_model.exam_result (clean_str(answer)==clean_truth)."""
    key = "strict" if strict else "correct"

    def gen(qi):
        q = questions[qi]
        correct = [r["answer"] for r in per_question[qi] if r[key]]
        wrong = list(dict.fromkeys(r["answer"] for r in per_question[qi] if not r[key]))
        return client.generate_QA_distillation(q["question"], correct, wrong)

    return pmap(gen, list(range(len(questions))), label=tag, every=50)


def save_db(db, path):
    with open(path, "w") as f:
        json.dump(
            {"db": db.db, "tokenized_corpus": db.tokenized_corpus},
            f,
            ensure_ascii=False,
        )
    return len(db.db)


def load_db_into(db, path):
    with open(path) as f:
        d = json.load(f)
    db.db = d["db"]
    db.tokenized_corpus = d["tokenized_corpus"]
    db._dirty = True
    db._S = None
    db.ensure()
    return len(db.db)


def epoch_metrics(per_question, confs=None):
    n = len(per_question)
    acc = sum(sum(1 for r in p if r["correct"]) for p in per_question) / (n * len(per_question[0]))
    acc_strict = sum(sum(1 for r in p if r["strict"]) for p in per_question) / (n * len(per_question[0]))
    out = {"acc": 100 * acc, "acc_strict": 100 * acc_strict, "n": n}
    if confs is not None:
        right = [c["conf"] for c in confs if c["ok"] and c.get("correct") is True]
        wrong = [c["conf"] for c in confs if c["ok"] and c.get("correct") is False]
        allc = [c["conf"] for c in confs if c["ok"]]
        out["conf_all"] = sum(allc) / len(allc) if allc else None
        out["conf_right"] = sum(right) / len(right) if right else None
        out["conf_wrong"] = sum(wrong) / len(wrong) if wrong else None
        out["conf_valid_frac"] = len(allc) / max(len(confs), 1)
    return out
