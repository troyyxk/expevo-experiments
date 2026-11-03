#!/usr/bin/env bash
# Assert that the regenerated numbers equal the values used in the paper.
set -uo pipefail
cd "$(dirname "$0")"
PY=${PYTHON:-python3}
fail=0
chk() { if [ "$2" = "1" ]; then printf "  [PASS] %s\n" "$1"; else printf "  [FAIL] %s\n" "$1"; fail=$((fail+1)); fi; }

echo "== V-C resources (Fig. 5) =="
$PY - <<'EOF'
import csv, sys, json
t = {r["setting"]: r for r in csv.DictReader(open("p7/expevo_lifecycle/runs/p10_backend_refinement/tables/refinement_resource_totals.csv"))}
tot = json.load(open("p7/expevo_lifecycle/runs/p7_full100/tables/totals.json"))["totals"]
ok = tot["raw"] == 22080160 and tot["dist"] == 4970488
print(f"  [{'PASS' if ok else 'FAIL'}] payload totals {tot['raw']:,} / {tot['dist']:,}")
sys.exit(0 if ok else 1)
EOF
[ $? -eq 0 ] && r=1 || r=0; chk "raw/distilled totals = 22,080,160 / 4,970,488" $r

echo "== V-D Table II =="
$PY - <<'EOF'
import csv, sys
t = {r["setting"]: r for r in csv.DictReader(open("p7/expevo_lifecycle/runs/p10_backend_refinement/tables/quality_resource_table2.csv"))}
exp = {"Full": ("75.68", "4.970", "24000"), "BM25_60": ("74.41", "1.599", "8332")}
ok = all(t[k]["accuracy_macro_pct"] == a and t[k]["storage_total_mb"] == s and t[k]["indexed_entries_total"] == n
         for k, (a, s, n) in exp.items())
print(f"  [{'PASS' if ok else 'FAIL'}] Full 75.68/4.970/24000, BM25_60 74.41/1.599/8332")
sys.exit(0 if ok else 1)
EOF
[ $? -eq 0 ] && r=1 || r=0; chk "accuracy and resources reproduce" $r

echo "== V-C Fig. 6 simulation =="
$PY - <<'EOF'
import pandas as pd, sys
d = pd.read_csv("fig6_network_simulation/results/per_run.csv")
e1 = d[(d.experiment == "E1") & (d.overhead_bytes == 0)]
e2 = d[(d.experiment == "E2") & (d.overhead_bytes == 0)]
raw100 = e1[e1.M == 100].raw_p95_ms.mean()
red95 = (1 - e2[e2.target_rho_raw == 0.95].dist_p95_ms / e2[e2.target_rho_raw == 0.95].raw_p95_ms).mean() * 100
ok = 50 < raw100 < 57 and 97.5 < red95 < 99.5
print(f"  [{'PASS' if ok else 'FAIL'}] raw P95 @M=100 = {raw100:.1f} ms, reduction @rho=0.95 = {red95:.2f}%")
sys.exit(0 if ok else 1)
EOF
[ $? -eq 0 ] && r=1 || r=0; chk "simulation statistics reproduce" $r

echo "== P9 emulation =="
$PY - <<'EOF'
import pandas as pd, sys
d = pd.read_csv("p9/results/full_20261027_194400/saving_summary.csv")
ok = d.measured_saving_pct.between(77.3, 78.0).all() and len(d) == 5
print(f"  [{'PASS' if ok else 'FAIL'}] measured saving {d.measured_saving_pct.min():.2f}-{d.measured_saving_pct.max():.2f}%")
sys.exit(0 if ok else 1)
EOF
[ $? -eq 0 ] && r=1 || r=0; chk "emulated saving 77.4-77.9%" $r

echo "== TSC cross-client sharing =="
$PY - <<'PYTSC'
import csv, sys
rows = list(csv.DictReader(open("runs/tsc_collaboration/results/accuracy_by_pool.csv")))
acc = {}
for r in rows:
    p = r["policy"]
    if p in ("local_only", "shared_matched", "shared_full"):     # seed-level rows are *_<seed>
        acc[p] = round(float(r["accuracy_percent"]), 2)
want = {"local_only": 80.36, "shared_matched": 80.24, "shared_full": 78.18}
ok = all(abs(acc.get(k, -1) - v) < 0.02 for k, v in want.items())
print(f"  [{'PASS' if ok else 'FAIL'}] local_only {acc.get('local_only')}, "
      f"shared_matched {acc.get('shared_matched')}, shared_full_hetero {acc.get('shared_full_hetero')}")
sys.exit(0 if ok else 1)
PYTSC
[ $? -eq 0 ] && r=1 || r=0; chk "cross-client sharing accuracies reproduce" $r

echo "== TSC heterogeneous coverage =="
$PY - <<'PYHET'
import csv, sys
rows = list(csv.DictReader(open("runs/tsc_collaboration_hetero/results/accuracy_by_pool.csv")))
acc = {}
for r in rows:
    p = r["policy"]
    if p in ("local_only", "shared_matched", "shared_full_hetero"):
        acc[p] = round(float(r["accuracy_percent"]), 2)
want = {"local_only": 81.45, "shared_matched": 80.48, "shared_full_hetero": 80.73}
ok = all(abs(acc.get(k, -1) - v) < 0.02 for k, v in want.items())
print(f"  [{'PASS' if ok else 'FAIL'}] local_only {acc.get('local_only')}, "
      f"shared_matched {acc.get('shared_matched')}, shared_full_hetero {acc.get('shared_full_hetero')}")
sys.exit(0 if ok else 1)
PYHET
[ $? -eq 0 ] && r=1 || r=0; chk "heterogeneous coverage accuracies reproduce" $r

echo
if [ "$fail" -eq 0 ]; then echo "ALL CHECKS PASSED"; else echo "$fail CHECK(S) FAILED"; fi
exit $fail
