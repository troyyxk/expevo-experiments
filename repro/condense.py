"""Offline experience-DB condensation (Fig.6), using the repo's own
`VectorDB.group_and_combine_similar()`.

  python condense.py prep --db out/fig6_db_full.json --matrix out/fig6_S.npy
  python condense.py run  --db out/fig6_db_full.json --matrix out/fig6_S.npy \
                          --threshold 100 --out out/fig6_db_bm100.json
"""
import argparse
import contextlib
import json
import os
import sys

import numpy as np

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

import engine  # noqa: E402
import runner  # noqa: E402


def make_db(corpus, tokenized, port=4003, lm=None):
    db = engine.FastVectorDB(port, lm)
    db.db = list(corpus)
    db.tokenized_corpus = [list(t) for t in tokenized]
    db._dirty = True
    db.ensure()
    return db


def load_payload(path):
    with open(path) as f:
        d = json.load(f)
    return d["db"], d["tokenized_corpus"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["prep", "run"])
    ap.add_argument("--db", required=True)
    ap.add_argument("--matrix")
    ap.add_argument("--threshold", type=float)
    ap.add_argument("--out")
    args = ap.parse_args()

    corpus, tok = load_payload(args.db)

    if args.cmd == "prep":
        db = make_db(corpus, tok)
        print(f"[prep] n={len(corpus)} computing {len(corpus)}x{len(corpus)} BM25 matrix ...",
              flush=True)
        with open(os.devnull, "w") as devnull, contextlib.redirect_stdout(devnull):
            S = db._get_similarity_matrix()
        np.save(args.matrix, S)
        np.fill_diagonal(S, 0)
        iu = np.triu_indices(len(corpus), k=1)
        off = S[iu]
        print(f"[prep] saved {args.matrix}  off-diag: median={np.median(off):.2f} "
              f"p90={np.percentile(off, 90):.2f} p99={np.percentile(off, 99):.2f} "
              f"max={off.max():.2f}", flush=True)
        return

    lm = engine.ORClient(tag=f"condense_bm{args.threshold:g}")
    db = make_db(corpus, tok, lm=lm)
    db._S = np.load(args.matrix)
    db.similarity_bm25th = args.threshold
    groups = db._find_similar_groups()
    n_groups = len(groups)
    sizes = sorted((len(g) for g in groups), reverse=True)
    if os.environ.get("ES_PARALLEL_CONDENSE") == "1" and groups:
        used = set()
        for g in groups:
            used.update(g)
        new_db = [db.db[i] for i in range(len(db.db)) if i not in used]
        new_tok = [db.tokenized_corpus[i] for i in range(len(db.db)) if i not in used]
        from util import tokenize_str as _tok
        condensed = engine.pmap(db._safe_combine, groups,
                                workers=int(os.environ.get("ES_CONC", "20")),
                                label="condense")
        for c in condensed:
            if not c:
                continue
            new_db.append(c)
            new_tok.append(_tok(c))
        db.db, db.tokenized_corpus = new_db, new_tok
        db._update_bm25()
    else:
        with open(os.devnull, "w") as devnull, contextlib.redirect_stdout(devnull):
            print(f"groups={n_groups} sizes[:10]={sizes[:10]} covered={sum(sizes)}")
            db.group_and_combine_similar()
    n_after = len(db.db)
    stats = {
        "threshold": args.threshold,
        "n_before": len(corpus),
        "n_after": n_after,
        "n_groups": n_groups,
        "group_sizes_top10": sizes[:10],
        "covered": sum(sizes),
        "compression": round(100 * n_after / len(corpus), 1),
    }
    with open(args.out.replace(".json", ".stats.json"), "w") as f:
        json.dump(stats, f, indent=1)
    with open(args.out, "w") as f:
        json.dump({"db": db.db, "tokenized_corpus": db.tokenized_corpus}, f, ensure_ascii=False)
    print(f"[th={args.threshold}] {len(corpus)} -> {n_after} "
          f"({stats['compression']}%), groups={n_groups}, covered={sum(sizes)}", flush=True)


if __name__ == "__main__":
    main()
