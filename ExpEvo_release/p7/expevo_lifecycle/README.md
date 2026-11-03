# ExpEvo P7 — Experience Lifecycle Data Footprint (rebuilt from public MMLU)

Re-generates, from public data, the three-stage data footprint used by P7:
Raw interaction episodes → distilled experiences → refined repository.

## Quick start

```bash
cp .env.example .env          # then fill LLM_BASE_URL / LLM_API_KEY / LLM_MODEL
pip install -r requirements.txt

# 1) freeze the MMLU construction/heldout split (no LLM calls)
python -m src.prepare_mmlu --config config/smoke.yaml

# 2) stage-by-stage
python -m src.run_interactions --config config/smoke.yaml
python -m src.distill          --config config/smoke.yaml
python -m src.route_and_store  --config config/smoke.yaml
python -m src.refine           --config config/smoke.yaml
python -m src.metrics          --config config/smoke.yaml
python -m src.plots            --config config/smoke.yaml
python -m src.validate         --config config/smoke.yaml
python -m src.report           --config config/smoke.yaml

# or everything at once (full run needs an explicit flag)
python -m src.run_all --config config/full.yaml --mode full
```

`PYTHONPATH=.` is required if you do not `pip install -e .` — the package uses
relative imports (`src.common`, ...).

## Scale (config/full.yaml)

| item | value |
|---|---|
| subjects | international_law, college_medicine, college_biology, high_school_geography |
| sampled per subject | 75 (80% construction = 60, 20% heldout = 15) |
| repeats | 10 interactions per construction question |
| episodes | 4 × 60 × 10 = 2,400 |
| thresholds | BM25 100 / 80 / 60 / 40, all from one frozen full snapshot |

## Outputs (runs/<run_id>/)

```
manifest.json  manifest_*.json  experiment_report.md  validation_report.md
dataset/  heldout/  episodes/  experiences/  full_repositories/
bm25/{score_matrix_*.npy, groups_*.json, score_diagnostics.csv}
refined/{subject}/bm25_{100,80,60,40}.jsonl
tables/{lifecycle_footprint,refinement_metrics,upload_latency,bm25_score_diagnostics,api_usage}.csv
figures/fig_lifecycle_footprint.{pdf,png}
figures/fig_modeled_upload_latency.{pdf,png}
figures/fig_refinement_storage_proxy.{pdf,png}
```

## Measurement rules implemented

* one canonical serializer for all three stages (`serialize_item`), IDs/logs excluded;
* `MB = bytes / 1e6`, bits `= 8 × bytes`;
* BM25 = `rank-bm25` `BM25Okapi(k1=1.5, b=0.75)`, tokenizer `[a-z0-9]+`, directed matrix,
  **raw scores, no rescaling**;
* anchor grouping covers every experience exactly once; each threshold restarts from
  the frozen full snapshot; singleton groups stay unchanged;
* context-overflow groups are **not** merged and are flagged `context_overflow_unmerged`;
* every reported number is recomputed from the persisted records.
