"""Aggregate P9 batch measurements into per-trial, per-condition statistics."""
import argparse, csv, json, os, statistics as st

N_ITEMS = 24000


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    out = a.out or a.out or a.dir
    rows = list(csv.DictReader(open(os.path.join(a.dir, "batches.csv"))))
    cal = list(csv.DictReader(open(os.path.join(a.dir, "calibration.csv"))))
    trial = {}
    for r in rows:
        k = (int(r["rate_mbps"]), r["mode"], int(r["trial"]))
        d = trial.setdefault(k, {"ms": 0.0, "canon": 0, "body": 0, "n": 0, "batches": []})
        d["ms"] += float(r["measured_batch_ms"])
        d["canon"] += int(r["canonical_payload_bytes"])
        d["body"] += int(r["http_body_bytes"])
        d["batches"].append(float(r["measured_batch_ms"]))
        d["n"] += int(r["record_count"])

    trials = []
    for (rate, mode, t), d in sorted(trial.items()):
        assert d["n"] == N_ITEMS, (rate, mode, t, d["n"])
        trials.append({"rate_mbps": rate, "mode": mode, "trial": t,
                       "batch_count": len(d["batches"]),
                       "canonical_payload_bytes": d["canon"],
                       "http_body_bytes": d["body"],
                       "trial_total_ms": round(d["ms"], 3),
                       "amortized_ms_per_item": round(d["ms"] / N_ITEMS, 6),
                       "batch_ms_mean": round(st.mean(d["batches"]), 3),
                       "batch_ms_sd": round(st.stdev(d["batches"]), 3) if len(d["batches"]) > 1 else 0.0})
    with open(os.path.join(out, "trial_summary.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(trials[0].keys())); w.writeheader(); w.writerows(trials)

    cond = {}
    for r in trials:
        cond.setdefault((r["rate_mbps"], r["mode"]), []).append(r["amortized_ms_per_item"])
    summary = []
    for (rate, mode), vals in sorted(cond.items()):
        summary.append({"rate_mbps": rate, "mode": mode, "trials": len(vals),
                        "amortized_ms_per_item_mean": round(st.mean(vals), 6),
                        "amortized_ms_per_item_sd": round(st.stdev(vals), 6) if len(vals) > 1 else 0.0,
                        "batch_ms_mean": round(st.mean(vals) * 1000, 3),
                        "canonical_bytes_total": 22080160 if mode == "raw" else 4970488})
    with open(os.path.join(out, "condition_summary.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(summary[0].keys())); w.writeheader(); w.writerows(summary)

    sav = []
    for rate in sorted({s["rate_mbps"] for s in summary}):
        raw = next(s for s in summary if s["rate_mbps"] == rate and s["mode"] == "raw")
        dis = next(s for s in summary if s["rate_mbps"] == rate and s["mode"] == "distilled")
        conf = next((c for c in cal if int(c["rate_mbps"]) == rate), {})
        eff = 8 * (22080160 if raw["mode"]=="raw" else 4970488) / (raw["batch_ms_mean"] * 24 * 1000)
        sav.append({"rate_mbps": rate,
                    "calibrated_mbps": conf.get("receiver_mbps", ""),
                    "deviation_pct": conf.get("deviation_pct", ""),
                    "raw_ms_per_item": raw["amortized_ms_per_item_mean"],
                    "distilled_ms_per_item": dis["amortized_ms_per_item_mean"],
                    "effective_raw_mbps": round(8 * 22080160 / (raw["batch_ms_mean"] * 24) / 1e3, 3),
                    "modeled_at_configured_ms_per_item": round(8 * 22080160 / (N_ITEMS * rate * 1e6) * 1000, 4),
                    "measured_saving_pct": round(100 * (1 - dis["amortized_ms_per_item_mean"] / raw["amortized_ms_per_item_mean"]), 2),
                    "modeled_raw_ms_per_item": round(8 * 22080160 / (N_ITEMS * rate * 1e6) * 1000, 4),
                    "modeled_distilled_ms_per_item": round(8 * 4970488 / (N_ITEMS * rate * 1e6) * 1000, 4),
                    "modeled_saving_pct": round(100 * (1 - 4970488 / 22080160), 2)})
    with open(os.path.join(out, "saving_summary.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(sav[0].keys())); w.writeheader(); w.writerows(sav)
    print(open(os.path.join(out, "saving_summary.csv")).read())


if __name__ == "__main__":
    main()
