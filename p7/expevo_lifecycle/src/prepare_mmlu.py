"""Freeze the MMLU construction/heldout split BEFORE any LLM call.

Deterministic: seed -> shuffled row indices -> first n_sampled; the first
`construction_frac` of them form the construction pool, the rest is heldout and
must never appear in any prompt.
"""
import argparse
import json
import os
import random

import pandas as pd

from .common import load_config, load_env, now_iso, sha256_file, write_json, write_jsonl

LETTERS = "ABCD"


def _load_subject(cfg, subject):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", cfg["data"]["data_dir"],
                        f"{subject}-{cfg['data']['split']}.parquet")
    path = os.path.abspath(path)
    df = pd.read_parquet(path)
    for col in ("question", "choices", "answer"):
        if col not in df.columns:
            raise ValueError(f"{path}: missing column {col}")
    # `answer` is a 0..3 class index -- verify instead of assuming strings
    answers = [int(a) for a in df["answer"].tolist()]
    if not all(0 <= a < len(c) for a, c in zip(answers, df["choices"].tolist())):
        raise ValueError(f"{path}: answer index out of range")
    return df, answers


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    args = ap.parse_args()
    cfg = load_config(args.config)
    run_dir = os.path.join(cfg["runtime"]["runs_dir"], cfg["run_id"])
    run_dir = os.path.abspath(run_dir)
    os.makedirs(run_dir, exist_ok=True)

    manifest = {
        "run_id": cfg["run_id"],
        "stage": "prepare_mmlu",
        "started_at": now_iso(),
        "seed": cfg["seed"],
        "dataset": {
            "repo": cfg["data"]["dataset_repo"],
            "revision": cfg["data"]["dataset_revision"],
            "split": cfg["data"]["split"],
        },
        "subjects": {},
    }

    for subject in cfg["data"]["subjects"]:
        df, answers = _load_subject(cfg, subject)
        rng = random.Random(cfg["seed"])
        idx = list(range(len(df)))
        rng.shuffle(idx)
        n = int(cfg["data"]["n_sampled_per_subject"])
        if n > len(idx):
            raise ValueError(
                f"{subject}: only {len(idx)} rows available, requested {n} "
                "(do NOT repeat-sample to fill the quota)"
            )
        picked = idx[:n]
        n_con = int(round(n * cfg["data"]["construction_frac"]))
        con_idx, held_idx = picked[:n_con], picked[n_con:]

        def rows(indices, pool, rank_offset=0):
            out = []
            for rank, i in enumerate(indices):
                row = df.iloc[int(i)]
                choices = list(row["choices"])
                out.append(
                    {
                        "qid": f"{subject}/Q{rank + rank_offset:03d}",
                        "subject": subject,
                        "pool": pool,
                        "row_index": int(i),
                        "question": row["question"],
                        "choices": choices,
                        "gold_answer": LETTERS[int(row["answer"])],
                        "gold_index": int(row["answer"]),
                    }
                )
            return out

        con = rows(con_idx, "construction", 0)
        held = rows(held_idx, "heldout", len(con_idx))
        write_jsonl(os.path.join(run_dir, "dataset", f"{subject}.jsonl"), con)
        write_jsonl(os.path.join(run_dir, "heldout", f"{subject}.jsonl"), held)
        manifest["subjects"][subject] = {
            "n_rows_in_split": len(df),
            "n_sampled": n,
            "n_construction": len(con),
            "n_heldout": len(held),
            "construction_ids": [r["qid"] for r in con],
            "heldout_ids": [r["qid"] for r in held],
            "construction_sha256": sha256_file(os.path.join(run_dir, "dataset", f"{subject}.jsonl")),
            "heldout_sha256": sha256_file(os.path.join(run_dir, "heldout", f"{subject}.jsonl")),
        }
        print(f"[prepare] {subject:<22} rows={len(df):>3} sampled={n:>2} "
              f"construction={len(con):>2} heldout={len(held):>2}")

    manifest["finished_at"] = now_iso()
    write_json(os.path.join(run_dir, "manifest_prepare.json"), manifest)
    print(f"[prepare] run dir: {run_dir}")


if __name__ == "__main__":
    main()
