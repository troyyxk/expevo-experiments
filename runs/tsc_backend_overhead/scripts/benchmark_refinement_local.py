#!/usr/bin/env python3
"""Phase C: time the BM25 similarity-matrix build and anchor grouping on the full 6,000-entry library.

The functions are imported from the frozen src/refine.py and called unchanged; only the timing wrapper is
new. Nothing is written back to the repositories.

Two modes:
  default           run the timings (SESSIONS x REPEATS) and write raw/ + results/
  --aggregate-only  re-summarise results/ from the existing raw/local_refinement_runs.csv, no timing
"""
import argparse, csv, gc, json, os, resource, statistics, sys, time
import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(os.path.dirname(HERE))
P7 = os.path.join(ROOT, "p7", "expevo_lifecycle", "runs", "p7_full100")
sys.path.insert(0, os.path.join(ROOT, "p7", "expevo_lifecycle"))
from src.refine import build_matrix, group_ids  # noqa: E402  (frozen implementation; nothing else is run)

SUBJECT = "high_school_geography"
THRESHOLD = 40
REPEATS = 3
SESSIONS = 2
RAW = os.path.join(HERE, "raw", "local_refinement_runs.csv")
SUMMARY = os.path.join(HERE, "results", "local_maintenance_summary.csv")


def read_jsonl(p):
    with open(p, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def summarise(rows, matrix_mb):
    """Median over ALL raw runs; per-session medians are kept alongside to show drift between sessions."""
    summ = []
    for op in ("bm25_similarity_matrix", "anchor_grouping"):
        sub = [r for r in rows if r["operation"] == op]
        vals = [float(r["elapsed_s"]) for r in sub]
        per_session = [round(statistics.median([float(r["elapsed_s"]) for r in sub
                                                if int(r["session"]) == sess]), 3)
                       for sess in sorted({int(r["session"]) for r in sub})]
        summ.append({"operation": op, "runs": len(vals), "sessions": len(per_session),
                     "time_mean_s": round(statistics.mean(vals), 3),
                     "time_median_s": round(statistics.median(vals), 3),
                     "time_min_s": round(min(vals), 3), "time_max_s": round(max(vals), 3),
                     "time_by_session_s": ";".join(f"{v:.3f}" for v in per_session),
                     "memory_note": f"{matrix_mb:.0f} MB float64 matrix, "
                                    f"{max(float(r['peak_rss_mib']) for r in sub):.0f} MiB peak RSS"})
    with open(SUMMARY, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(summ[0].keys()))
        w.writeheader(); w.writerows(summ)
    for s in summ:
        print(f"[refine] {s['operation']}: median {s['time_median_s']} s over {s['runs']} runs "
              f"(sessions {s['time_by_session_s']}); range {s['time_min_s']}-{s['time_max_s']} s")
    return summ


def run_timings(matrix_mb):
    items = read_jsonl(f"{P7}/full_repositories/{SUBJECT}.jsonl")
    assert len(items) == 6000
    ids = [x["experience_id"] for x in items]
    texts = [x["text"] for x in items]
    n = len(texts)
    avail = int(next(l.split()[1] for l in open("/proc/meminfo") if l.startswith("MemAvailable"))) / 1048576
    print(f"[refine] {n} entries; matrix {matrix_mb:.0f} MB; MemAvailable {avail:.0f} GiB")
    assert avail > matrix_mb / 1024 * 4, "not enough free memory"

    import hashlib
    h = hashlib.sha256("\n".join(texts).encode()).hexdigest()
    rows = []
    for session in range(1, SESSIONS + 1):
        for rep in range(1, REPEATS + 1):
            gc.collect()
            t0 = time.perf_counter()
            S, bm25 = build_matrix(texts, k1=1.5, b=0.75)
            t1 = time.perf_counter()
            mat_s = t1 - t0
            t2 = time.perf_counter()
            groups = group_ids(ids, S, THRESHOLD)
            t3 = time.perf_counter()
            grp_s = t3 - t2
            sizes = [len(g) for g in groups]
            rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
            print(f"[refine] session {session} run {rep}: matrix {mat_s:.2f} s, grouping {grp_s:.2f} s, "
                  f"{len(groups)} groups (max {max(sizes)}, singletons {sum(1 for s in sizes if s==1)}), "
                  f"peak RSS {rss:.0f} MiB")
            rows.append({"session": session, "run_id": rep, "operation": "bm25_similarity_matrix",
                         "subject": SUBJECT, "n_full_entries": n, "threshold": THRESHOLD,
                         "elapsed_s": round(mat_s, 3), "input_hash": h[:16],
                         "algorithm_version": "src/refine.py build_matrix (k1=1.5,b=0.75)",
                         "hardware_id": "xeon8368-152t", "status": "ok",
                         "peak_rss_mib": round(rss, 1), "matrix_mb": round(matrix_mb, 1),
                         "notes": f"session {session}, repeat {rep}; float64 directed matrix"})
            rows.append({"session": session, "run_id": rep, "operation": "anchor_grouping",
                         "subject": SUBJECT, "n_full_entries": n, "threshold": THRESHOLD,
                         "elapsed_s": round(grp_s, 3), "input_hash": h[:16],
                         "algorithm_version": "src/refine.py group_ids",
                         "hardware_id": "xeon8368-152t", "status": "ok",
                         "peak_rss_mib": round(rss, 1), "matrix_mb": round(matrix_mb, 1),
                         "notes": f"session {session}, repeat {rep}; tau_sim={THRESHOLD}; "
                                  f"{len(groups)} groups, max size {max(sizes)}, "
                                  f"{sum(1 for s in sizes if s == 1)} singletons"})
            del S, bm25, groups
            gc.collect()
    with open(RAW, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--aggregate-only", action="store_true",
                    help="re-summarise results/ from the existing raw CSV without re-timing")
    a = ap.parse_args()
    n = 6000
    matrix_mb = n * n * 8 / 1e6
    if a.aggregate_only:
        rows = list(csv.DictReader(open(RAW)))
        assert rows, f"no raw runs in {RAW}"
        print(f"[refine] aggregate-only: {len(rows)} raw rows from {os.path.relpath(RAW, HERE)} "
              f"(no timing performed)")
        summarise(rows, matrix_mb)
        return
    rows = run_timings(matrix_mb)
    summarise(rows, matrix_mb)


if __name__ == "__main__":
    main()
