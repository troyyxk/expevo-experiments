# P9 — Real Network Upload Measurement (results)

_Generated from `/data/xingkun/exp_scale/p9/results/full_20261027_194400` · host `hydu8x5090gpu` · 2026-10-27 19:44:00 → 2026-10-27 20:11:23_

## 1. Where it ran and why

The interactive sandbox has `CapEff=0`, `NoNewPrivs=1` and no user namespaces, so `ip netns` / `veth` / `tc`
cannot be created there. The experiment therefore ran on the RTX-5090 node
(`hydu8x5090gpu`) inside two isolated network namespaces, driven remotely.

- Topology: `expevo_client` (10.226.88.1) ⟷ veth ⟷ `expevo_server` (10.226.88.2)
- Shaping: `tc qdisc tbf` on `veth_ex_c` egress only, `latency 100ms`
- Burst: `max(2 KB, R × 0.25 KB)` — keeps token-bucket slack at ≈2 ms of link time so it cannot swallow a short batch
- Rates: [1, 5, 10, 20, 50] Mbps · trials per condition: 5 · batch size: 1000
- Transport: HTTP/1.1 keep-alive, `Content-Type: application/x-ndjson`, `Accept-Encoding: identity`,
  body = 1,000 canonical P7 items joined by `\n` + trailing `\n`; header `X-Record-Count: 1000`
- Timing: `perf_counter_ns` around POST → full ACK read; bodies and SHA256 precomputed before timing
- TCP_NODELAY on both ends (without it, Nagle + delayed ACK added a spurious ~40 ms per request)

## 2. Link calibration (iperf3, 15 s per rate)

| Configured (Mbps) | TBF burst | iperf3 measured (Mbps) | Deviation | Retransmits | tc dropped | tc overlimits |
|---|---|---|---|---|---|---|
| 1 | 2kb | 0.904 | 9.6 | 17 | 0 | 0 |
| 5 | 2kb | 4.669 | 6.62 | 25 | 581 | 224926 |
| 10 | 3kb | 9.533 | 4.67 | 36 | 1034 | 431911 |
| 20 | 5kb | 19.082 | 4.59 | 0 | 1342 | 647689 |
| 50 | 13kb | 47.818 | 4.36 | 0 | 1342 | 886326 |

## 3. Main results (5 full-corpus trials per condition)

| R (Mbps) | iperf3 (Mbps) | HTTP goodput (Mbps) | Measured raw (ms/item) | Measured distilled (ms/item) | Modeled raw (ms/item) | Modeled distilled (ms/item) | Saving (%) |
|---|---|---|---|---|---|---|---|
| 1 | 0.904 | 0.955 | 7.705821 | 1.742768 | 7.3601 | 1.6568 | 77.38 |
| 5 | 4.669 | 4.774 | 1.541838 | 0.348571 | 1.472 | 0.3314 | 77.39 |
| 10 | 9.533 | 9.533 | 0.772032 | 0.173991 | 0.736 | 0.1657 | 77.46 |
| 20 | 19.082 | 19.021 | 0.386935 | 0.08682 | 0.368 | 0.0828 | 77.56 |
| 50 | 47.818 | 47.258 | 0.155741 | 0.034426 | 0.1472 | 0.0331 | 77.9 |

Values are amortized per experience: `sum(24 batch times) / 24,000`.

Measured times exceed the modeled `D/R` at the nominal rate by 4.0–5.8 %, uniformly across rates.
That gap is *proportional to the payload*, not a fixed per-request cost. It is almost entirely the
link's goodput ratio: TBF meters whole frames, so the shaped link carries ~95 % of the nominal rate as
payload (10.000 -> 9.533 Mbps measured by HTTP at 10 Mbps), and `1/0.953 = 1.049` reproduces the
observed 4.9 % excess. Because the overhead scales with bytes it cancels in the raw-vs-distilled ratio,
which is why the saving stays flat instead of eroding at high rates.

One caveat on the counters above: `tc qdisc replace` keeps the existing qdisc instance, so
`tc_dropped`/`tc_overlimits` accumulate across the sweep and are shifted one rate later than the row
they appear in. They are a sanity signal, not per-rate loss statistics. Per-batch ACK verification
passed 1,200/1,200, and iperf3 retransmits were 0–36 per 15 s.

## 4. Per-trial detail

| R | Mode | Trial | Batch mean (ms) | Batch SD (ms) | Trial total (ms) | ms/item |
|---|---|---|---|---|---|---|
| 1 | distilled | 1 | 1742.261 | 162.238 | 41814.252 | 1.74226 |
| 1 | distilled | 2 | 1742.888 | 163.26 | 41829.309 | 1.742888 |
| 1 | distilled | 3 | 1742.888 | 163.279 | 41829.317 | 1.742888 |
| 1 | distilled | 4 | 1742.962 | 163.241 | 41831.082 | 1.742962 |
| 1 | distilled | 5 | 1742.843 | 163.25 | 41828.227 | 1.742843 |
| 1 | raw | 1 | 7707.645 | 1445.982 | 184983.481 | 7.707645 |
| 1 | raw | 2 | 7705.203 | 1445.367 | 184924.871 | 7.705203 |
| 1 | raw | 3 | 7705.316 | 1445.078 | 184927.583 | 7.705316 |
| 1 | raw | 4 | 7705.643 | 1445.191 | 184935.442 | 7.705643 |
| 1 | raw | 5 | 7705.297 | 1444.783 | 184927.123 | 7.705297 |
| 5 | distilled | 1 | 347.998 | 32.485 | 8351.955 | 0.347998 |
| 5 | distilled | 2 | 350.427 | 32.965 | 8410.245 | 0.350427 |
| 5 | distilled | 3 | 348.138 | 32.703 | 8355.314 | 0.348138 |
| 5 | distilled | 4 | 348.129 | 32.482 | 8355.088 | 0.348129 |
| 5 | distilled | 5 | 348.161 | 32.659 | 8355.875 | 0.348161 |
| 5 | raw | 1 | 1542.109 | 289.64 | 37010.605 | 1.542109 |
| 5 | raw | 2 | 1541.598 | 289.478 | 36998.349 | 1.541598 |
| 5 | raw | 3 | 1541.685 | 289.445 | 37000.437 | 1.541685 |
| 5 | raw | 4 | 1542.014 | 289.582 | 37008.343 | 1.542014 |
| 5 | raw | 5 | 1541.782 | 289.613 | 37002.767 | 1.541782 |
| 10 | distilled | 1 | 174.026 | 16.331 | 4176.626 | 0.174026 |
| 10 | distilled | 2 | 174.033 | 16.324 | 4176.794 | 0.174033 |
| 10 | distilled | 3 | 173.979 | 16.27 | 4175.493 | 0.173979 |
| 10 | distilled | 4 | 173.943 | 16.306 | 4174.641 | 0.173943 |
| 10 | distilled | 5 | 173.973 | 16.262 | 4175.343 | 0.173973 |
| 10 | raw | 1 | 772.179 | 145.055 | 18532.293 | 0.772179 |
| 10 | raw | 2 | 772.093 | 145.111 | 18530.226 | 0.772093 |
| 10 | raw | 3 | 771.988 | 145.042 | 18527.703 | 0.771988 |
| 10 | raw | 4 | 771.806 | 145.012 | 18523.341 | 0.771806 |
| 10 | raw | 5 | 772.095 | 144.789 | 18530.291 | 0.772095 |
| 20 | distilled | 1 | 86.826 | 8.207 | 2083.821 | 0.086826 |
| 20 | distilled | 2 | 86.803 | 8.17 | 2083.267 | 0.086803 |
| 20 | distilled | 3 | 86.851 | 8.176 | 2084.432 | 0.086851 |
| 20 | distilled | 4 | 86.815 | 8.249 | 2083.565 | 0.086815 |
| 20 | distilled | 5 | 86.805 | 8.214 | 2083.329 | 0.086805 |
| 20 | raw | 1 | 387.275 | 72.712 | 9294.59 | 0.387275 |
| 20 | raw | 2 | 386.818 | 72.732 | 9283.632 | 0.386818 |
| 20 | raw | 3 | 386.617 | 72.499 | 9278.813 | 0.386617 |
| 20 | raw | 4 | 387.016 | 73.217 | 9288.391 | 0.387016 |
| 20 | raw | 5 | 386.95 | 72.749 | 9286.812 | 0.386951 |
| 50 | distilled | 1 | 34.514 | 3.242 | 828.345 | 0.034514 |
| 50 | distilled | 2 | 34.365 | 3.286 | 824.749 | 0.034365 |
| 50 | distilled | 3 | 34.35 | 3.274 | 824.406 | 0.03435 |
| 50 | distilled | 4 | 34.413 | 3.243 | 825.901 | 0.034413 |
| 50 | distilled | 5 | 34.486 | 3.276 | 827.669 | 0.034486 |
| 50 | raw | 1 | 156.262 | 29.532 | 3750.3 | 0.156262 |
| 50 | raw | 2 | 155.782 | 29.447 | 3738.758 | 0.155782 |
| 50 | raw | 3 | 155.865 | 29.566 | 3740.768 | 0.155865 |
| 50 | raw | 4 | 155.146 | 29.091 | 3723.507 | 0.155146 |
| 50 | raw | 5 | 155.65 | 29.431 | 3735.609 | 0.15565 |

## 5. Figure

`fig_p9_upload_time_measured.pdf/png` — left: completion time per 1,000-item batch vs configured rate
(modeled `D/R` dashed, measured solid with ±SD over trials); right: measured upload-time saving.

## 6. Caveats

- This is a **controlled Linux network-emulation measurement**, not a field cellular measurement.
- The shaped rate is set by `tc tbf`; the achieved rate is reported above and differs from nominal by design.
- Upload time includes HTTP request/ACK overhead and excludes LLM inference and distillation.
- `canonical_payload_bytes` excludes the NDJSON separators; `http_body_bytes` includes them.
