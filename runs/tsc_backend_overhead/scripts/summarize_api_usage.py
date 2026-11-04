#!/usr/bin/env python3
"""Phase B: summarise the historical LLM condensation cost for condense/HSG/bm25_40 (no new calls)."""
import csv, json, os
import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(os.path.dirname(HERE))
LOG = os.path.join(ROOT, "p7", "expevo_lifecycle", "runs", "p7_full100", "tables", "api_usage.csv")
TAG = "condense/high_school_geography/bm25_40"
DISTILL_TAG = "distill/high_school_geography"


def main():
    rows = list(csv.DictReader(open(LOG)))
    sel = [r for r in rows if r["tag"] == TAG]
    assert sel, f"no rows for {TAG}"
    ok = [r for r in sel if r["cached"] == "0" and r["status"] == "ok"]
    hit = [r for r in sel if r["cached"] == "1"]
    bad = [r for r in sel if not (r["cached"] == "0" and r["status"] == "ok") and r["cached"] != "1"]
    assert len(ok) + len(hit) + len(bad) == len(sel), "rows do not partition"

    os.makedirs(os.path.join(HERE, "raw"), exist_ok=True)
    with open(os.path.join(HERE, "raw", "api_usage_filtered.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(sel[0].keys()) + ["group"])
        w.writeheader()
        for r in sel:
            grp = "ok_uncached" if r in ok else ("cache_hit" if r in hit else "failed")
            w.writerow({**r, "group": grp})

    lat = np.array([float(r["latency_s"]) for r in ok])
    tin = sum(int(r["prompt_tokens"]) for r in ok)
    tout = sum(int(r["completion_tokens"]) for r in ok)
    cost = sum(float(r["cost_usd"]) for r in ok)
    hit_cost = sum(float(r["cost_usd"]) for r in hit)
    model = sorted({r["model"] for r in sel})

    summary = [{
        "subject": "high_school_geography", "threshold": 40, "api_tag": TAG,
        "successful_uncached_calls": len(ok), "cache_hits": len(hit), "failed_calls": len(bad),
        "input_tokens": tin, "output_tokens": tout, "total_tokens": tin + tout,
        "latency_p50_s": round(float(np.percentile(lat, 50)), 3),
        "latency_p95_s": round(float(np.percentile(lat, 95)), 3),
        "latency_mean_s": round(float(lat.mean()), 3),
        "latency_min_s": round(float(lat.min()), 3), "latency_max_s": round(float(lat.max()), 3),
        "estimated_cost": round(cost, 6), "reported_currency": "USD (per log cost_usd column)",
        "cache_hit_cost": round(hit_cost, 6),
        "source_log": os.path.relpath(LOG, ROOT), "model": ";".join(model),
        "notes": "cache-hit latency excluded from P50/P95; request latencies are not summed into wall-clock",
    }]
    with open(os.path.join(HERE, "results", "api_usage_summary.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(summary[0].keys()))
        w.writeheader(); w.writerows(summary)

    # distillation is reported separately, never inside the backend table
    dsel = [r for r in rows if r["tag"] == DISTILL_TAG]
    dok = [r for r in dsel if r["cached"] == "0" and r["status"] == "ok"]
    dlat = np.array([float(r["latency_s"]) for r in dok]) if dok else np.array([0.0])
    with open(os.path.join(HERE, "results", "distillation_cost_separate.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["subject", "api_tag", "successful_uncached_calls", "cache_hits",
                                          "input_tokens", "output_tokens", "latency_p50_s", "latency_p95_s",
                                          "estimated_cost", "notes"])
        w.writeheader()
        w.writerow({"subject": "high_school_geography", "api_tag": DISTILL_TAG,
                    "successful_uncached_calls": len(dok), "cache_hits": len(dsel) - len(dok),
                    "input_tokens": sum(int(r["prompt_tokens"]) for r in dok),
                    "output_tokens": sum(int(r["completion_tokens"]) for r in dok),
                    "latency_p50_s": round(float(np.percentile(dlat, 50)), 3),
                    "latency_p95_s": round(float(np.percentile(dlat, 95)), 3),
                    "estimated_cost": round(sum(float(r["cost_usd"]) for r in dok), 6),
                    "notes": "experience distillation, NOT backend condensation; reported separately"})

    s = summary[0]
    print(f"{TAG}: {s['successful_uncached_calls']} real calls, {s['cache_hits']} cache hits, {s['failed_calls']} failed")
    print(f"  tokens in/out: {tin:,} / {tout:,}")
    print(f"  latency P50 {s['latency_p50_s']} s, P95 {s['latency_p95_s']} s (mean {s['latency_mean_s']})")
    print(f"  logged estimated cost: ${s['estimated_cost']:.4f}  (cache hits ${s['cache_hit_cost']:.4f})")
    print(f"  distillation (separate): {len(dok)} calls, ${sum(float(r['cost_usd']) for r in dok):.4f}")


if __name__ == "__main__":
    main()
