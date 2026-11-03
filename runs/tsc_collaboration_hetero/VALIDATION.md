# Validation — heterogeneous coverage experiment

## Input audit (`manifests/input_audit.json`)

| Check | Result |
|---|---|
| episodes / experiences / full repository | 6,000 / 6,000 / 6,000 |
| unique experience ids | 6,000 |
| clients | 0:1,500 · 1:1,500 · 2:1,500 · 3:1,500 |
| per (client, construction question) | exactly 25, 240 cells |
| experiences without an episode | 0 |
| request assignment inherited | 55 questions, 15 original + 40 extended, 0 overlap with construction, clients 14/14/14/13 |

## Pool construction (`manifests/pool_validation.json`)

| Check | Result |
|---|---|
| partition covers all 60 questions exactly once | PASS (15/15/15/15, seed 20261108) |
| each `Local_c` | 375 entries, 15 questions × 25 |
| local pools are disjoint in questions and in ids | PASS |
| `Shared-full-hetero` | 1,500 entries, 60 questions × 25, 375 per client |
| each matched pool | 375 entries, 60 questions × (6 or 7), ≤94 per client, subset of the union |
| matched pools rebuilt from seeds | 20261109 / 20261110 / 20261111 |

## Retrieval (`retrieval/retrieval_diagnostics.csv`)

| Policy | mean retrieved tokens | Top-5 from other clients | distinct source questions |
|---|---:|---:|---:|
| Local-only | 139.1 | 0.00 | 2.25 |
| Shared-matched | 135.8 | 3.59 | 2.88 |
| Shared-full-hetero | 133.8 | 3.65 | 2.38 |

Top-5 overlap between the matched pools and the full union: 21 %. The coverage manipulation therefore
changes what is retrieved, not just the label.

## Evaluation

| Check | Result |
|---|---|
| answered samples | 2,750 (2,745 new + 5 smoke), 0 API errors |
| samples per (policy, pool, question) | exactly 10 |
| model / decoding | `llama-3.1-8b-instruct`, T=0.7, max 320 tokens, identical across policies |
| prompt | built by the P10 `build_prompt` / `SYSTEM`; prompt hash stored per sample |
| new calls | 2,750; 10.8 min; $0.063 |

## Statistics

- Unit is the question (55), never the 550 responses or the three pools.
- Bootstrap resamples question keys and recomputes all policies on the same resample (paired).
- Matched summary averages the three pools within question, then across questions.
- Seed-level accuracies are reported alongside so the pool-to-pool spread is visible.

## Control baselines (added after the null result)

The sharing experiments show no effect. To check whether the retrieved experiences matter at all on this
benchmark, two controls were run on the **same 55 questions, same model, same decoding, 10 samples each**
(`predictions/controls.jsonl`, `results/control_baselines.csv`):

- **plain** — the identical prompt with an empty retrieved list (`(none)`), 550 answers;
- **placebo** — Top-5 retrieved from the *International Law* repositories, i.e. on-topic text that is
  unrelated to High School Geography, 550 answers.

| Condition | Accuracy (%) | 95% CI | Δ vs plain (pp) | 95% CI |
|---|---:|---|---:|---|
| plain (no context) | 80.55 | [71.45, 88.36] | — | — |
| placebo (unrelated Top-5) | 83.64 | [74.72, 91.28] | +3.09 | [−1.09, +7.82] |
| Local-only (375) | 81.45 | [72.36, 89.64] | +0.91 | [−3.45, +4.55] |
| Shared-matched (375, all 60 Q) | 80.48 | [71.64, 88.55] | −0.06 | [−4.79, +4.85] |
| Shared-full-hetero (1,500) | 80.73 | [71.82, 88.91] | +0.18 | [−4.36, +4.91] |

Per-question accuracy is identical between plain and Local-only on 39 of 55 questions. **No retrieved
context — not even topically unrelated text — changes accuracy measurably.** The 55-question evaluation
is therefore dominated by the model's prior on this subject, which is why both sharing designs return
null results.

## Cross-subject check: does the repository help at all?

Same 55 questions per subject, same prompt scaffolding, 10 samples. `plain` = empty retrieved list;
`full-repo` = the P10 evaluation against the full 6,000-experience repository.

| Subject | plain (%) | full repository (%) | Δ (repo − plain) | 95% CI |
|---|---:|---:|---:|---|
| High School Geography | 80.55 | 78.18 | −2.36 | [−8.0, +3.1] |
| College Biology | 81.09 | 80.73 | −0.36 | [−3.6, +3.3] |
| College Medicine | 69.82 | 70.00 | +0.18 | [−6.7, +7.3] |
| International Law | 77.27 | 73.82 | −3.45 | [−7.5, +0.4] |

Data: `predictions/plain_all_subjects.jsonl`, `predictions/controls.jsonl`,
`results/plain_vs_fullrepo_by_subject.csv`.

**Reading.** The model answers these unseen MMLU questions at 70–81 % with no retrieved context at all,
and attaching the full experience repository changes the accuracy by between −3.5 and +0.2 percentage
points. This is not specific to one subject. On unseen questions the experience repository does not
measurably help; the null results of both sharing experiments are a consequence of that, not of the
sharing design.

## Why the epoch curve rose while these runs did not

The epoch experiment asks the **same 200 questions every epoch** and uses a prompt that forces the final
line to be `#### <option text>`, asking the model to copy the chosen option verbatim. The runs in this
directory use a JSON-letter answer instead. Re-asking 55 construction questions (for which the
repository holds experiences distilled from the same question) under both contracts:

| Prompt contract | no context | with same-question Top-5 | Δ |
|---|---:|---:|---:|
| JSON letter (P10) | 77.45 % | 78.55 % | **+1.09 pp** |
| `#### <option text>` (epoch) | 55.64 % | 71.09 % | **+15.45 pp** |

Data: `predictions/epoch_prompt_control.jsonl`, `results/prompt_contract_control.csv`.

The epoch contract drops the model to 55.6 % when no context is provided, and the retrieved experiences —
which are paraphrases of the correct option — lift it back by 15.5 points. The epoch curve therefore
measures **recovery of the expected answer string through retrieved text**, not knowledge acquisition.
Under the JSON-letter contract the model already answers at 77–84 % without any context, and the same
experiences add about one point. This is consistent with the null results of both sharing experiments.

## The same sharing comparison under the epoch prompt contract

The heterogeneous comparison was repeated with the old answer contract (`#### <option text>`) to rule
out the possibility that the JSON contract hides an effect. 3,300 answers, 0 failures.

| Contract | Condition | Accuracy (%) | Δ vs plain (pp) | 95% CI |
|---|---|---:|---:|---|
| `####` | plain | 52.36 | — | — |
| `####` | Local-only | 51.09 | −1.27 | [−9.45, +6.91] |
| `####` | Shared-matched | 52.06 | −0.30 | [−7.82, +7.45] |
| `####` | Shared-full-hetero | 49.45 | −2.91 | [−10.36, +4.36] |
| JSON | plain | 80.55 | — | — |
| JSON | Local-only | 81.45 | +0.91 | [−3.27, +4.55] |
| JSON | Shared-matched | 80.48 | −0.06 | [−4.91, +4.91] |
| JSON | Shared-full-hetero | 80.73 | +0.18 | [−4.55, +4.91] |

Data: `predictions/hetero_epoch_contract.jsonl`, `results/contract_comparison.csv`.

The contract lowers the absolute level by about 28 points but does not change the conclusion: sharing
experience from *other* questions does not raise accuracy. Format compliance under the `####` contract is
96–99 % (unparsed answers are counted as incorrect, as in every other run).

The only configuration where a large gain appears is when the retrieved experiences come from **the same
question** (construction questions, +15.45 pp). That is answer recall, not transfer.
