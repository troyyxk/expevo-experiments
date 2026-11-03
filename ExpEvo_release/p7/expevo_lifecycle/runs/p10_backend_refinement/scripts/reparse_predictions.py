#!/usr/bin/env python3
"""Apply one documented parser rule to responses that previously had no extractable letter.

Rule: an answer field of the form "<LETTER>. <free text>" (e.g. "D. Mongolia") denotes that letter.
Only rows whose predicted_option is empty are touched; the original text is preserved verbatim and every
repair is logged. Nothing is inferred from the gold label.
"""
import json, os, re

OUT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
p = os.path.join(OUT, "eval", "predictions.jsonl")
log = os.path.join(OUT, "reports", "parse_repairs.jsonl")
rows = [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]
fixed = 0
with open(log, "w") as fh:
    for r in rows:
        if r["predicted_option"]:
            continue
        m = re.search(r'"answer"\s*:\s*"\s*([ABCD])\s*[\.\)]\s', r["raw_text"] or "")
        if not m:
            continue
        letter = m.group(1)
        before = dict(predicted_option=r["predicted_option"], correct=r["correct"], parse_status=r["parse_status"])
        r["predicted_option"] = letter
        r["correct"] = (letter == r["gold_option"])
        r["parse_status"] = "reparsed_letter_prefix"
        fixed += 1
        fh.write(json.dumps({"question_id": r["question_id"], "setting": r["setting"],
                             "sample_idx": r["sample_idx"], "letter": letter,
                             "gold": r["gold_option"], "correct": r["correct"],
                             "rule": "<LETTER>. <text>", "before": before}, ensure_ascii=False) + "\n")
with open(p, "w") as fh:
    for r in rows:
        fh.write(json.dumps(r, ensure_ascii=False) + "\n")
print(f"repaired {fixed} response(s); log -> {log}")
print(f"total responses: {len(rows)}, now parsed: {sum(1 for r in rows if r['predicted_option'])}")
