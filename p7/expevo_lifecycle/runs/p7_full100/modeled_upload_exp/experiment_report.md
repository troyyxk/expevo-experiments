# P9 (Scheme A) — modeled upload time

Method: `analytical_D_over_R`. No network measurement, no `tc`, no HTTP, no LLM calls.

## Results

| Effective rate (Mbps) | Raw (ms/item) | Distilled (ms/item) | Raw total (s) | Distilled total (s) | Time saving |
|---:|---:|---:|---:|---:|---:|
| 1 | 7.3601 | 1.6568 | 176.6413 | 39.7639 | 77.49% |
| 5 | 1.4720 | 0.3314 | 35.3283 | 7.9528 | 77.49% |
| 10 | 0.7360 | 0.1657 | 17.6641 | 3.9764 | 77.49% |
| 20 | 0.3680 | 0.0828 | 8.8321 | 1.9882 | 77.49% |
| 50 | 0.1472 | 0.0331 | 3.5328 | 0.7953 | 77.49% |

Payload reduction: 77.49%  (22,080,160 B -> 4,970,488 B over 24,000 pairs).
Modeled time saving equals the payload reduction at every rate, as `D/R` requires.

## Figure

`figures/fig_modeled_upload_time.pdf` (single column, 249.8 x 198.7 pt), `300` dpi PNG alongside.


## Model boundaries

- Included: pure application-layer serialized payload transmission time.
- Excluded: RTT, TCP/IP/HTTP headers, connection setup, TLS, queueing, congestion, retransmission, distillation/refinement compute, downstream response.
- This is a deterministic cost model, so no error bars and no trial-to-trial variation exist.
- Naming: `modeled upload time` / `D/R`-based time only; never `measured`, `observed` or `emulated`.
