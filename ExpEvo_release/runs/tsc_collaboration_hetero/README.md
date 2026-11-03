# Heterogeneous client coverage — cross-client experience reuse

Retrospective experiment on MMLU **High School Geography** that asks whether sharing experiences helps
when the four clients cover **complementary** parts of the construction space, rather than the same
questions. It complements `../tsc_collaboration/` (matched coverage) and answers a different question.

## Design (fixed before any evaluation)

| Step | Rule |
|---|---|
| Partition | the 60 construction questions are shuffled with seed **20261108** and split into four disjoint sets `Q_0 … Q_3` of 15 |
| Client pool | client `c` keeps only **its own** 25 experiences on the questions in `Q_c` → `Local_c` = **375** |
| Shared-full-hetero | union of the four local pools → **1,500**, covering all 60 questions, 25 each |
| Shared-matched-hetero | **375** entries from the union covering all 60 questions: 6 per question + 15 extra (one per question, owners 4/4/4/3), seeds **20261109/10/11** |
| Evaluation | the same 55 unseen questions (15 original + 40 extended), the same fixed request→client assignment as the matched-coverage experiment, 10 responses per question, BM25 Top-5, identical model/prompt/decoding |
| Statistics | question-level paired bootstrap, 5,000 replicates, seed 20261112; matched summary averages the three pools within question |

No parameter was tuned after seeing accuracy, and no alternative partition was kept.

## Results

| Setting | Entries | Source clients | Construction Q. | Accuracy (%) | 95% CI |
|---|---:|---:|---:|---:|---|
| Local-only | 375 | 1 | 15 | **81.45** | [72.36, 89.82] |
| Shared-matched | 375 | 4 | 60 | **80.48** | [71.76, 88.43] |
| Shared-full-hetero | 1,500 | 4 | 60 | **80.73** | [71.82, 88.73] |

| Comparison | Δ (pp) | 95% CI |
|---|---:|---|
| Matched − Local | −0.97 | [−4.06, +2.12] |
| Full − Matched | +0.24 | [−2.73, +3.09] |
| Full − Local | −0.73 | [−3.82, +2.36] |

Per-seed matched accuracy: 80.55 / 78.73 / 82.18. Every interval includes zero.

**Interpretation.** Complementary coverage is real — in the matched pools 3.6 of the five retrieved
experiences come from other clients, and their Top-5 ids overlap only 21 % with the full union — yet
accuracy does not move. Pool-to-pool spread (3.5 pp) exceeds every between-policy difference. The
honest statement is that sharing reduces communication and storage cost; it does not produce a
measurable accuracy benefit in this frozen, single-topic, 55-question setting.

## Files

```
runs/tsc_collaboration_hetero/
├── scripts/            audit_inputs, build_hetero_pools, retrieve_hetero, evaluate_hetero,
│                       aggregate_hetero, plot_hetero, export_hetero_table, run_all_hetero.sh
├── config/question_partition.json          the frozen 15/15/15/15 partition
├── manifests/          four local pools, three matched pools, the union, pool_validation.json,
│                       input_audit.json
├── retrieval/retrieval_diagnostics.csv     8 pools x 55 questions with source-client provenance
├── predictions/predictions.jsonl           2,750 answered samples (2,745 new + 5 smoke)
├── results/            accuracy_by_question, accuracy_by_pool, paired_differences,
│                       bootstrap_replicates, table_hetero.{csv,md}
├── figures/fig_hetero_sharing.{pdf,png}    495 x 178 pt
└── latex/              fig_hetero_sharing.tex, table_hetero.tex, vc_hetero_results.tex
```

## Reproduce

```bash
./scripts/run_all_hetero.sh        # audit -> pools -> retrieval -> stats -> figure -> table, no API
```

Re-running the answers needs the API (2,750 calls, ~11 min, ~$0.06):

```bash
EXPEVO_ENV=/path/to/.env python3 scripts/evaluate_hetero.py --concurrency 14
```

## Controls: does the retrieved experience matter at all?

| Condition | Accuracy (%) | 95% CI | Δ vs plain |
|---|---:|---|---:|
| plain, no retrieved context | 80.55 | [71.45, 88.36] | — |
| placebo, Top-5 from International Law | 83.64 | [74.72, 91.28] | +3.09 [−1.09, +7.82] |
| Local-only | 81.45 | [72.36, 89.64] | +0.91 [−3.45, +4.55] |
| Shared-matched | 80.48 | [71.64, 88.55] | −0.06 [−4.79, +4.85] |
| Shared-full-hetero | 80.73 | [71.82, 88.91] | +0.18 [−4.36, +4.91] |

The model already answers these 55 unseen questions at 80.6 % **without any experience**, and unrelated
retrieved text does not hurt. Per-question answers are identical to Local-only on 39/55 questions. The
null sharing results therefore reflect a benchmark whose accuracy is driven by the model's prior, not by
the experience repository.

## Cross-subject check (same 55 questions, 10 samples)

| Subject | no context (%) | full 6k repository (%) | Δ |
|---|---:|---:|---:|
| High School Geography | 80.55 | 78.18 | −2.36 |
| College Biology | 81.09 | 80.73 | −0.36 |
| College Medicine | 69.82 | 70.00 | +0.18 |
| International Law | 77.27 | 73.82 | −3.45 |

Every subject is answered at 70–81 % without any experience, and the repository moves accuracy by
−3.5…+0.2 pp. The experience corpus does not measurably help on unseen MMLU questions.

## Limits that must be stated in the paper

- The heterogeneous exposure is **constructed retrospectively**; the original corpus had every client
  seeing the same 60 construction questions. This is not a field trace of organically partitioned
  clients.
- One topic, 55 questions, intervals of about ±9 pp: only large effects would be detectable.
- Matched and local pools are equal in entry count but differ in coverage, which is the treatment;
  they are not matched on total bytes, text quality or global storage.
