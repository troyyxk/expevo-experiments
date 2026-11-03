#!/usr/bin/env python3
"""Phase D: join per-sample predictions with repository resources -> per-question, per-subject,
per-setting accuracies and the Table 2 payload."""
import csv
import json
import os
from collections import defaultdict

OUT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SETTINGS = ["Full", "BM25_100", "BM25_80", "BM25_60", "BM25_40"]
SUBJECTS = ["international_law", "college_medicine", "college_biology", "high_school_geography"]
NICE = {"international_law": "International Law", "college_medicine": "College Medicine",
        "college_biology": "College Biology", "high_school_geography": "High School Geography"}


def read_jsonl(p):
    with open(p, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def main():
    preds = read_jsonl(os.path.join(OUT, "eval", "predictions.jsonl"))
    ext_path = os.path.join(OUT, "eval", "predictions_extended.jsonl")
    if os.path.exists(ext_path):
        ext = read_jsonl(ext_path)
        for r in ext:
            r.setdefault("question_set", "extended")
        preds = preds + ext
        print(f"merged {len(ext)} extended-set responses")
    for r in preds:
        r.setdefault("question_set", "original")
    res = list(csv.DictReader(open(os.path.join(OUT, "tables", "refinement_resource_by_subject.csv"))))
    res_tot = {r["setting"]: r for r in csv.DictReader(
        open(os.path.join(OUT, "tables", "refinement_resource_totals.csv")))}

    # per question
    per_q = defaultdict(lambda: {"n": 0, "n_parsed": 0, "n_correct": 0, "n_refused": 0,
                                 "repo_sha": "", "question_set": ""})
    for r in preds:
        k = (r["subject"], r["setting"], r["question_id"])
        d = per_q[k]
        d["n"] += 1
        d["repo_sha"] = r["repository_sha256"]
        d["question_set"] = r.get("question_set", "original")
        if r.get("predicted_option"):
            d["n_parsed"] += 1
            d["n_correct"] += 1 if r["correct"] else 0
        else:
            d["n_refused"] += 1
    rows_q = []
    for (s, c, q), d in sorted(per_q.items()):
        # primary definition: every sampled response counts, a refusal is simply incorrect
        acc = d["n_correct"] / d["n"] if d["n"] else None
        acc_ans = d["n_correct"] / d["n_parsed"] if d["n_parsed"] else None
        rows_q.append({"run_id": "p10_backend_refinement", "subject": s, "question_id": q, "setting": c,
                       "question_set": d.get("question_set", ""),
                       "n_samples": d["n"], "n_parsed": d["n_parsed"], "n_correct": d["n_correct"],
                       "n_refused": d["n_refused"],
                       "question_accuracy": f"{acc:.6f}" if acc is not None else "",
                       "question_accuracy_answered_only": f"{acc_ans:.6f}" if acc_ans is not None else "",
                       "repository_sha256": d["repo_sha"],
                       "eval_status": "complete" if d["n_parsed"] == d["n"] else "with_refusals"})
    with open(os.path.join(OUT, "tables", "accuracy_by_question.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows_q[0].keys())); w.writeheader(); w.writerows(rows_q)

    # per subject
    subj = defaultdict(lambda: {"acc": [], "n": 0, "n_parsed": 0})
    for r in rows_q:
        d = subj[(r["subject"], r["setting"])]
        d["n"] += r["n_samples"]; d["n_parsed"] += r["n_parsed"]
        if r["question_accuracy"] != "":
            d["acc"].append(float(r["question_accuracy"]))
    rows_s = []
    for s in SUBJECTS:
        for c in SETTINGS:
            d = subj[(s, c)]
            acc = sum(d["acc"]) / len(d["acc"]) if d["acc"] else None
            rr = next(r for r in res if r["subject"] == s and r["setting"] == c)
            rows_s.append({"subject": s, "setting": c, "n_questions": len(d["acc"]), "n_samples": d["n"],
                           "n_parsed": d["n_parsed"],
                           "subject_accuracy": f"{acc:.6f}" if acc is not None else "",
                           "storage_mb": rr["storage_mb"], "entry_count": rr["entry_count"],
                           "storage_reduction_pct": rr["storage_reduction_pct"],
                           "entry_reduction_pct": rr["entry_reduction_pct"]})
    with open(os.path.join(OUT, "tables", "accuracy_by_subject.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows_s[0].keys())); w.writeheader(); w.writerows(rows_s)

    # breakdown by question set (original 15 vs extended 40)
    qset = defaultdict(lambda: {"acc": [], "sets": set()})
    for r in rows_q:
        k = (r["question_set"], r["setting"])
        if r["question_accuracy"] != "":
            qset[k]["acc"].append(float(r["question_accuracy"]))
            qset[k]["sets"].add(r["subject"])
    qs_rows = []
    for (qset_name, setting), d in sorted(qset.items()):
        qs_rows.append({"question_set": qset_name, "setting": setting,
                        "n_questions": len(d["acc"]), "n_subjects": len(d["sets"]),
                        "accuracy_pct": f"{100*sum(d['acc'])/len(d['acc']):.2f}" if d["acc"] else ""})
    with open(os.path.join(OUT, "tables", "accuracy_by_question_set.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["question_set", "setting", "n_questions", "n_subjects", "accuracy_pct"])
        w.writeheader(); w.writerows(qs_rows)

    # macro accuracy per setting
    macro, delta = {}, {}
    for c in SETTINGS:
        vals = [float(r["subject_accuracy"]) for r in rows_s if r["setting"] == c and r["subject_accuracy"] != ""]
        macro[c] = 100 * sum(vals) / len(vals) if vals else None
    for c in SETTINGS:
        delta[c] = None if (macro[c] is None or macro["Full"] is None) else macro[c] - macro["Full"]

    t2 = []
    for c in SETTINGS:
        v = res_tot[c]
        t2.append({"setting": c,
                   "accuracy_macro_pct": f"{macro[c]:.2f}" if macro[c] is not None else "",
                   "accuracy_delta_pp": f"{delta[c]:+.2f}" if delta[c] is not None else "",
                   "storage_total_bytes": v["total_storage_bytes"],
                   "storage_total_mb": f"{float(v['total_storage_mb']):.3f}",
                   "indexed_entries_total": v["total_entries"],
                   "storage_reduction_pct": f"{float(v['storage_reduction_pct']):.2f}",
                   "entry_reduction_pct": f"{float(v['entry_reduction_pct']):.2f}",
                   "n_subjects": 4, "n_questions_total": len({r["question_id"] for r in rows_q}) // 5,
                   "n_samples_per_question": max(r["n_samples"] for r in rows_q),
                   "complete": "true" if all(r["eval_status"] == "complete" for r in rows_q) else "false"})
    with open(os.path.join(OUT, "tables", "quality_resource_table2.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(t2[0].keys())); w.writeheader(); w.writerows(t2)

    print(f"questions={len(rows_q)} predictors={len(preds)}")
    print(f"{'setting':<9}{'macro_acc':>10}{'delta_pp':>10}{'storage_MB':>12}{'entries':>9}")
    for r in t2:
        print(f"{r['setting']:<9}{r['accuracy_macro_pct']:>10}{r['accuracy_delta_pp']:>10}"
              f"{r['storage_total_mb']:>12}{r['indexed_entries_total']:>9}")


if __name__ == "__main__":
    main()
