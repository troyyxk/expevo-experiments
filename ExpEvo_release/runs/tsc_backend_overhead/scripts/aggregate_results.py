#!/usr/bin/env python3
"""Phase E: assemble the three cost families into one table CSV (no mixing of units)."""
import csv, json, os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read_csv(name):
    with open(os.path.join(HERE, name)) as f:
        return list(csv.DictReader(f))


def main():
    man = json.load(open(os.path.join(HERE, "manifests", "input_manifest.json")))
    api = read_csv("results/api_usage_summary.csv")[0]
    loc = {r["operation"]: r for r in read_csv("results/local_maintenance_summary.csv")}
    ret = {r["repository"]: r for r in read_csv("results/retrieval_latency_summary.csv")}
    dec = {r["repository"]: r for r in read_csv("results/query_cost_decomposition.csv")}

    full, ref = ret["full"], ret["refined"]
    rows = [
        {"group": "Repository", "metric": "Indexed entries",
         "full": f"{int(full['entries']):,}", "refined": f"{int(ref['entries']):,}",
         "notes": f"entry reduction {100*(1-int(ref['entries'])/int(full['entries'])):.1f}%"},
        {"group": "Retrieval", "metric": "Index build (s)",
         "full": f"{float(full['index_build_s']):.4f}", "refined": f"{float(ref['index_build_s']):.4f}",
         "notes": "median of 3 builds, BM25Okapi construction only"},
        {"group": "Retrieval", "metric": "Hot query P50 (ms)",
         "full": f"{float(full['query_p50_ms']):.2f}", "refined": f"{float(ref['query_p50_ms']):.2f}",
         "notes": "55 queries x 5 repeats, P10 code path"},
        {"group": "Retrieval", "metric": "Hot query P95 (ms)",
         "full": f"{float(full['query_p95_ms']):.2f}", "refined": f"{float(ref['query_p95_ms']):.2f}",
         "notes": "55 queries x 5 repeats, P10 code path"},
        {"group": "Retrieval", "metric": "Query time P50 reduction",
         "full": "--", "refined": f"{100*(1-float(ref['query_p50_ms'])/float(full['query_p50_ms'])):.1f}%",
         "notes": "1 - refined/full; not an end-to-end latency claim"},
        {"group": "Local refinement", "metric": "BM25 matrix build (s)",
         "full": "--", "refined": f"{float(loc['bm25_similarity_matrix']['time_median_s']):.1f}",
         "notes": f"6000x6000 float64, median of {loc['bm25_similarity_matrix']['runs']} runs "
                  f"({loc['bm25_similarity_matrix']['time_min_s']}-{loc['bm25_similarity_matrix']['time_max_s']} s)"},
        {"group": "Local refinement", "metric": "Anchor grouping (s)",
         "full": "--", "refined": f"{float(loc['anchor_grouping']['time_median_s']):.2f}",
         "notes": f"tau_sim=40, median of {loc['anchor_grouping']['runs']} runs, 662 groups"},
        {"group": "LLM condensation", "metric": "Successful uncached calls",
         "full": "--", "refined": api["successful_uncached_calls"],
         "notes": f"historical log; {api['cache_hits']} cache hits excluded"},
        {"group": "LLM condensation", "metric": "Input / output tokens",
         "full": "--", "refined": f"{int(api['input_tokens']):,} / {int(api['output_tokens']):,}",
         "notes": "successful uncached requests only"},
        {"group": "LLM condensation", "metric": "API request P50 / P95 (s)",
         "full": "--", "refined": f"{api['latency_p50_s']} / {api['latency_p95_s']}",
         "notes": "per-request latency, not wall-clock"},
        {"group": "LLM condensation", "metric": "Logged estimated cost (USD)",
         "full": "--", "refined": f"{float(api['estimated_cost']):.4f}",
         "notes": "as recorded by the historical log; not an audited bill"},
    ]
    with open(os.path.join(HERE, "results", "backend_overhead_table.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["group", "metric", "full", "refined", "notes"])
        w.writeheader(); w.writerows(rows)
    for r in rows:
        print(f"{r['group']:<17}{r['metric']:<30}{r['full']:>10}{r['refined']:>16}   {r['notes']}")
    print(f"\nquery cost decomposition: full {dec['full']['score_share_percent']}% scoring, "
          f"refined {dec['refined']['score_share_percent']}% scoring")


if __name__ == "__main__":
    main()
