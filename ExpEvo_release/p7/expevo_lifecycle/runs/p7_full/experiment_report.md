# Experiment report — p7_full

## 1. Setup

- model_id: `meta-llama/llama-3.1-8b-instruct`
- dataset: `cais/mmlu` split `test` revision `c30699e8356da336a370243923dbaf21066bb9fe`
- seed: `20261026`; sampled per subject: 75 (construction 60, heldout rest); repeats: 10
- thresholds: [100, 80, 60, 40]; BM25 k1=1.5, b=0.75

## 2. Lifecycle footprint (canonical serialization)

| subject | questions | raw eps | distilled | full repo | refined@100 | raw MB | dist MB | refined MB | upload ↓ | storage ↓ |
|---|---|---|---|---|---|---|---|---|---|---|
| international_law | 60 | 600 | 600 | 600 | 592 | 0.6180 | 0.1389 | 0.1363 | 77.52% | 1.88% |
| college_medicine | 60 | 600 | 600 | 600 | 583 | 0.6176 | 0.1136 | 0.1097 | 81.61% | 3.42% |
| college_biology | 60 | 600 | 600 | 600 | 587 | 0.5400 | 0.1202 | 0.1166 | 77.74% | 3.01% |
| high_school_geography | 60 | 600 | 600 | 600 | 598 | 0.4247 | 0.1116 | 0.1111 | 73.72% | 0.51% |
| **total** | | 2400 | 2400 | | | 2.2002 | 0.4843 | 0.4736 | 77.99% | 2.21% |

## 3. Refinement sweep

| subject | τ | refined count | ratio | storage ↓ | items ↓ | overflow |
|---|---|---|---|---|---|---|
| college_biology | 100 | 587 | 0.9783 | 3.01% | 2.17% | 0 |
| college_biology | 80 | 530 | 0.8833 | 14.54% | 11.67% | 0 |
| college_biology | 60 | 383 | 0.6383 | 39.16% | 36.17% | 0 |
| college_biology | 40 | 203 | 0.3383 | 65.08% | 66.17% | 0 |
| college_medicine | 100 | 583 | 0.9717 | 3.42% | 2.83% | 0 |
| college_medicine | 80 | 532 | 0.8867 | 13.79% | 11.33% | 0 |
| college_medicine | 60 | 398 | 0.6633 | 35.7% | 33.67% | 0 |
| college_medicine | 40 | 301 | 0.5017 | 46.79% | 49.83% | 156 |
| high_school_geography | 100 | 598 | 0.9967 | 0.51% | 0.33% | 0 |
| high_school_geography | 80 | 574 | 0.9567 | 6.31% | 4.33% | 0 |
| high_school_geography | 60 | 468 | 0.78 | 26.02% | 22.0% | 0 |
| high_school_geography | 40 | 235 | 0.3917 | 59.92% | 60.83% | 0 |
| international_law | 100 | 592 | 0.9867 | 1.88% | 1.33% | 0 |
| international_law | 80 | 526 | 0.8767 | 13.53% | 12.33% | 0 |
| international_law | 60 | 327 | 0.545 | 45.81% | 45.5% | 0 |
| international_law | 40 | 143 | 0.2383 | 70.17% | 76.17% | 0 |

## 4. BM25 score diagnostics (raw scale, no rescaling)

| subject | n | self median | off p50 | off p90 | off p99 | off max | frac≥40 | frac≥100 |
|---|---|---|---|---|---|---|---|---|
| international_law | 600 | 79.6 | 8.29 | 18.29 | 41.73 | 113.3 | 1.088% | 0.004% |
| college_medicine | 600 | 73.5 | 4.29 | 12.37 | 38.71 | 132.2 | 0.953% | 0.011% |
| college_biology | 600 | 74.0 | 3.66 | 11.66 | 34.44 | 125.2 | 0.846% | 0.009% |
| high_school_geography | 600 | 64.4 | 3.41 | 10.23 | 31.82 | 100.5 | 0.652% | 0.001% |

## 5. Modeled upload time (D/R, not measured latency)

| subject | 1 Mbps | 5 Mbps | 10 Mbps | 20 Mbps | 50 Mbps |
|---|---|---|---|---|---|
| college_biology | 1.603 ms | 0.321 ms | 0.160 ms | 0.080 ms | 0.032 ms |
| college_medicine | 1.514 ms | 0.303 ms | 0.151 ms | 0.076 ms | 0.030 ms |
| high_school_geography | 1.488 ms | 0.298 ms | 0.149 ms | 0.074 ms | 0.030 ms |
| international_law | 1.852 ms | 0.370 ms | 0.185 ms | 0.093 ms | 0.037 ms |

## 6. API usage

| stage | billed calls | cache hits | prompt tok | completion tok | est. cost (USD) |
|---|---|---|---|---|---|
| distill | 2256 | 144 | 754115 | 71129 | 0.043396 |
| interactions | 2256 | 144 | 370929 | 203190 | 0.034802 |
| refine | 720 | 25 | 196177 | 33702 | 0.012505 |

## 7. Notes and limitations

- The model served by the provider is `meta-llama/llama-3.1-8b-instruct`; the original HGF checkpoint `meta-llama/Meta-Llama-3-8B-Instruct` is no longer served, so the Llama-3.1-8B-Instruct substitute is used consistently for inference, distillation and condensation.
- BM25 absolute scores depend on corpus size; at this scale τ=100/80 merge very little, which is reported as measured rather than tuned away.
- Serialized bytes are an application-layer payload model: no TCP/TLS/header overhead.
- 156 experiences stayed unmerged because their group exceeded the condensation context budget (`context_overflow_unmerged`); the affected reductions are therefore lower bounds, not optimised results.
- Resource experiment only: no heldout accuracy is reported (`not_evaluated`).

