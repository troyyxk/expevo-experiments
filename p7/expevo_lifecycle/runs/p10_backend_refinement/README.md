# P10 — Backend refinement (Figure 5 + Table 2)

Continuation of the P7 run `p7_full100`. The 16 refined repositories already produced by P7 are
**reused**, not regenerated; the only new compute is the held-out accuracy evaluation.

## Artifacts

| Path | Content |
|---|---|
| `figures/fig_backend_refinement_quality_resource.pdf/.png` | Figure 5: (a) repository storage, (b) normalized indexed entries |
| `tables/table2_quality_resource.tex/.md/.csv` | Table 2: accuracy vs storage vs entries |
| `tables/refinement_resource_by_subject.csv` | 20 rows (4 subjects x 5 settings) with hashes, counts, bytes |
| `tables/accuracy_by_question.csv` | 1,100 rows (55 questions x 4 subjects / 5 settings) |
| `tables/accuracy_by_subject.csv` | 20 rows (55 questions, 550 samples each) |
| `tables/accuracy_by_question_set.csv` | original 15 vs extended 40 breakdown |
| `eval/heldout_extended.jsonl` | frozen extended set, 160 questions + manifest hash |
| `tables/accuracy_bootstrap_ci.csv` | 95% CI resampling question IDs |
| `eval/predictions.jsonl` | 3,000 sampled responses with retrieval provenance |
| `eval/retrieval_logs.jsonl` | Top-5 retrieved IDs and scores per question x setting |
| `reports/validation_report.md`, `reports/experiment_report.md` | checks and full results |
| `input_manifest.json`, `run_config.json` | provenance and protocol |

## Reproduce

```bash
cd runs/p10_backend_refinement

# 1. validate the P7 repositories and rebuild the resource matrix (no API)
python scripts/run_refinement.py

# 2a. freeze the extended held-out set (40 unused questions per subject, verified disjoint)
python scripts/build_extended_heldout.py

# 2b. evaluate the original 15 held-out questions: 60 x 5 x 10 = 3,000 calls (~11 min, ~$0.09)
python scripts/evaluate_heldout.py --samples 10 --top-k 5 --temperature 0.7 --max-tokens 320 --concurrency 12

# 2c. evaluate the extended 40 questions: 160 x 5 x 10 = 8,000 calls (~20 min, ~$0.22)
python scripts/evaluate_heldout.py --question-set extended --samples 10 --top-k 5 \
    --temperature 0.7 --max-tokens 320 --concurrency 14

# 3. aggregate, uncertainty, table, figure, reports
python scripts/reparse_predictions.py     # documented repair of answer-format misses (logged)
python scripts/aggregate_metrics.py
python scripts/bootstrap_ci.py            # paired bootstrap over question IDs
python scripts/diagnose_tau40.py          # why storage rebounds at the lowest threshold
python scripts/export_table2.py
python scripts/plot_fig5.py
python scripts/make_reports.py
```

All commands above were executed in this run. `evaluate_heldout.py` is resumable: re-running skips
samples already present in `eval/predictions.jsonl`.

## Notes

- Retrieval Top-K = 5 is a **newly fixed protocol** adopted for this evaluation (P7 had no retrieval
  evaluation); it is identical for all five settings and was not tuned on the held-out labels.
- The BM25 similarity threshold (100/80/60/40) is a grouping threshold and is unrelated to the
  Top-K retrieval cutoff.
- `G_ret` = indexed entries, a repository-size proxy, not measured BM25 latency.
- Backend refinement happens after upload and does not reduce the uplink payload measured in P7/P9.
