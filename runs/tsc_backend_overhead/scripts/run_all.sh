#!/usr/bin/env bash
# Rebuild every artifact of the backend-overhead experiment. No LLM calls.
set -euo pipefail
cd "$(dirname "$0")/.."
PY=${PYTHON:-python3}
say() { printf "\n\033[1m== %s ==\033[0m\n" "$*"; }
say "Phase A  inventory + query set (no LLM)";   $PY scripts/inventory.py | tail -4
say "Phase B  historical API condensation";      $PY scripts/summarize_api_usage.py
say "Phase C  matrix build + grouping timing";   $PY scripts/benchmark_refinement_local.py
say "Phase D  index build + query latency";      $PY scripts/benchmark_retrieval.py
say "Phase D2 query cost decomposition";         $PY scripts/decompose_query_cost.py
say "Phase E  table";                            $PY scripts/aggregate_results.py | tail -3
                                                 $PY scripts/make_overhead_table.py >/dev/null
echo "  latex/table_backend_overhead.tex"
say "done"
