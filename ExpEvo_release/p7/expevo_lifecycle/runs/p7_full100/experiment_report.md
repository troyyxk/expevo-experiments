# Experiment report — p7_full100

## 1. Setup

- model_id: `meta-llama/llama-3.1-8b-instruct`
- dataset: `cais/mmlu` split `test` revision `c30699e8356da336a370243923dbaf21066bb9fe`
- seed: `20261026`; sampled per subject: 75 (construction 60, heldout rest); repeats: 100
- thresholds: [100, 80, 60, 40]; BM25 k1=1.5, b=0.75

## 2. Lifecycle footprint (canonical serialization)

| subject | questions | raw eps | distilled | full repo | refined@100 | raw MB | dist MB | refined MB | upload ↓ | storage ↓ |
|---|---|---|---|---|---|---|---|---|---|---|
| international_law | 60 | 6000 | 6000 | 6000 | 4989 | 6.2395 | 1.4000 | 1.1254 | 77.56% | 19.61% |
| college_medicine | 60 | 6000 | 6000 | 6000 | 5033 | 6.1498 | 1.1720 | 0.9371 | 80.94% | 20.04% |
| college_biology | 60 | 6000 | 6000 | 6000 | 4874 | 5.4438 | 1.2255 | 0.9412 | 77.49% | 23.2% |
| high_school_geography | 60 | 6000 | 6000 | 6000 | 5728 | 4.2470 | 1.1729 | 1.0956 | 72.38% | 6.6% |
| **total** | | 24000 | 24000 | | | 22.0802 | 4.9705 | 4.0993 | 77.49% | 17.53% |

## 3. Refinement sweep

| subject | τ | refined count | ratio | storage ↓ | items ↓ | overflow |
|---|---|---|---|---|---|---|
| college_biology | 100 | 4874 | 0.8123 | 23.2% | 18.77% | 0 |
| college_biology | 80 | 3379 | 0.5632 | 49.45% | 43.68% | 99 |
| college_biology | 60 | 1711 | 0.2852 | 74.87% | 71.48% | 100 |
| college_biology | 40 | 776 | 0.1293 | 86.42% | 87.07% | 223 |
| college_medicine | 100 | 5033 | 0.8388 | 20.04% | 16.12% | 0 |
| college_medicine | 80 | 4021 | 0.6702 | 37.36% | 32.98% | 494 |
| college_medicine | 60 | 2360 | 0.3933 | 63.1% | 60.67% | 854 |
| college_medicine | 40 | 2977 | 0.4962 | 47.6% | 50.38% | 2624 |
| high_school_geography | 100 | 5728 | 0.9547 | 6.6% | 4.53% | 0 |
| high_school_geography | 80 | 4718 | 0.7863 | 26.26% | 21.37% | 0 |
| high_school_geography | 60 | 2444 | 0.4073 | 63.14% | 59.27% | 108 |
| high_school_geography | 40 | 942 | 0.157 | 82.02% | 84.3% | 282 |
| international_law | 100 | 4989 | 0.8315 | 19.61% | 16.85% | 0 |
| international_law | 80 | 3288 | 0.548 | 48.68% | 45.2% | 99 |
| international_law | 60 | 1817 | 0.3028 | 69.56% | 69.72% | 511 |
| international_law | 40 | 1834 | 0.3057 | 63.03% | 69.43% | 1529 |

## 4. BM25 score diagnostics (raw scale, no rescaling)

| subject | n | self median | off p50 | off p90 | off p99 | off max | frac≥40 | frac≥100 |
|---|---|---|---|---|---|---|---|---|
| international_law | 6000 | 84.3 | 10.04 | 22.39 | 48.09 | 174.7 | 1.571% | 0.019% |
| college_medicine | 6000 | 80.4 | 5.41 | 16.23 | 46.06 | 343.4 | 1.382% | 0.029% |
| college_biology | 6000 | 82.8 | 5.81 | 16.39 | 42.33 | 155.3 | 1.085% | 0.029% |
| high_school_geography | 6000 | 72.9 | 4.92 | 13.61 | 38.04 | 132.0 | 0.907% | 0.003% |

### 2b. Exploratory variant: BM25 τ = 60 (not the official setting)

| subject | full count | τ=60 count | ratio | storage ↓ |
|---|---|---|---|---|
| college_biology | 6000 | 1711 | 0.2852 | 74.87% |
| college_medicine | 6000 | 2360 | 0.3933 | 63.1% |
| high_school_geography | 6000 | 2444 | 0.4073 | 63.14% |
| international_law | 6000 | 1817 | 0.3028 | 69.56% |

The official main figure (`fig_lifecycle_footprint`) uses τ = 100. The τ = 60 bars are reported as an exploratory alternative (`fig_lifecycle_footprint_tau60`) and must not replace the formal 100/80/60/40 sweep.

## 5. Modeled upload time (D/R, not measured latency)

| subject | 1 Mbps | 5 Mbps | 10 Mbps | 20 Mbps | 50 Mbps |
|---|---|---|---|---|---|
| college_biology | 1.634 ms | 0.327 ms | 0.163 ms | 0.082 ms | 0.033 ms |
| college_medicine | 1.563 ms | 0.312 ms | 0.156 ms | 0.078 ms | 0.031 ms |
| high_school_geography | 1.564 ms | 0.313 ms | 0.156 ms | 0.078 ms | 0.031 ms |
| international_law | 1.867 ms | 0.373 ms | 0.187 ms | 0.093 ms | 0.037 ms |

## 6. API usage

| stage | billed calls | cache hits | prompt tok | completion tok | est. cost (USD) |
|---|---|---|---|---|---|
| distill | 16727 | 7273 | 5629077 | 551509 | 0.325575 |
| interactions | 2515 | 21487 | 339526 | 188444 | 0.032052 |
| refine | 3608 | 66 | 2156384 | 191125 | 0.123109 |

## 7. Notes and limitations

- The model served by the provider is `meta-llama/llama-3.1-8b-instruct`; the original HGF checkpoint `meta-llama/Meta-Llama-3-8B-Instruct` is no longer served, so the Llama-3.1-8B-Instruct substitute is used consistently for inference, distillation and condensation.
- BM25 absolute scores depend on corpus size; at this scale τ=100/80 merge very little, which is reported as measured rather than tuned away.
- Serialized bytes are an application-layer payload model: no TCP/TLS/header overhead.
- 6923 experiences stayed unmerged because their group exceeded the condensation context budget (`context_overflow_unmerged`); the affected reductions are therefore lower bounds, not optimised results.
- Resource experiment only: no heldout accuracy is reported (`not_evaluated`).

