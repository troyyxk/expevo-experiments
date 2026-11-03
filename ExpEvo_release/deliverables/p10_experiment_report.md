# P10 — Backend refinement: resources and held-out accuracy

## Setup

- Repositories: `/data/xingkun/exp_scale/p7/expevo_lifecycle/runs/p7_full100` reused, not regenerated (16/16).
- Grouping: directed BM25 (`rank_bm25.BM25Okapi`, k1=1.5, b=0.75), raw scores, absolute
  thresholds applied independently to the same frozen snapshot; anchor = first unused id in
  stable order; candidate joins when `S[anchor, candidate] >= threshold`.
- Condensation: Llama-3.1-8B-Instruct, T=0, max 512 tokens; groups over 3,500 words are
  rejected and their members retained unmerged (never dropped).
- Retrieval: BM25 Top-5, deterministic order (score desc, id tie-break), query = question + options,
  identical for all five settings.
- Answering: Llama-3.1-8B-Instruct, T=0.7, max 320 tokens, JSON answer, 10 samples per question.
- API: 11,020 calls, 4,804,987 input tokens, 934,890 output tokens, est. $0.315.

## Resources

| Setting | Storage (MB) | Indexed entries | Storage red. (%) | Entry red. (%) |
|---|---:|---:|---:|---:|
| Full | 4.970 | 24,000 | 0.0 | 0.0 |
| BM25_100 | 4.099 | 20,624 | 17.5 | 14.1 |
| BM25_80 | 2.937 | 15,406 | 40.9 | 35.8 |
| BM25_60 | 1.599 | 8,332 | 67.8 | 65.3 |
| BM25_40 | 1.509 | 6,529 | 69.6 | 72.8 |

## Why storage is non-monotonic at the lowest threshold

At tau=40 the similarity groups become large, so many of them exceed the 3,500-word
condensation budget and are **rejected**; their members are retained individually. That adds
entries and bytes back, which is why International Law and College Medicine grow between
tau=60 and tau=40 while College Biology and High School Geography keep shrinking.

| Subject | tau | entries | condensed groups | retained singletons | budget-rejected items | MB condensed | MB retained |
|---|---:|---:|---:|---:|---:|---:|---:|
| international_law | 100 | 4989 | 149 | 4840 | 0 | 0.058 | 1.067 |
| international_law | 80 | 3288 | 308 | 2980 | 99 | 0.116 | 0.603 |
| international_law | 60 | 1817 | 278 | 1539 | 511 | 0.107 | 0.319 |
| international_law | 40 | 1834 | 140 | 1694 | 1529 | 0.061 | 0.456 |
| college_medicine | 100 | 5033 | 127 | 4906 | 0 | 0.041 | 0.896 |
| college_medicine | 80 | 4021 | 255 | 3766 | 494 | 0.079 | 0.655 |
| college_medicine | 60 | 2360 | 330 | 2030 | 854 | 0.092 | 0.341 |
| college_medicine | 40 | 2977 | 164 | 2813 | 2624 | 0.046 | 0.568 |
| college_biology | 100 | 4874 | 143 | 4731 | 0 | 0.049 | 0.893 |
| college_biology | 80 | 3379 | 316 | 3063 | 99 | 0.095 | 0.525 |
| college_biology | 60 | 1711 | 318 | 1393 | 100 | 0.094 | 0.214 |
| college_biology | 40 | 776 | 235 | 541 | 223 | 0.068 | 0.098 |
| high_school_geography | 100 | 5728 | 72 | 5656 | 0 | 0.024 | 1.072 |
| high_school_geography | 80 | 4718 | 223 | 4495 | 0 | 0.068 | 0.797 |
| high_school_geography | 60 | 2444 | 335 | 2109 | 108 | 0.093 | 0.339 |
| high_school_geography | 40 | 942 | 281 | 661 | 282 | 0.083 | 0.128 |

Example: International Law condenses 278 groups at tau=60 but only 140 at tau=40, while
budget-rejected items rise from 511 to 1,529 and the retained-membership bytes rise from
0.319 MB to 0.456 MB. Nothing is dropped or double counted — the lineage partition still
covers all 6,000 experiences exactly once.

## Accuracy

| Setting | Accuracy (%) | Delta vs Full (pp) | 95% paired CI of the delta |
|---|---:|---:|---|
| Full | 75.68 | +0.00 | [+0.00, +0.00] |
| BM25_100 | 75.50 | -0.18 | [-2.00, +1.68] |
| BM25_80 | 75.14 | -0.55 | [-2.45, +1.36] |
| BM25_60 | 74.41 | -1.27 | [-3.36, +0.73] |
| BM25_40 | 75.27 | -0.41 | [-2.32, +1.50] |

The stratified paired bootstrap resamples questions within each subject (220 question IDs, 5,000 replicates) and recomputes every setting on the same resample, so the
delta interval is much tighter than the marginal accuracy interval. Every delta interval contains
zero, so no threshold is shown to differ from Full.

Expressed as counts rather than percentages: out of 2200 sampled answers per setting, Full answers 1665 correctly, BM25_100 1661 (-4), BM25_80 1653 (-12), BM25_60 1637 (-28), BM25_40 1656 (-9).

## Refusals

A sampled answer containing no A-D letter is counted as **incorrect** in the primary number.
Refusals per setting: Full 1, BM25_100 3, BM25_80 0, BM25_60 0, BM25_40 1.

| Setting | Refusals counted incorrect (%) | Refusals excluded (%) |
|---|---:|---:|
| Full | 75.68 | 75.73 |
| BM25_100 | 75.50 | 75.61 |
| BM25_80 | 75.14 | 75.14 |
| BM25_60 | 74.41 | 74.41 |
| BM25_40 | 75.27 | 75.31 |

Excluding them changes every setting by less than 0.1 pp, so it cannot change a conclusion.

## Original vs extended question set

| Question set | Questions | Setting | Accuracy (%) |
|---|---:|---|---:|
| extended | 160 | BM25_100 | 77.69 |
| extended | 160 | BM25_40 | 77.06 |
| extended | 160 | BM25_60 | 77.06 |
| extended | 160 | BM25_80 | 77.31 |
| extended | 160 | Full | 77.81 |
| original | 60 | BM25_100 | 69.67 |
| original | 60 | BM25_40 | 70.50 |
| original | 60 | BM25_60 | 67.33 |
| original | 60 | BM25_80 | 69.33 |
| original | 60 | Full | 70.00 |

The two sets share the same repositories, retrieval and prompt; the extended set only adds
questions that were never used for construction or refinement. The extended questions are
somewhat easier, so absolute levels differ, but the ordering across settings does not.

## Table 2

| Setting | Acc (%) | Storage (MB) | Entries | Storage red. (%) | Entry red. (%) |
|---|---:|---:|---:|---:|---:|
| Full | 75.68 | 4.970 | 24000 | 0.00 | 0.00 |
| BM25_100 | 75.50 | 4.099 | 20624 | 17.53 | 14.07 |
| BM25_80 | 75.14 | 2.937 | 15406 | 40.91 | 35.81 |
| BM25_60 | 74.41 | 1.599 | 8332 | 67.83 | 65.28 |
| BM25_40 | 75.27 | 1.509 | 6529 | 69.64 | 72.80 |

## Answer-format audit

11000 responses across the two question sets. 5 carry no A-D letter (4 safety refusals and 1 malformed letter `I`), all counted as incorrect.
One earlier reply used `"answer":"D. Mongolia"`; a documented rule
(`<LETTER>. <text>` -> letter) recovers it, logged in `reports/parse_repairs.jsonl`.
No gold label is ever read by the parser.

## Methodology sentence for the paper (Section IV-C)

`Groups exceeding the 3,500-word condensation budget are excluded from merging, and their
original experiences are retained.` This is exactly what the tau=40 rebound measures, so the
sentence makes Figure 5 explainable from the method description alone.

## Limitations

- 55 held-out questions per subject (15 original + 40 extended) is still a modest evaluation set;
  the intervals are reported, and no threshold is proven better or worse than Full.
- `G_ret` is the indexed-entry count, a repository-size proxy, not measured BM25 latency.
- Backend refinement happens after upload and does not reduce the uplink payload of P7/P9.
- Accuracy comes from a reconstructed run with Llama-3.1-8B-Instruct and is not numerically
  comparable with the older NMI results.

