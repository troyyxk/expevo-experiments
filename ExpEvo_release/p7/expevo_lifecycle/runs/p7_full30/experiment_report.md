# Experiment report — p7_full30

## 1. Setup

- model_id: `meta-llama/llama-3.1-8b-instruct`
- dataset: `cais/mmlu` split `test` revision `c30699e8356da336a370243923dbaf21066bb9fe`
- seed: `20261026`; sampled per subject: 75 (construction 60, heldout rest); repeats: 30
- thresholds: [100, 80, 60, 40]; BM25 k1=1.5, b=0.75

## 2. Lifecycle footprint (canonical serialization)

| subject | questions | raw eps | distilled | full repo | refined@100 | raw MB | dist MB | refined MB | upload ↓ | storage ↓ |
|---|---|---|---|---|---|---|---|---|---|---|
| international_law | 60 | 1800 | 1800 | 1800 | 1699 | 1.8708 | 0.4126 | 0.3869 | 77.94% | 6.24% |
| college_medicine | 60 | 1800 | 1800 | 1800 | 1661 | 1.8347 | 0.3431 | 0.3092 | 81.3% | 9.86% |
| college_biology | 60 | 1800 | 1800 | 1800 | 1669 | 1.6389 | 0.3631 | 0.3288 | 77.84% | 9.45% |
| high_school_geography | 60 | 1800 | 1800 | 1800 | 1781 | 1.2733 | 0.3405 | 0.3352 | 73.26% | 1.54% |
| **total** | | 7200 | 7200 | | | 6.6177 | 1.4593 | 1.3602 | 77.95% | 6.79% |

## 3. Refinement sweep

| subject | τ | refined count | ratio | storage ↓ | items ↓ | overflow |
|---|---|---|---|---|---|---|
| college_biology | 100 | 1669 | 0.9272 | 9.45% | 7.28% | 0 |
| college_biology | 80 | 1346 | 0.7478 | 30.06% | 25.22% | 0 |
| college_biology | 60 | 776 | 0.4311 | 60.5% | 56.89% | 0 |
| college_biology | 40 | 341 | 0.1894 | 80.7% | 81.06% | 0 |
| college_medicine | 100 | 1661 | 0.9228 | 9.86% | 7.72% | 0 |
| college_medicine | 80 | 1479 | 0.8217 | 21.35% | 17.83% | 157 |
| college_medicine | 60 | 1134 | 0.63 | 40.02% | 37.0% | 470 |
| college_medicine | 40 | 800 | 0.4444 | 53.2% | 55.56% | 574 |
| high_school_geography | 100 | 1781 | 0.9894 | 1.54% | 1.06% | 0 |
| high_school_geography | 80 | 1644 | 0.9133 | 11.27% | 8.67% | 0 |
| high_school_geography | 60 | 1088 | 0.6044 | 43.32% | 39.56% | 0 |
| high_school_geography | 40 | 382 | 0.2122 | 77.98% | 78.78% | 0 |
| international_law | 100 | 1699 | 0.9439 | 6.24% | 5.61% | 0 |
| international_law | 80 | 1309 | 0.7272 | 29.08% | 27.28% | 0 |
| international_law | 60 | 670 | 0.3722 | 64.55% | 62.78% | 0 |
| international_law | 40 | 189 | 0.105 | 85.86% | 89.5% | 0 |

## 4. BM25 score diagnostics (raw scale, no rescaling)

| subject | n | self median | off p50 | off p90 | off p99 | off max | frac≥40 | frac≥100 |
|---|---|---|---|---|---|---|---|---|
| international_law | 1800 | 80.9 | 8.96 | 19.95 | 44.75 | 140.2 | 1.270% | 0.010% |
| college_medicine | 1800 | 74.9 | 4.02 | 12.83 | 42.32 | 317.2 | 1.130% | 0.015% |
| college_biology | 1800 | 76.2 | 3.97 | 12.81 | 38.25 | 133.1 | 0.940% | 0.018% |
| high_school_geography | 1800 | 67.8 | 4.04 | 11.46 | 34.95 | 113.4 | 0.768% | 0.002% |

### 2b. Exploratory variant: BM25 τ = 60 (not the official setting)

| subject | full count | τ=60 count | ratio | storage ↓ |
|---|---|---|---|---|
| college_biology | 1800 | 776 | 0.4311 | 60.5% |
| college_medicine | 1800 | 1134 | 0.63 | 40.02% |
| high_school_geography | 1800 | 1088 | 0.6044 | 43.32% |
| international_law | 1800 | 670 | 0.3722 | 64.55% |

The official main figure (`fig_lifecycle_footprint`) uses τ = 100. The τ = 60 bars are reported as an exploratory alternative (`fig_lifecycle_footprint_tau60`) and must not replace the formal 100/80/60/40 sweep.

## 5. Modeled upload time (D/R, not measured latency)

| subject | 1 Mbps | 5 Mbps | 10 Mbps | 20 Mbps | 50 Mbps |
|---|---|---|---|---|---|
| college_biology | 1.614 ms | 0.323 ms | 0.161 ms | 0.081 ms | 0.032 ms |
| college_medicine | 1.525 ms | 0.305 ms | 0.152 ms | 0.076 ms | 0.030 ms |
| high_school_geography | 1.513 ms | 0.303 ms | 0.151 ms | 0.076 ms | 0.030 ms |
| international_law | 1.834 ms | 0.367 ms | 0.183 ms | 0.092 ms | 0.037 ms |

## 6. API usage

| stage | billed calls | cache hits | prompt tok | completion tok | est. cost (USD) |
|---|---|---|---|---|---|
| distill | 4787 | 2413 | 1610261 | 152278 | 0.092695 |
| interactions | 4801 | 2400 | 795063 | 436454 | 0.074669 |
| refine | 1514 | 55 | 608871 | 77967 | 0.036681 |

## 7. Notes and limitations

- The model served by the provider is `meta-llama/llama-3.1-8b-instruct`; the original HGF checkpoint `meta-llama/Meta-Llama-3-8B-Instruct` is no longer served, so the Llama-3.1-8B-Instruct substitute is used consistently for inference, distillation and condensation.
- BM25 absolute scores depend on corpus size; at this scale τ=100/80 merge very little, which is reported as measured rather than tuned away.
- Serialized bytes are an application-layer payload model: no TCP/TLS/header overhead.
- 1201 experiences stayed unmerged because their group exceeded the condensation context budget (`context_overflow_unmerged`); the affected reductions are therefore lower bounds, not optimised results.
- Resource experiment only: no heldout accuracy is reported (`not_evaluated`).

