#!/usr/bin/env bash
# Regenerate every table and figure in this release from the shipped data.
# No network, no LLM calls, no root. Runtimes: ~10 s total (Fig.6 simulation is ~7 s).
set -euo pipefail
cd "$(dirname "$0")"
PY=${PYTHON:-python3}
say() { printf "\n\033[1m== %s ==\033[0m\n" "$*"; }

say "V-C / Fig. 5  lifecycle footprint (bytes -> tables + figure)"
cd p7/expevo_lifecycle
$PY -m src.metrics     --config config/full100.yaml >/dev/null
$PY -m src.plots       --config config/full100.yaml --tau 60
$PY -m src.plots_paper --config config/full100.yaml --tau 60
$PY -m src.validate    --config config/full100.yaml | tail -1
cd ../..

say "V-C / modeled upload time (analytical D/R, kept as the baseline)"
cd p7/expevo_lifecycle
$PY scripts/p9_modeled_upload.py --run-dir runs/p7_full100 --rates 1 5 10 20 50 | tail -1
cd ../..

say "V-D / Fig. 7 + Table II  (backend refinement: resources, accuracy, bootstrap)"
cd p7/expevo_lifecycle/runs/p10_backend_refinement
$PY scripts/run_refinement.py | tail -8
$PY scripts/aggregate_metrics.py | tail -7
$PY scripts/bootstrap_ci.py | tail -6
$PY scripts/diagnose_tau40.py >/dev/null
$PY scripts/export_table2.py >/dev/null
$PY scripts/plot_fig5.py
$PY scripts/make_reports.py
cd -

say "V-C / Fig. 6  (multi-client queueing simulation)"
cd fig6_network_simulation
$PY src/extract_payloads.py
$PY src/tests_sim.py | tail -2
$PY src/sim_uploads.py --seeds 30 >/dev/null
$PY src/plot_fig6.py
$PY src/plot_fig6.py --layout stacked --out images/fig_upload_completion_simulation_stacked >/dev/null
cd ..

say "P9 / emulated upload (analysis + figure from the shipped run)"
cd p9
$PY analyze.py --dir results/full_20261027_194400 | tail -6
$PY plot_p9.py --dir results/full_20261027_194400 | tail -3
cd ..

say "TSC / figure + table  (cross-client sharing)"
cd runs/tsc_collaboration
./scripts/run_all_tsc.sh | tail -4
cd ../..

say "done — regenerated files are listed in REPRODUCE.md"
