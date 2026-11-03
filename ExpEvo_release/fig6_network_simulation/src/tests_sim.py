#!/usr/bin/env python3
"""Correctness tests for the FCFS uplink simulator (task book section 6)."""
import os, sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sim_uploads import load_pairs, poisson_arrivals, fcfs, run_one

FAIL = []
def check(cond, msg):
    print(("[PASS] " if cond else "[FAIL] ") + msg)
    if not cond:
        FAIL.append(msg)

raw, dis = load_pairs()

# 1. single event, no queue
s = 8.0 * (1000 + 0) / 1e6
f, q, l = fcfs(np.array([0.0]), np.array([s]))
check(abs(l[0] * 1e3 - 8 * 1000 / 1e3) < 1e-9 and q[0] == 0,
      f"single event: L = 8D/R exactly ({l[0]*1e3:.4f} ms)")

# 2. no contention -> queue delay 0
a = np.array([0.0, 10.0, 20.0]); svc = np.array([0.001, 0.001, 0.001])
f, q, l = fcfs(a, svc)
check(np.allclose(q, 0), "widely spaced arrivals give zero queueing delay")

# 3. paired fairness: raw and distilled share arrivals and payload indices
r = run_one(raw, dis, 2000, 50.0, 1.0, seed=7)
a_ind = poisson_arrivals(2000, 50.0, 7)
perm = np.random.default_rng(7 + 104729).permutation(len(raw))[:2000]
_, _, l_raw = fcfs(a_ind, 8.0 * raw[perm] / 1e6)
_, _, l_dis = fcfs(a_ind, 8.0 * dis[perm] / 1e6)
check(abs(np.percentile(l_raw, 95) * 1e3 - r["raw_p95_ms"]) < 1e-9 and
      abs(np.percentile(l_dis, 95) * 1e3 - r["dist_p95_ms"]) < 1e-9,
      "raw and distilled share one arrival sequence and one payload assignment")

# 4. FIFO invariants over a congested run
a = poisson_arrivals(20000, 120.0, seed=3)
svc = 8.0 * raw[np.random.default_rng(3).permutation(len(raw))[:20000]] / 1e6
f, q, l = fcfs(a, svc)
b = a + q
check(np.all(f >= b - 1e-12) and np.all(b >= a - 1e-12), "F >= B >= A for every event")
check(np.all(np.diff(b) >= 0) and np.all(np.diff(f) > 0), "server is sequential (no overlap)")
check(np.all(q >= -1e-12), "queueing delay is non-negative")

# 5. conservation of the payload pool
check(len(raw) == 24000 and abs(raw.sum() - 22_080_160) < 1 and abs(dis.sum() - 4_970_488) < 1,
      "24,000 unique pairs, totals match the paper (22.080/4.970 MB)")

# 6. utilisation tracks the target load
for rho in (0.30, 0.85):
    cap = 1e6 / (8 * raw.mean())
    r = run_one(raw, dis, 24000, rho * cap, 1.0, seed=11)
    check(abs(r["raw_utilization"] - rho) < 0.03,
          f"measured utilisation {r['raw_utilization']:.3f} tracks target rho={rho}")

# 7. hand-computed three-event case
a = np.array([0.0, 1.0, 2.0]); svc = np.array([4.0, 4.0, 4.0])
f, q, l = fcfs(a, svc)
check(np.allclose(f, [4, 8, 12]) and np.allclose(q, [0, 3, 6]) and np.allclose(l, [4, 7, 10]),
      "three-event hand calculation matches (finish 4/8/12, queue 0/3/6)")

# 8. reproducibility of aggregate statistics
x = run_one(raw, dis, 5000, 80.0, 1.0, seed=42)
y = run_one(raw, dis, 5000, 80.0, 1.0, seed=42)
check(x["raw_p95_ms"] == y["raw_p95_ms"] and x["dist_mean_ms"] == y["dist_mean_ms"],
      "identical seed reproduces identical statistics")

print(f"\n{len(FAIL)} failure(s)")
sys.exit(1 if FAIL else 0)
