#!/usr/bin/env python3
"""Assert that the CSV, the LaTeX table and the two prose paragraphs carry the same numbers."""
import csv, os, re, sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
rows = {(r["group"], r["metric"]): r for r in
        csv.DictReader(open(os.path.join(HERE, "results", "backend_overhead_table.csv")))}
table = open(os.path.join(HERE, "latex", "table_backend_overhead.tex")).read()
prose = open(os.path.join(HERE, "latex", "ve_backend_overhead_results.tex")).read()
log = open(os.path.join(HERE, "REVISION_LOG.md")).read()
summ = {r["operation"]: r for r in
        csv.DictReader(open(os.path.join(HERE, "results", "local_maintenance_summary.csv")))}

checks = []


def check(name, cond):
    checks.append((name, bool(cond)))


# 1. table cells must appear verbatim in the LaTeX table
for (group, metric), r in rows.items():
    if "reduction" in metric.lower():
        continue  # derived row, quoted in the prose rather than tabulated
    for col in ("full", "refined"):
        v = r[col]
        if v in ("--", ""):
            continue
        check(f"table has {metric} [{col}] = {v}", v.replace(",", "{,}") in table)

# 2. the prose quotes the retrieval and maintenance numbers
for token in ("22.67", "3.60", "37.72", "5.73", "84.1", "84.8", "94.1", "92.5", "150.3", "0.38",
              "275", "186{,}279", "12{,}864", "1.69", "4.05", "0.0103", "6{,}000", "942", "84.3"):
    check(f"prose mentions {token}", token in prose.replace("\\,", ""))

check("prose states the P50 reduction 84.1%", "84.1" in prose)

# 3. the log reports the all-run medians, not the median of session medians
check("log has matrix median 94.137", "94.137" in log)
check("log has grouping median 0.380", "0.380" in log)
check("log keeps per-session medians", "93.113" in log and "115.886" in log)

# 4. the summary CSV itself
check("summary matrix median = 94.137", abs(float(summ["bm25_similarity_matrix"]["time_median_s"]) - 94.137) < 1e-9)
check("summary grouping median = 0.380", abs(float(summ["anchor_grouping"]["time_median_s"]) - 0.380) < 1e-9)
check("summary matrix range 92.494-150.343",
      float(summ["bm25_similarity_matrix"]["time_min_s"]) == 92.494
      and float(summ["bm25_similarity_matrix"]["time_max_s"]) == 150.343)
check("summary keeps 6 runs", int(summ["bm25_similarity_matrix"]["runs"]) == 6)

bad = [n for n, ok in checks if not ok]
for n, ok in checks:
    print(("  PASS  " if ok else "  FAIL  ") + n)
print(f"\n{len(checks) - len(bad)}/{len(checks)} checks passed")
sys.exit(1 if bad else 0)
