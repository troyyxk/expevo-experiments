# Revision log — backend management overhead (TSC §5.2)

## Guidance availability

`guidance/README.md`, `guidance/AGENTS.md` and `guidance/ExpEvo_TMC_Revision_Guide.md` are **not present**
in this workspace (checked before starting). This experiment therefore follows the execution guide
(`20261104-ExpEvo-TSC-Backend-Management-Overhead-Agent执行指南.md`) directly; nothing in it conflicted
with the frozen data or with earlier project decisions.

## Scope

One subject (`high_school_geography`), one threshold (`tau_sim = 40`), **zero new LLM calls** — the API
log was last written on 2026-10-27, before this experiment started. Only `build_matrix()` and
`group_ids()` are imported from the frozen `src/refine.py`; `condense()` and the `refine.py` main
pipeline are never invoked. The three
cost families are reported side by side and never summed: historical API requests, one-off local
maintenance, and per-query retrieval.

## Frozen inputs (read-only)

| Item | Value |
|---|---|
| Full repository | 6,000 entries, `p7/expevo_lifecycle/runs/p7_full100/full_repositories/high_school_geography.jsonl` |
| Refined repository | 942 entries, `.../refined/high_school_geography/bm25_40.jsonl` |
| Entry reduction | 84.3 % (single subject; **not** the 72.8 % four-subject aggregate) |
| Refined entries' provenance | the 942 entries cover all 6,000 source experiences exactly once |
| Queries | 55 (15 original + 40 extended), unique keys, identical text for both repositories |
| API log | `.../p7_full100/tables/api_usage.csv`, tag `condense/high_school_geography/bm25_40` |

File hashes, query-set hash, hardware and package versions: `manifests/input_manifest.json`.

## New measurements (all local, all timed with `perf_counter`)

| Measurement | Value | Runs |
|---|---|---|
| BM25 similarity matrix, 6000×6000 float64 | **94.1 s** (median; 92.5–150.3) | 6 |
| Anchor grouping, tau=40 (662 groups) | **0.38 s** (0.377–0.391) | 6 |
| Index build, full → refined | **0.0354 s → 0.0079 s** | 9 each |
| Hot query P50, full → refined | **22.67 ms → 3.60 ms** (−84.1 %) | 3 × 275 each |
| Hot query P95, full → refined | **37.72 ms → 5.73 ms** (−84.8 %) | 3 × 275 each |

Run-to-run variation on this shared node is substantial and is reported rather than hidden: an earlier
standalone round measured 28.11 → 3.99 ms (P50) and a 109.8 s matrix, i.e. the absolute times move with
machine state while the refined/full ratio stays at 84–86 %. Query numbers here are the median of three
measurement sessions (22.40–22.88 ms for the full repository, 3.42–3.63 ms for the refined one within
those sessions).

Peak RSS during matrix construction: 329 MiB (the matrix itself is 288 MB). Query-cost decomposition:
tokenisation 0.01 ms, BM25 scoring 18.1 ms, ranking 3.9 ms on the full repository — i.e. 81 % of the
per-query time is scoring, which is why fewer entries translate directly into a lower latency.

## Historical LLM condensation (re-analysis, not new calls)

275 successful uncached requests, 6 cache hits, 0 failures. 186,279 input and 12,864 output tokens.
Per-request latency P50 1.691 s, P95 4.052 s. Logged estimated cost $0.0103.
Cache-hit rows (latency 0) are excluded from every latency statistic, and request latencies are **not**
summed: they were issued concurrently and the log has no per-request completion ordering.

Cross-check: the grouping step produced 662 groups, of which 379 are singletons that need no
condensation; 283 groups remain, against 281 logged condensation requests (275 uncached + 6 cached).
The two numbers are consistent.

Experience distillation (`distill/high_school_geography`, 4,163 calls, $0.0700) is reported in
`results/distillation_cost_separate.csv` and is **not** part of the backend table.

## Repetition beyond the minimum

The supplementary instruction allows a single matrix timing and one pass of 55 x 5 x 2 queries. Because
the node is shared and the first round differed from the second by ~16 %, the measurements were repeated
(two sessions of three matrix builds, three query sessions) and the medians are reported. This is the
same measurement repeated for stability, not an extension of the experimental scope.

## Things deliberately not claimed

- No end-to-end service latency: the model generation time is not part of these measurements.
- No condensation wall-clock: the log records per-request latency for concurrent calls.
- The old `manifest_refine.json` wall-clock of 667.9 s covers four subjects and four thresholds and is
  **not** attributed to this single-subject configuration.
- No amortisation statement. A break-even count could be computed (110 s of maintenance against a
  24 ms per-query saving) but it would mix a one-off job triggered by a threshold change with a query
  rate that this experiment never measured, so it is left out of the paper.

## Deviations / gaps

- The refined repository shipped with the project was **not** regenerated; its condensation text came
  from the original run. Only grouping was re-timed, so the 0.38 s figure is the local part of the
  pipeline, not a full re-run.
- Index build time covers `BM25Okapi` construction on a pre-tokenised corpus; document tokenisation is
  reported separately in `raw/index_build_runs.csv` (0.035 s full, 0.008 s refined).
- Timings are single-machine and the node is shared (Xeon Platinum 8368, 152 logical cores, no CPU
  pinning, no isolated NUMA node). Absolute values therefore differ across runs — the matrix build was
  measured between 92.5 s and 150.3 s — so the paper quotes medians and the full/refined ratio, which
  stayed at 84–86 % in every session.
