#!/usr/bin/env python3
"""Step 1: audit the frozen inputs and the inherited request assignment. No LLM calls."""
import hashlib
import json
import os
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(os.path.dirname(HERE))
P7 = os.path.join(ROOT, "p7", "expevo_lifecycle", "runs", "p7_full100")
P10 = os.path.join(ROOT, "p7", "expevo_lifecycle", "runs", "p10_backend_refinement")
PREV = os.path.join(HERE, "..", "tsc_collaboration")
SUBJECT = "high_school_geography"


def read_jsonl(p):
    with open(p, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def sha_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def main():
    eps = {e["episode_id"]: e for e in read_jsonl(f"{P7}/episodes/{SUBJECT}.jsonl")}
    exps = read_jsonl(f"{P7}/experiences/{SUBJECT}.jsonl")
    full = read_jsonl(f"{P7}/full_repositories/{SUBJECT}.jsonl")
    pairs = defaultdict(int)
    missing = 0
    for x in exps:
        e = eps.get(x["source_episode_id"])
        if e is None:
            missing += 1
            continue
        pairs[(e["client_id"], e["source_question_id"])] += 1
    qids = sorted({q for _, q in pairs})
    ids = [x["experience_id"] for x in exps]
    audit = {
        "subject": SUBJECT,
        "n_episodes": len(eps), "n_experiences": len(exps), "n_full": len(full),
        "n_unique_experience_ids": len(set(ids)),
        "n_construction_questions": len(qids),
        "clients": dict(sorted(Counter(e["client_id"] for e in eps.values()).items())),
        "per_client_question_counts": dict(sorted(Counter(pairs.values()).items())),
        "experiences_without_episode": missing,
        "hashes": {f: sha_file(p) for f, p in (
            ("episodes", f"{P7}/episodes/{SUBJECT}.jsonl"),
            ("experiences", f"{P7}/experiences/{SUBJECT}.jsonl"),
            ("full_repository", f"{P7}/full_repositories/{SUBJECT}.jsonl"))},
    }
    assert audit["n_experiences"] == 6000 and audit["n_construction_questions"] == 60
    assert audit["per_client_question_counts"] == {25: 240}, audit["per_client_question_counts"]

    # inherited request assignment
    prev = json.load(open(os.path.join(PREV, "config", "request_assignment.json")))
    qs = prev["questions"]
    held = read_jsonl(f"{P7}/heldout/{SUBJECT}.jsonl")
    ext = [q for q in read_jsonl(os.path.join(P10, "eval", "heldout_extended.jsonl")) if q["subject"] == SUBJECT]
    held_ids = {q["qid"] for q in held}
    ext_ids = {q["qid"] for q in ext}
    audit["evaluation"] = {"n_questions": len(qs),
                           "by_set": {"original": sum(1 for q in qs if q["question_set"] == "original"),
                                      "extended": sum(1 for q in qs if q["question_set"] == "extended")},
                           "client_counts": dict(sorted(Counter(q["requesting_client_id"] for q in qs).items())),
                           "overlap_with_construction": len({q["qid"] for q in qs} & set(qids)),
                           "assignment_seed": prev["assign_seed"],
                           "sha256": sha_file(os.path.join(PREV, "config", "request_assignment.json"))}
    assert len(qs) == 55 and audit["evaluation"]["overlap_with_construction"] == 0
    assert audit["evaluation"]["by_set"] == {"original": 15, "extended": 40}

    os.makedirs(os.path.join(HERE, "manifests"), exist_ok=True)
    json.dump(audit, open(os.path.join(HERE, "manifests", "input_audit.json"), "w"), indent=1)
    print(json.dumps({k: audit[k] for k in ("n_experiences", "n_construction_questions", "clients",
                                            "per_client_question_counts", "experiences_without_episode")}, indent=1))
    print("evaluation:", audit["evaluation"])


if __name__ == "__main__":
    main()
