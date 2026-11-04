#!/usr/bin/env python3
"""Phase D: BM25 index-build time and hot-index query latency, full (6,000) vs refined (942).

Retrieval path copied from P10's evaluate_heldout.py: tokenize(query) -> get_scores -> top-5 with
ascending-id tie-break. Nothing else changes between the two repositories.
"""
import csv, hashlib, json, os, statistics, sys, time
import numpy as np
from rank_bm25 import BM25Okapi

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(os.path.dirname(HERE))
P7 = os.path.join(ROOT, "p7", "expevo_lifecycle", "runs", "p7_full100")
SUBJECT = "high_school_geography"
REPEATS = 5
SESSIONS = 3
K1, B, TOP_K = 1.5, 0.75, 5


def tokenize(text):
    import re
    return re.findall(r"[a-z0-9]+", text.lower())


def read_jsonl(p):
    with open(p, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def sha_ids(ids):
    h = hashlib.sha256()
    for i in ids:
        h.update(i.encode())
    return h.hexdigest()


def load_repo(name):
    if name == "full":
        rows = read_jsonl(f"{P7}/full_repositories/{SUBJECT}.jsonl")
        items = [{"id": r["experience_id"], "text": r["text"]} for r in rows]
    else:
        rows = read_jsonl(f"{P7}/refined/{SUBJECT}/bm25_40.jsonl")
        items = [{"id": r["refined_id"], "text": r["text"]} for r in rows]
    return items


def main():
    queries = json.load(open(os.path.join(HERE, "manifests", "queries.json")))
    assert len(queries) == 55
    repos = {name: load_repo(name) for name in ("full", "refined")}
    assert len(repos["full"]) == 6000 and len(repos["refined"]) == 942

    all_build, all_rows = [], []
    for session in range(1, SESSIONS + 1):
        print(f"[session {session}/{SESSIONS}]")
        build_rows, rows, ref_top = _measure(session, queries, repos)
        all_build += build_rows
        all_rows += rows
    _summarise(all_build, all_rows, queries, repos, ref_top)


def _measure(session, queries, repos):
    # ---- index build (3 repeats each) -------------------------------------
    build_rows, built = [], {}
    for rep in range(1, 4):
        for name in ("full", "refined"):
            items = repos[name]
            t0 = time.perf_counter(); corpus = [tokenize(x["text"]) for x in items]; t1 = time.perf_counter()
            bm25 = BM25Okapi(corpus, k1=K1, b=B); t2 = time.perf_counter()
            build_rows.append({"session": session, "repository": name, "entries": len(items), "run_id": rep,
                               "index_build_s": round(t2 - t1, 4), "tokenize_s": round(t1 - t0, 4),
                               "total_prepare_s": round(t2 - t0, 4), "subject": SUBJECT,
                               "repo_hash": sha_ids([x["id"] for x in items]),
                               "hardware_id": "xeon8368-152t",
                               "notes": "BM25Okapi(corpus,k1=1.5,b=0.75); tokenisation timed separately"})
            if rep == 3:
                built[name] = (bm25, items)
            print(f"[index] {name} run {rep}: build {t2-t1:.4f} s, tokenize {t1-t0:.4f} s")
    # ---- warm-up (untimed) -------------------------------------------------
    for name, (bm25, items) in built.items():
        for q in queries:
            s = bm25.get_scores(tokenize(q["query_text"]))
            order = sorted(range(len(items)), key=lambda i: (-s[i], items[i]["id"]))[:TOP_K]

    # reference top-5 for correctness cross-check
    ref_top = {}
    for name, (bm25, items) in built.items():
        for q in queries:
            s = bm25.get_scores(tokenize(q["query_text"]))
            order = sorted(range(len(items)), key=lambda i: (-s[i], items[i]["id"]))[:TOP_K]
            ref_top[(name, q["query_key"])] = [items[i]["id"] for i in order]

    # ---- timed queries -----------------------------------------------------
    rows = []
    for rep in range(1, REPEATS + 1):
        order = ("full", "refined") if rep % 2 == 1 else ("refined", "full")
        for q in queries:
            for name in order:
                bm25, items = built[name]
                t0 = time.perf_counter()
                scores = bm25.get_scores(tokenize(q["query_text"]))
                idx = sorted(range(len(items)), key=lambda i: (-scores[i], items[i]["id"]))[:TOP_K]
                t1 = time.perf_counter()
                top = [items[i]["id"] for i in idx]
                rows.append({"session": session, "repository": name, "entries": len(items), "repeat_id": rep,
                             "query_key": q["query_key"], "query_order": f"{rep}-{q['query_key']}-{name}",
                             "query_latency_ms": round((t1 - t0) * 1000, 4),
                             "top5_ids_hash": sha_ids(top)[:16],
                             "repo_hash": sha_ids([x["id"] for x in items])[:16]})
    return build_rows, rows, ref_top


def _summarise(build_rows, rows, queries, repos, ref_top):
    with open(os.path.join(HERE, "raw", "index_build_runs.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(build_rows[0].keys()))
        w.writeheader(); w.writerows(build_rows)
    with open(os.path.join(HERE, "raw", "query_latency_per_query.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)

    # ---- correctness: measured top-5 must equal the reference --------------
    measured = {}
    for r in rows:
        measured[(r["repository"], r["query_key"])] = r["top5_ids_hash"]
    mismatches = 0
    for (name, qkey), ids in ref_top.items():
        if measured[(name, qkey)] != sha_ids(ids)[:16]:
            mismatches += 1
    assert mismatches == 0, f"{mismatches} queries returned a different Top-5"
    print(f"[query] correctness: all 55 x 2 repositories reproduce the reference Top-5")

    # ---- summary -----------------------------------------------------------
    summ = []
    for name in ("full", "refined"):
        sub = [r for r in rows if r["repository"] == name]
        vals = np.array([r["query_latency_ms"] for r in sub])
        sess = sorted({r["session"] for r in sub})
        s50 = [float(np.percentile([r["query_latency_ms"] for r in sub if r["session"] == s], 50)) for s in sess]
        s95 = [float(np.percentile([r["query_latency_ms"] for r in sub if r["session"] == s], 95)) for s in sess]
        builds = [r["index_build_s"] for r in build_rows if r["repository"] == name]
        per_rep = {rep: float(np.percentile([r["query_latency_ms"] for r in sub if r["repeat_id"] == rep], 50))
                   for rep in range(1, REPEATS + 1)}
        summ.append({"repository": name, "entries": len(repos[name]), "n_unique_queries": 55,
                     "n_repeats": REPEATS, "n_sessions": len(sess),
                     "n_measured_queries": len(vals),
                     "index_build_s": round(statistics.median(builds), 4),
                     "index_build_min_s": min(builds), "index_build_max_s": max(builds),
                     "query_p50_ms": round(float(np.median(s50)), 4),
                     "query_p95_ms": round(float(np.median(s95)), 4),
                     "query_p50_min_ms": round(min(s50), 4), "query_p50_max_ms": round(max(s50), 4),
                     "query_p95_min_ms": round(min(s95), 4), "query_p95_max_ms": round(max(s95), 4),
                     "query_p50_combined_ms": round(float(np.percentile(vals, 50)), 4),
                     "query_p95_combined_ms": round(float(np.percentile(vals, 95)), 4),
                     "query_mean_ms": round(float(vals.mean()), 4),
                     "query_p50_by_repeat": ";".join(f"{v:.4f}" for v in per_rep.values()),
                     "query_p50_by_session": ";".join(f"{v:.4f}" for v in s50),
                     "query_p95_by_session": ";".join(f"{v:.4f}" for v in s95),
                     "repo_hash": sha_ids([x["id"] for x in repos[name]])[:16]})
    with open(os.path.join(HERE, "results", "retrieval_latency_summary.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(summ[0].keys()))
        w.writeheader(); w.writerows(summ)

    f, r = [s for s in summ if s["repository"] == "full"][0], [s for s in summ if s["repository"] == "refined"][0]
    f50, f95 = float(f["query_p50_ms"]), float(f["query_p95_ms"])
    r50, r95 = float(r["query_p50_ms"]), float(r["query_p95_ms"])
    print(f"[query] full:    build {f['index_build_s']} s, P50 {f50:.2f} ms "
          f"(sessions {f['query_p50_min_ms']:.2f}-{f['query_p50_max_ms']:.2f}), "
          f"P95 {f95:.2f} ms (sessions {f['query_p95_min_ms']:.2f}-{f['query_p95_max_ms']:.2f})")
    print(f"[query] refined: build {r['index_build_s']} s, P50 {r50:.2f} ms "
          f"(sessions {r['query_p50_min_ms']:.2f}-{r['query_p50_max_ms']:.2f}), "
          f"P95 {r95:.2f} ms (sessions {r['query_p95_min_ms']:.2f}-{r['query_p95_max_ms']:.2f})")
    print(f"[query] P50 reduction {100*(1-r50/f50):.1f}%, P95 reduction {100*(1-r95/f95):.1f}%")


if __name__ == "__main__":
    main()
