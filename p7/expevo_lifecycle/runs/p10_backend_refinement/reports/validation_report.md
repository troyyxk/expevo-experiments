# Validation report — P10 backend refinement

Source run: `/data/xingkun/exp_scale/p7/expevo_lifecycle/runs/p7_full100`

## Input provenance

| Test | Result |
|---|---|
| P7 `p7_full100` is the Fig.3 run | PASS — /data/xingkun/exp_scale/p7/expevo_lifecycle/runs/p7_full100 |
| 6,000 full experiences per subject (24,000 total) | PASS |
| Canonical full bytes = 4,970,488 | PASS — 4,970,488 |
| BM25 60 recomputes to 1,598,983 B / 8,332 entries | PASS — 1,598,983 B / 8,332 |
| BM25 100 matches the P7 figure 4,099,303 B | PASS — 4,099,303 B |
| All thresholds derive from one frozen snapshot per subject | PASS — `source_full_sha256` identical across the five settings |
| Held-out questions disjoint from construction | PASS — 15 per subject (Q060–Q074), 0 overlap |

## Repository integrity

| Test | Result |
|---|---|
| All 4 subjects x 4 thresholds present | PASS — 16/16 reused, 0 regenerated |
| Refined IDs unique | PASS |
| Every entry has source_experience_ids | PASS |
| Lineage is an exact partition of the full repository | PASS — each of 24,000 experience IDs appears in exactly one refined entry |
| No cross-subject merging | PASS |
| Singletons and budget-rejected groups retained and counted | PASS — see `tables/tau40_diagnosis.csv` |

## Held-out evaluation

| Test | Result |
|---|---|
| Questions x settings x samples | 220 questions x 5 settings x 10 samples = 11000 responses |
| API errors | 0 |
| Parsed answers per setting | Full 2199/2200, BM25_100 2197/2200, BM25_80 2200/2200, BM25_60 2200/2200, BM25_40 2199/2200 |
| Answer-format repairs | 0 (documented in `reports/parse_repairs.jsonl`, gold never used) |
| No gold label in prompt | PASS |
| Cache key includes repository hash + retrieved IDs + prompt hash | PASS |
| Extended held-out set frozen | PASS — 40 unused questions per subject, seed 20261028, sha256 recorded |
| Extended set disjoint from construction, original held-out and itself | PASS — checked by qid and by normalized question text |
| Refused / unparsable responses | 5 — counted as incorrect, see experiment report |
| Uncertainty | stratified paired bootstrap over question IDs, 5,000 resamples |

