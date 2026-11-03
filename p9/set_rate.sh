#!/usr/bin/env bash
set -euo pipefail
CLIENT=${CLIENT:-expevo_client}
VETH_C=${VETH_C:-veth_ex_c}
RATE=${1:?usage: set_rate.sh <mbps>}
ip netns exec "$CLIENT" tc qdisc replace dev "$VETH_C" root tbf rate "${RATE}mbit" burst 32kb latency 100ms
ip netns exec "$CLIENT" tc -s qdisc show dev "$VETH_C" | head -2
