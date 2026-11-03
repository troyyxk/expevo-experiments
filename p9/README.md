# P9 — Real network upload measurement

Measures the **application-level upload completion time** of P7's raw episodes versus distilled
experiences over a bandwidth-limited link, using the *same* 24,000 serialized payloads.

## Layout

| File | Purpose |
|---|---|
| `common.py` | P7 canonical serializer, pair loader, 1,000-item batching |
| `receiver.py` | Backend HTTP/1.1 receiver: reads full body, validates NDJSON record count, returns SHA256 ACK |
| `uploader.py` | Frontend client: persistent connection, warmup, times each POST |
| `run_benchmark.py` | Driver: `tc tbf` per rate → iperf3 calibration → upload trials → CSV |
| `setup_network.sh` / `set_rate.sh` / `cleanup_network.sh` | netns + veth + `tc` topology (idempotent) |
| `remote_run.sh` | One-shot wrapper for a privileged host (`smoke` or `full`) |
| `analyze.py` | Batch CSV → per-trial and per-condition statistics |
| `plot_p9.py` | IEEE double-column figure (modeled vs measured) |
| `report_p9.py` / `paper_text.py` | Markdown report and paper paragraph/caption |

## Run

```bash
# on a host with root (or CAP_NET_ADMIN) and iperf3:
sudo bash remote_run.sh smoke     # 40 pairs, 1 rate — validates the pipeline
sudo bash remote_run.sh full      # 5 rates x 2 modes x 5 trials x 24 batches = 1,200 POSTs (~30 min)
python3 analyze.py --dir results/full_YYYYmmdd_HHMMSS
python3 plot_p9.py --dir results/full_YYYYmmdd_HHMMSS
python3 report_p9.py --dir results/full_YYYYmmdd_HHMMSS
```

## Measurement contract

- body = `b"\n".join(1000 canonical items) + b"\n"`; `canonical_payload_bytes` excludes the separators,
  `http_body_bytes` includes them.
- timing = `perf_counter_ns` around `POST` → full ACK read, after connection warmup; bodies and
  SHA256 are prepared before the clock starts.
- `TCP_NODELAY` on both ends — without it, Nagle plus delayed ACK adds a spurious ~40 ms per request.
- TBF burst is `max(2 KB, R x 0.25 KB)` (≈2 ms of link time) so the token bucket cannot swallow a
  short batch; the burst used per rate is recorded in `calibration.csv`.
