# P9 (Scheme A) — validation report

Input: `/data/xingkun/exp_scale/ExpEvo_release/p7/expevo_lifecycle/runs/p7_full100`

| Check | Result | Evidence |
|---|---|---|
| 6,000 unique pairs per subject | PASS | International Law 6,000, College Medicine 6,000, College Biology 6,000, High School Geography 6,000 |
| 1:1 episode/experience pairing | PASS | set equality on all four subjects |
| Byte totals match the Fig.3 byte table | PASS | 4/4 rows identical |
| Total raw bytes | PASS | 22,080,160 |
| Total distilled bytes | PASS | 4,970,488 |
| Aggregate vs per-item mean | PASS | agree to 1e-9 for every rate |
| avg x N == total | PASS | asserted for every rate |
| Saving independent of R | PASS | identical to 9 decimals across all rates |
| Serializer | PASS | `serialize_item` reproduces stored `raw_payload_bytes` / `distilled_payload_bytes` for all 24,000 pairs |
