#!/usr/bin/env bash
# Regenerate every artifact of the cross-client sharing experiment from the shipped data.
# Phases 1-3 and 5-6 need no API; phase 4 (the 2,200 answers) is already shipped in predictions/.
set -euo pipefail
cd "$(dirname "$0")/.."
PY=${PYTHON:-python3}
say() { printf "\n\033[1m== %s ==\033[0m\n" "$*"; }

say "pools + request assignment (no LLM)"
$PY scripts/build_pools.py | tail -3

say "retrieval per pool + Shared-full reuse audit (no LLM)"
$PY scripts/validate_reuse.py | tail -2

say "statistics: per-question, per-pool, paired bootstrap (no LLM)"
$PY scripts/aggregate_stats.py

say "figure + table + LaTeX"
$PY scripts/plot_collaboration.py --mode real --out figures/fig_collaborative_sharing | tail -1
$PY scripts/export_table.py | tail -4
echo "  latex/fig_collaborative_sharing.tex, table_collaborative_sharing.tex, vc_collaboration_results.tex"

say "done"
