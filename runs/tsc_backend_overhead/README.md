# Backend management overhead

Local cost of producing a refined repository and serving queries from it, on MMLU High School
Geography at `tau_sim = 40`. **No LLM calls were made**: the API numbers are a re-analysis of the run log.

```bash
./scripts/run_all.sh        # inventory -> api summary -> matrix/grouping timing -> retrieval -> table
python3 scripts/plot_query_latency.py    # optional figure
```

| File | Contents |
|---|---|
| `manifests/input_manifest.json` | hashes, entry counts, query keys, hardware, package versions |
| `results/api_usage_summary.csv` | historical condensation requests (tokens, latency, logged cost) |
| `results/local_maintenance_summary.csv` | matrix build and anchor grouping timings |
| `results/retrieval_latency_summary.csv` | index build and hot-query P50/P95 per repository |
| `results/query_cost_decomposition.csv` | tokenisation vs scoring vs ranking |
| `results/backend_overhead_table.csv` | the paper table in CSV form |
| `latex/table_backend_overhead.tex` | single-column table, values copied from the CSV |
| `latex/ve_backend_overhead_results.tex` | V.E protocol + results paragraphs |
| `figures/query_latency_comparison.{pdf,png}` | optional §7.2 figure, P50/P95 on one axis |
| `latex/fig_query_latency.tex`, `latex/preview_ve_page.tex` | include file and the one-page layout mock |

Headline numbers: 6,000 → 942 entries; index build 0.0354 s → 0.0079 s; hot-query P50 22.67 ms → 3.60 ms
(−84.1 %) and P95 37.72 ms → 5.73 ms (−84.8 %); one-off maintenance 94.1 s (matrix, median of 6 runs) +
0.38 s (grouping); 275 uncached condensation requests, 186,279/12,864 tokens, per-request P50/P95
1.691/4.052 s, logged cost $0.0103.
