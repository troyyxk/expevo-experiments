# Revision log — heterogeneous coverage experiment

## Why a second sharing experiment

The matched-coverage experiment (`../tsc_collaboration/`) holds the construction questions constant and
finds no accuracy effect. That design cannot answer whether *complementary* experience helps, because
every client there already had experience on all 60 questions. This experiment creates complementary
coverage and re-asks the question.

## What was built

- Frozen partition of the 60 construction questions into 4 × 15 (seed 20261108).
- Four local pools (375 each), a 1,500-entry union covering all 60 questions, and three 375-entry matched
  pools covering all 60 (seeds 20261109/10/11, owners 4/4/4/3).
- 2,750 new answers (local + matched ×3 + union), 0 failures, 10.8 min, $0.063.
- No historical prediction was reused: the union is a 1,500-entry pool, not the 6,000-entry repository.

## Results

| Setting | Accuracy (%) | 95% CI |
|---|---:|---|
| Local-only | 81.45 | [72.36, 89.82] |
| Shared-matched | 80.48 | [71.76, 88.43] |
| Shared-full-hetero | 80.73 | [71.82, 88.73] |

Δ(Matched−Local) = −0.97 [−4.06, +2.12]; Δ(Full−Matched) = +0.24 [−2.73, +3.09];
Δ(Full−Local) = −0.73 [−3.82, +2.36]. Matched pool seeds: 80.55 / 78.73 / 82.18.

## Reading

No measurable accuracy effect of complementary coverage. The manipulation is verifiably active
(3.6/5 retrieved experiences come from other clients; 21 % Top-5 overlap with the union), so the null
result is not an artifact of an inactive treatment. The paper should present sharing as a
communication/storage saving, not as an accuracy gain.

## Not claimed

- That clients organically sampled disjoint tasks: the exposure is retrospective.
- That the three matched seeds bound the pool variance: they illustrate it.
- Any latency, uplink or storage statement: those are measured elsewhere (P7, P9, Fig. 6, Table II).
