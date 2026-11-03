#!/usr/bin/env python3
"""Freeze an extended held-out set: 40 questions per subject that were never used.

Reconstructs the P7 sampling (same seed, same shuffle) to recover the 75 used rows, verifies the
reconstruction against the saved construction/heldout files (by row index AND question text), then
samples 40 unused rows per subject. The resulting list is immutable and shared by all five settings.
"""
import hashlib
import json
import os
import random

def _release_root(start=None):
    """Locate the release root (the directory that contains p7/expevo_lifecycle/runs)."""
    d = os.path.dirname(os.path.abspath(start or __file__))
    for _ in range(8):
        if os.path.isdir(os.path.join(d, "p7", "expevo_lifecycle", "runs")):
            return d
        nd = os.path.dirname(d)
        if nd == d:
            break
        d = nd
    return None


def _p7_run(name="p7_full100"):
    """P7 run directory: EXPEVO_P7_RUN overrides, otherwise resolved inside the release."""
    env = os.environ.get("EXPEVO_P7_RUN")
    if env and os.path.isdir(env):
        return env
    root = _release_root()
    if root:
        p = os.path.join(root, "p7", "expevo_lifecycle", "runs", name)
        if os.path.isdir(p):
            return p
    return None


import pandas as pd

P7 = _p7_run()
DATA = os.path.join(os.path.dirname(P7), "..", "..", "data")
OUT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SUBJECTS = ["international_law", "college_medicine", "college_biology", "high_school_geography"]
SEED_P7 = 20261026
SEED_NEW = 20261028
N_NEW = 40
LETTERS = "ABCD"


def norm(t):
    return " ".join(str(t).lower().split())


def main():
    man = json.load(open(f"{P7}/manifest_prepare.json"))["subjects"]
    out_rows, manifest = [], {"seed_p7": SEED_P7, "seed_new": SEED_NEW,
                              "n_new_per_subject": N_NEW,
                              "dataset_revision": "c30699e8356da336a370243923dbaf21066bb9fe",
                              "subjects": {}}
    for s in SUBJECTS:
        df = pd.read_parquet(f"{DATA}/{s}-test.parquet")
        rng = random.Random(SEED_P7)
        idx = list(range(len(df)))
        rng.shuffle(idx)
        picked = idx[:75]                      # exactly what prepare_mmlu did
        n_rows = man[s]["n_rows_in_split"]
        assert len(df) == n_rows, (s, len(df), n_rows)

        # verify the reconstruction against the saved files (row index and text)
        held = [json.loads(l) for l in open(f"{P7}/heldout/{s}.jsonl")]
        for h in held:
            assert h["row_index"] in picked[60:], f"{s}: heldout row {h['row_index']} not in reconstruction"
            assert norm(df.iloc[h["row_index"]]["question"]) == norm(h["question"]), f"{s}: text mismatch"
        cons_ids = set(man[s]["construction_ids"])
        assert len(cons_ids) == 60

        # unused pool, additionally guarded by question text
        used_text = {norm(df.iloc[i]["question"]) for i in picked}
        unused = [i for i in range(len(df))
                  if i not in set(picked) and norm(df.iloc[i]["question"]) not in used_text]
        if len(unused) < N_NEW:
            raise SystemExit(f"{s}: only {len(unused)} unused questions, need {N_NEW}")
        rng2 = random.Random(SEED_NEW)
        chosen = sorted(rng2.sample(unused, N_NEW))
        for rank, i in enumerate(chosen):
            row = df.iloc[i]
            out_rows.append({"qid": f"{s}/X{rank:03d}", "subject": s, "question_set": "extended",
                             "row_index": int(i), "question": row["question"],
                             "choices": list(row["choices"]),
                             "gold_answer": LETTERS[int(row["answer"])],
                             "gold_index": int(row["answer"])})
        manifest["subjects"][s] = {
            "n_rows_in_split": len(df), "n_used_by_p7": len(picked),
            "n_unused_pool": len(unused), "n_sampled_new": len(chosen),
            "new_row_indices": [int(x) for x in chosen],
            "new_qids": [f"{s}/X{r:03d}" for r in range(len(chosen))],
            "sha256": hashlib.sha256(json.dumps(chosen).encode()).hexdigest()}
        print(f"{s:<24} rows={len(df):>3} used=75 unused={len(unused):>3} -> sampled {len(chosen)}")

    # global guard: no overlap with construction or original heldout, by id or text
    used_qids = set()
    used_texts = set()
    for s in SUBJECTS:
        used_qids |= set(man[s]["construction_ids"]) | set(man[s]["heldout_ids"])
        for h in [json.loads(l) for l in open(f"{P7}/heldout/{s}.jsonl")]:
            used_texts.add(norm(h["question"]))
    for e in out_rows:
        assert e["qid"] not in used_qids
        assert norm(e["question"]) not in used_texts, e["qid"]
    texts = [norm(e["question"]) for e in out_rows]
    assert len(texts) == len(set(texts)), "duplicate question text inside the new set"

    os.makedirs(f"{OUT}/eval", exist_ok=True)
    with open(f"{OUT}/eval/heldout_extended.jsonl", "w") as f:
        for e in out_rows:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    manifest["n_total"] = len(out_rows)
    manifest["sha256_file"] = hashlib.sha256(
        open(f"{OUT}/eval/heldout_extended.jsonl", "rb").read()).hexdigest()
    json.dump(manifest, open(f"{OUT}/eval/heldout_extended_manifest.json", "w"), indent=1)
    print(f"\nfrozen {len(out_rows)} questions -> eval/heldout_extended.jsonl "
          f"sha256={manifest['sha256_file'][:16]}")


if __name__ == "__main__":
    main()
