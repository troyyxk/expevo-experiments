#!/usr/bin/env python3
"""Where does the query time go? Tokenisation vs BM25 scoring vs Top-5 ranking (P10's exact code path).

Runs outside the 5-repeat benchmark; one pass over the 55 queries per repository, 3 passes, medians.
"""
import csv, json, os, re, statistics, time
import numpy as np
from rank_bm25 import BM25Okapi

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(os.path.dirname(HERE))
P7 = os.path.join(ROOT, "p7", "expevo_lifecycle", "runs", "p7_full100")
SUBJECT = "high_school_geography"
TOK = re.compile(r"[a-z0-9]+")


def tokenize(t):
    return TOK.findall(t.lower())


def read_jsonl(p):
    with open(p, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def main():
    queries = json.load(open(os.path.join(HERE, "manifests", "queries.json")))
    repos = {}
    for name, path, idk in (("full", f"{P7}/full_repositories/{SUBJECT}.jsonl", "experience_id"),
                            ("refined", f"{P7}/refined/{SUBJECT}/bm25_40.jsonl", "refined_id")):
        items = [{"id": r[idk], "text": r["text"]} for r in read_jsonl(path)]
        repos[name] = (items, BM25Okapi([tokenize(x["text"]) for x in items], k1=1.5, b=0.75))

    rows = []
    for name, (items, bm25) in repos.items():
        for rep in range(1, 4):
            for q in queries:
                t0 = time.perf_counter(); toks = tokenize(q["query_text"]); t1 = time.perf_counter()
                scores = bm25.get_scores(toks); t2 = time.perf_counter()
                order = sorted(range(len(items)), key=lambda i: (-scores[i], items[i]["id"]))[:5]
                t3 = time.perf_counter()
                rows.append({"repository": name, "entries": len(items), "repeat_id": rep,
                             "query_key": q["query_key"],
                             "tokenize_ms": round((t1 - t0) * 1000, 4),
                             "score_ms": round((t2 - t1) * 1000, 4),
                             "rank_ms": round((t3 - t2) * 1000, 4),
                             "total_ms": round((t3 - t0) * 1000, 4)})
    with open(os.path.join(HERE, "raw", "query_cost_decomposition.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)

    summ = []
    for name in ("full", "refined"):
        sub = [r for r in rows if r["repository"] == name]
        med = {k: statistics.median([r[k] for r in sub]) for k in ("tokenize_ms", "score_ms", "rank_ms", "total_ms")}
        summ.append({"repository": name, "entries": sub[0]["entries"], **{f"{k}": round(v, 4) for k, v in med.items()},
                     "score_share_percent": round(100 * med["score_ms"] / med["total_ms"], 1),
                     "rank_share_percent": round(100 * med["rank_ms"] / med["total_ms"], 1)})
    with open(os.path.join(HERE, "results", "query_cost_decomposition.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(summ[0].keys()))
        w.writeheader(); w.writerows(summ)
    for s in summ:
        print(f"{s['repository']:<8} total {s['total_ms']:.3f} ms = tokenize {s['tokenize_ms']:.3f} + "
              f"score {s['score_ms']:.3f} + rank {s['rank_ms']:.3f}   "
              f"(score {s['score_share_percent']}%, rank {s['rank_share_percent']}%)")


if __name__ == "__main__":
    main()
