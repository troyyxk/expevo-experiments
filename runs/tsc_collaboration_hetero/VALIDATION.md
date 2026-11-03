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
