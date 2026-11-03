# Validation report

- run: `p7_full`

- [x] dataset frozen with revision/seed — rev=c30699e8...
- [x] construction and heldout question IDs are disjoint
- [x] no heldout question entered any episode — 0 overlaps
- [x] inference prompt template carries no gold answer
- [x] every experience traces to a real episode
- [x] n_raw == n_distilled == full_count — raw=2400 dist=2400 full=2400
- [x] full_bytes == distilled_total_bytes — 484287 vs 484287
- [x] every threshold covers each experience exactly once
- [x] refined_count <= full_count and bytes recomputable
- [x] BM25 diagnostics recorded (raw scores, no rescaling) — 4 rows
- [x] API key absent from all run artifacts
- [x] required figures exist (pdf) — 3 pdf

**Overall: PASS**
