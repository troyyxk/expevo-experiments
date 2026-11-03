# Revision log — V.C cross-client sharing experiment (TSC revision)

## What was added

A controlled three-policy comparison on **MMLU High School Geography**, reusing the frozen P7 corpus.
Nothing in the existing pipeline was modified; all new work lives under `runs/tsc_collaboration/`.

| Policy | Candidate entries | Source clients | Experiences per construction question |
|---|---:|---:|---:|
| Local-only | 1,500 | 1 | 25 |
| Shared-matched (3 seeds) | 1,500 | 4 | 25 |
| Shared-full | 6,000 | 4 | 100 |

## Data reuse and new compute

| Item | Status |
|---|---|
| Episodes / experiences / full repository | **reused** (no regeneration) |
| Local-only pools (4 × 1,500) | built from `client_id` provenance, no LLM |
| Shared-matched pools (3 × 1,500) | sampled with seeds 20261103/04/05, no LLM |
| Request assignment (55 → 4 clients, 14/14/14/13) | seed 20261106, fixed before evaluation |
| Shared-full predictions | **reused 550 historical answers** — all 55 questions reproduce the historical Top-5 ids and prompt hash exactly (`manifests/validate_reuse.json`) |
| New inference | **2,200 answers** (550 local + 3 × 550 matched), 0 failures, 7.0 min, $0.052 |

## Results (question-level, 55 questions, 10 responses each)

| Setting | Accuracy (%) | 95% CI |
|---|---:|---|
| Local-only | 80.36 | [70.73, 88.37] |
| Shared-matched | 80.24 | [71.39, 88.18] |
| Shared-full | 78.18 | [69.27, 86.55] |

| Comparison | Δ (pp) | 95% CI |
|---|---:|---|
| Matched − Local | −0.12 | [−3.03, +2.73] |
| Full − Matched | −2.06 | [−6.18, +2.00] |
| Full − Local | −2.18 | [−6.55, +2.18] |

Per-seed matched accuracy: 79.27 / 82.00 / 79.45.

Every interval includes zero. The honest reading is *no detectable effect*, in either direction, of
mixing sources at matched entry count or of expanding to the full repository.

## Method notes

- Statistical unit is the question (55), never the 550 responses or the 3 pools; the bootstrap resamples
  question keys and recomputes all policies on the same resample.
- The matched summary averages the three pools **within question** first, then across questions.
- Shared-full reuse was accepted only after a 55/55 match on retrieved ids and prompt hashes; no
  historical prediction was altered.
- Tokenizer, BM25 parameters, Top-5, prompt and decoding are byte-identical to the P10 evaluation.

## Known limitations

- One topic, 55 questions: the intervals are wide (±9 pp marginal), so only large effects would be
  detectable.
- The shared pools are synthetic entry-count-matched samples, not a deployed sharing policy.
- The experiment says nothing about latency, uplink cost or heterogeneous client expertise.
