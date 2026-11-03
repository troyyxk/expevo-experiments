#!/usr/bin/env bash
# Runs on the target host as root. Usage: remote_run.sh {smoke|full}
set -euo pipefail
BASE=/home/xingkun/exp_scale_handoff
P9=$BASE/p9
MODE=${1:-smoke}
bash "$P9/cleanup_network.sh" || true
bash "$P9/setup_network.sh" 10
if [ "$MODE" = "smoke" ]; then
  python3 "$P9/run_benchmark.py" --out "$P9/results/smoke_$(date +%Y%m%d_%H%M%S)" \
      --rates 10 --trials 1 --iperf-seconds 5 --smoke
else
  python3 "$P9/run_benchmark.py" --out "$P9/results/full_$(date +%Y%m%d_%H%M%S)" \
      --rates 1,5,10,20,50 --trials 5 --iperf-seconds 15
fi
bash "$P9/cleanup_network.sh" || true
