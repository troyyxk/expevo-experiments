#!/usr/bin/env bash
# Regenerate every artifact of the heterogeneous-coverage experiment from shipped data.
set -euo pipefail
cd "$(dirname "$0")/.."
PY=${PYTHON:-python3}
say() { printf "\n\033[1m== %s ==\033[0m\n" "$*"; }
say "audit inputs (no LLM)";            $PY scripts/audit_inputs.py | tail -2
say "partition + pools (no LLM)";       $PY scripts/build_hetero_pools.py | tail -3
say "retrieval + diagnostics (no LLM)"; $PY scripts/retrieve_hetero.py | tail -4
say "statistics (no LLM)";              $PY scripts/aggregate_hetero.py
say "figure + table";                   $PY scripts/plot_hetero.py --mode real | tail -1
                                        $PY scripts/export_hetero_table.py | tail -4
say "done"
