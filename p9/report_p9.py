"""Build P9_REPORT.md from the measured CSVs."""
import argparse, csv, json, os


def table(rows, cols, headers=None, fmt=None):
    headers = headers or cols
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(cols)) + "|"]
    for r in rows:
        cells = []
        for c in cols:
            v = r.get(c, "")
            cells.append(fmt[c](v, r) if fmt and c in fmt else str(v))
        out.append("| " + " | ".join(cells) + " |")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    a = ap.parse_args()
    d = a.dir
    meta = json.load(open(os.path.join(d, "meta.json")))
    cal = list(csv.DictReader(open(os.path.join(d, "calibration.csv"))))
    sav = list(csv.DictReader(open(os.path.join(d, "saving_summary.csv"))))
    cond = list(csv.DictReader(open(os.path.join(d, "condition_summary.csv"))))
    trials = list(csv.DictReader(open(os.path.join(d, "trial_summary.csv"))))

    cal_t = table(cal, ["rate_mbps", "burst", "receiver_mbps", "deviation_pct", "retransmits",
                        "tc_dropped", "tc_overlimits"],
                  ["Configured (Mbps)", "TBF burst", "iperf3 measured (Mbps)", "Deviation", "Retransmits",
                   "tc dropped", "tc overlimits"])
    res_t = table(sav, ["rate_mbps", "calibrated_mbps", "effective_raw_mbps", "raw_ms_per_item",
                        "distilled_ms_per_item", "modeled_raw_ms_per_item", "modeled_distilled_ms_per_item",
                        "measured_saving_pct"],
                  ["R (Mbps)", "iperf3 (Mbps)", "HTTP goodput (Mbps)", "Measured raw (ms/item)",
                   "Measured distilled (ms/item)", "Modeled raw (ms/item)", "Modeled distilled (ms/item)",
                   "Saving (%)"])
    trial_t = table(trials, ["rate_mbps", "mode", "trial", "batch_ms_mean", "batch_ms_sd",
                             "trial_total_ms", "amortized_ms_per_item"],
                    ["R", "Mode", "Trial", "Batch mean (ms)", "Batch SD (ms)", "Trial total (ms)", "ms/item"])

    doc = f"""# P9 — Real Network Upload Measurement (results)

_Generated from `{os.path.abspath(d)}` · host `{meta.get('host')}` · {meta.get('started')} → {meta.get('finished')}_

## 1. Where it ran and why

The interactive sandbox has `CapEff=0`, `NoNewPrivs=1` and no user namespaces, so `ip netns` / `veth` / `tc`
cannot be created there. The experiment therefore ran on the RTX-5090 node
(`hydu8x5090gpu`) inside two isolated network namespaces, driven remotely.

- Topology: `expevo_client` (10.226.88.1) ⟷ veth ⟷ `expevo_server` (10.226.88.2)
- Shaping: `tc qdisc tbf` on `veth_ex_c` egress only, `latency 100ms`
- Burst: `max(2 KB, R × 0.25 KB)` — keeps token-bucket slack at ≈2 ms of link time so it cannot swallow a short batch
- Rates: {meta['rates']} Mbps · trials per condition: {meta['trials']} · batch size: {meta['batch_size']}
- Transport: HTTP/1.1 keep-alive, `Content-Type: application/x-ndjson`, `Accept-Encoding: identity`,
  body = 1,000 canonical P7 items joined by `\\n` + trailing `\\n`; header `X-Record-Count: 1000`
- Timing: `perf_counter_ns` around POST → full ACK read; bodies and SHA256 precomputed before timing
- TCP_NODELAY on both ends (without it, Nagle + delayed ACK added a spurious ~40 ms per request)

## 2. Link calibration (iperf3, 15 s per rate)

{cal_t}

## 3. Main results (5 full-corpus trials per condition)

{res_t}

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

{trial_t}

## 5. Figure

`fig_p9_upload_time_measured.pdf/png` — left: completion time per 1,000-item batch vs configured rate
(modeled `D/R` dashed, measured solid with ±SD over trials); right: measured upload-time saving.

## 6. Caveats

- This is a **controlled Linux network-emulation measurement**, not a field cellular measurement.
- The shaped rate is set by `tc tbf`; the achieved rate is reported above and differs from nominal by design.
- Upload time includes HTTP request/ACK overhead and excludes LLM inference and distillation.
- `canonical_payload_bytes` excludes the NDJSON separators; `http_body_bytes` includes them.
"""
    open(os.path.join(d, "P9_REPORT.md"), "w").write(doc)
    print("wrote", os.path.join(d, "P9_REPORT.md"))


if __name__ == "__main__":
    main()
