# Reproduction map — which script produces which paper artifact

Run `./run_all.sh` once; it regenerates everything below in about ten seconds from the shipped data.
`./verify.sh` then asserts that the numbers match the values quoted in the paper.

Legend: **in** = input data shipped in this package · **out** = regenerated file.

---

## Fig. 5 — experience-lifecycle data footprint (§V-C)

| Step | Command | In → Out |
|---|---|---|
| 1 | `cd p7/expevo_lifecycle && python -m src.metrics --config config/full100.yaml` | `runs/p7_full100/{episodes,experiences,refined}/*.jsonl` → `tables/lifecycle_footprint.csv`, `tables/refinement_metrics.csv`, `tables/totals.json` |
| 2 | `python -m src.plots --config config/full100.yaml --tau 60` | the tables above → `figures/fig_lifecycle_footprint.{pdf,png}` |
| 3 | `python -m src.plots_paper --config config/full100.yaml --tau 60` | same → `figures/fig_lifecycle_footprint_tau60_paper.pdf` (the one used in the paper, 250.7 × 122.3 pt) |

Expected values: raw **22.080 MB**, distilled **4.970 MB**, refined@60 **1.599 MB**, reduction **77.5 %**
then **67.8 %**; per subject storage reduction 69.6 / 63.1 / 74.9 / 63.1 %.

---

## Fig. 6 — multi-client upload simulation (§V-C)

| Step | Command | In → Out |
|---|---|---|
| 1 | `cd fig6_network_simulation && python src/extract_payloads.py` | `p7/.../runs/p7_full100/{episodes,experiences}` → `data/payload_pairs.csv` (24,000 rows) |
| 2 | `python src/tests_sim.py` | — → ten correctness checks, must print `0 failure(s)` |
| 3 | `python src/sim_uploads.py --seeds 30` | `data/payload_pairs.csv` → `results/per_run.csv`, `results/summary.csv`, `results/config.json` |
| 4 | `python src/plot_fig6.py` | `results/per_run.csv` → `images/fig_upload_completion_simulation.{pdf,png}` |
| 4b | `python src/plot_fig6.py --layout stacked --out images/fig_upload_completion_simulation_stacked` | single-column variant |

Expected values: P95 completion time at 10 → 100 clients rises **12.6 → 53.6 ms** for raw episodes and
**2.8 → 3.4 ms** for distilled experiences (ratio 4.44× → 15.9×); the P95 reduction rises **83.5 % →
98.6 %** as the offered load goes 0.30 → 0.95, against the 77.5 % payload-reduction baseline.

---

## Fig. 7 and Table II — backend refinement (§V-D)

All commands run in `p7/expevo_lifecycle/runs/p10_backend_refinement/`.

| Step | Command | In → Out |
|---|---|---|
| 1 | `python scripts/run_refinement.py` | `runs/p7_full100/{full_repositories,refined}` → `tables/refinement_resource_by_subject.csv`, `refinement_resource_totals.csv`, `refinement_run_manifest.csv`, `input_manifest.json` |
| 2 | `python scripts/aggregate_metrics.py` | `eval/predictions{,_extended}.jsonl` + step 1 → `tables/accuracy_by_question.csv` (1,100 rows), `accuracy_by_subject.csv`, `accuracy_by_question_set.csv`, `quality_resource_table2.csv` |
| 3 | `python scripts/bootstrap_ci.py` | step 2 → `tables/accuracy_bootstrap_ci.csv` |
| 4 | `python scripts/diagnose_tau40.py` | refined repositories → `tables/tau40_diagnosis.csv` (explains the τ=40 rebound) |
| 5 | `python scripts/export_table2.py` | `quality_resource_table2.csv` → `tables/table2_quality_resource.{tex,md}` |
| 6 | `python scripts/plot_fig5.py` | `refinement_resource_by_subject.csv` → `figures/fig_backend_refinement_quality_resource.{pdf,png}` |
| 7 | `python scripts/make_reports.py` | everything above → `reports/{validation_report,experiment_report}.md` |

Expected Table II: Full **75.68 %**, 4.970 MB, 24,000 entries; BM25 60 **74.41 %**, 1.599 MB, 8,332
entries (67.8 % / 65.3 % reduction); all paired Δ CIs include zero.

---

## V.C (TSC revision) — cross-client sharing experiment

Everything lives in `runs/tsc_collaboration/`.

| Step | Command (from `runs/tsc_collaboration/`) | In → Out |
|---|---|---|
| 0 | `./scripts/run_all_tsc.sh` | runs steps 1–5 below |
| 1 | `scripts/build_pools.py` | frozen corpus → 4 local pools, 3 matched pools, full pool, `config/request_assignment.json` |
| 2 | `scripts/validate_reuse.py` | pools → `retrieval/retrieval_diagnostics.csv`, `manifests/validate_reuse.json` |
| 3 | `scripts/aggregate_stats.py` | `predictions/predictions.jsonl` → `results/*.csv` (per-question, per-pool, paired differences, 5,000 bootstrap replicates) |
| 4 | `scripts/plot_collaboration.py --mode real` | those CSVs → `figures/fig_collaborative_sharing.{pdf,png}` |
| 5 | `scripts/export_table.py` | → `latex/{fig,table}_collaborative_sharing.tex`, `latex/vc_collaboration_results.tex` |

Expected: Local-only **80.36 %** [70.73, 88.37], Shared-matched **80.24 %** [71.39, 88.18],
Shared-full **78.18 %** [69.27, 86.55]; paired Δ = −0.12, −2.06, −2.18 pp, all CIs including zero.

Re-running the 2,200 answers (the only API phase) needs `EXPEVO_ENV=/path/to/.env` and
`scripts/evaluate_policies.py --concurrency 14`.

---

## File inventory you can diff against

After `./run_all.sh` the following are rewritten (all deterministic):

```
p7/expevo_lifecycle/runs/p7_full100/tables/*.csv
p7/expevo_lifecycle/runs/p7_full100/figures/*.pdf|png
p7/expevo_lifecycle/runs/p7_full100/experiment_report.md, validation_report.md
p7/expevo_lifecycle/runs/p7_full100/modeled_upload_exp/{tables,figures}/*
p7/expevo_lifecycle/runs/p10_backend_refinement/{tables,figures,reports}/*
fig6_network_simulation/{data,results,images}/*
p9/results/full_20261027_194400/{trial_summary,condition_summary,saving_summary}.csv
runs/tsc_collaboration/{results,figures,latex}/*
```
