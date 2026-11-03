#!/usr/bin/env python3
"""Trace-driven FCFS uplink simulation with measured per-event payload sizes.

Model: M logical clients -> one shared uplink (constant rate R) -> shared backend.
Every event carries a paired (raw, distilled) payload; both representations see the same arrival
times, client assignment, rate and seed. Service time is 8*(D+H)/R.
"""
import argparse, json, os, platform, sys
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_pairs(path=None):
    df = pd.read_csv(path or os.path.join(ROOT, "data", "payload_pairs.csv"))
    return df["raw_bytes"].to_numpy(float), df["distilled_bytes"].to_numpy(float)


def poisson_arrivals(n, lam_total, seed):
    rng = np.random.default_rng(seed)
    return np.cumsum(rng.exponential(1.0 / lam_total, n))


def fcfs(arrivals, service):
    """Single FIFO server. Returns finish times and per-event (queue delay, sojourn time)."""
    n = len(arrivals)
    start = np.empty(n)
    finish = np.empty(n)
    prev = 0.0
    for i in range(n):
        s = arrivals[i] if arrivals[i] > prev else prev
        start[i] = s
        prev = s + service[i]
        finish[i] = prev
    return finish, start - arrivals, finish - arrivals


def distribution(l):
    return {"mean_ms": 1e3 * l.mean(), "p50_ms": 1e3 * np.percentile(l, 50),
            "p95_ms": 1e3 * np.percentile(l, 95), "p99_ms": 1e3 * np.percentile(l, 99)}


def run_one(raw, dis, n_events, lam_total, rate_mbps, seed, overhead=0.0, warmup_frac=0.0):
    a = poisson_arrivals(n_events, lam_total, seed)
    perm = np.random.default_rng(seed + 104729).permutation(len(raw))[:n_events]
    out = {"n_events": n_events, "lam_total": lam_total, "rate_mbps": rate_mbps, "seed": seed,
           "overhead_bytes": overhead, "warmup_frac": warmup_frac}
    k0 = int(n_events * warmup_frac)
    for mode, payload in (("raw", raw[perm]), ("dist", dis[perm])):
        s = 8.0 * (payload + overhead) / (rate_mbps * 1e6)
        finish, q, l = fcfs(a, s)
        out[f"{mode}_offered_load"] = float(lam_total * s.mean())
        out[f"{mode}_utilization"] = float(s.sum() / (finish[-1] - a[0]))
        out[f"{mode}_mean_queue_ms"] = float(1e3 * q[k0:].mean())
        for k, v in distribution(l[k0:]).items():
            out[f"{mode}_{k}"] = float(v)
    return out


SCENARIOS = {
    "E1": [{"M": m} for m in (10, 20, 50, 100)],
    "E2": [{"M": 50, "rho_raw": r} for r in (0.3, 0.6, 0.85, 0.95)],
    "E3": [{"M": 50, "rate": r, "overhead": h} for r in (1.0, 5.0) for h in (0.0, 60.0)],
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--experiments", nargs="+", default=["E1", "E2", "E3"])
    ap.add_argument("--seeds", type=int, default=10)
    ap.add_argument("--events", type=int, default=24000)
    ap.add_argument("--rate", type=float, default=1.0)
    ap.add_argument("--lambda-client", type=float, default=1.0)
    ap.add_argument("--overhead", type=float, default=0.0, help="E1/E2 protocol overhead in bytes")
    ap.add_argument("--warmup-frac", type=float, default=0.0)
    ap.add_argument("--out", default=os.path.join(ROOT, "results"))
    a = ap.parse_args()
    raw, dis = load_pairs()
    cap_raw = 1e6 / (8 * (raw.mean() + a.overhead))
    rows = []
    for exp in a.experiments:
        for sc in SCENARIOS[exp]:
            M = sc["M"]
            lam = sc.get("rho_raw", None)
            lam_total = lam * cap_raw if lam is not None else M * a.lambda_client
            rate = sc.get("rate", a.rate)
            overhead = sc.get("overhead", a.overhead)
            for seed in range(a.seeds):
                r = run_one(raw, dis, a.events, lam_total, rate, seed, overhead, a.warmup_frac)
                r.update({"experiment": exp, "M": M, "target_rho_raw": lam if lam is not None else "",
                          "lambda_client": lam_total / M})
                rows.append(r)
    df = pd.DataFrame(rows)
    os.makedirs(a.out, exist_ok=True)
    df.to_csv(os.path.join(a.out, "per_run.csv"), index=False)

    keys = ["experiment", "M", "target_rho_raw", "rate_mbps", "overhead_bytes"]
    metrics = [c for c in df.columns if c.endswith("_ms") or c.endswith("_utilization")
               or c.endswith("_offered_load")]
    summ = df.groupby(keys, dropna=False)[metrics].agg(["mean", "std"]).round(4)
    summ.columns = [f"{m}_{s}" for m, s in summ.columns]
    summ = summ.reset_index()
    summ.to_csv(os.path.join(a.out, "summary.csv"), index=False)

    cfg = {"events_per_run": a.events, "seeds": a.seeds, "experiments": a.experiments,
           "lambda_client_default": a.lambda_client, "rate_mbps_default": a.rate,
           "overhead_default_bytes": a.overhead, "warmup_frac": a.warmup_frac,
           "service_model": "S = 8*(D+H)/R", "queue": "single FIFO, constant rate",
           "arrivals": "Poisson per scenario at aggregate rate lam_total",
           "raw_service_capacity_eps": cap_raw, "python": platform.python_version(),
           "numpy": np.__version__, "pandas": pd.__version__,
           "payload_csv_sha256": __import__("hashlib").sha256(
               open(os.path.join(ROOT, "data", "payload_pairs.csv"), "rb").read()).hexdigest()}
    json.dump(cfg, open(os.path.join(a.out, "config.json"), "w"), indent=1)

    print(summ[[c for c in summ.columns if c in keys or c.endswith("p95_ms_mean")
                or c.endswith("utilization_mean")]].round(2).to_string(index=False))


if __name__ == "__main__":
    main()
