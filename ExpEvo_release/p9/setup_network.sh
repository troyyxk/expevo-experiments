#!/usr/bin/env bash
# Idempotent netns/veth/tc setup for the P9 upload experiment. Run as root.
set -euo pipefail
CLIENT=${CLIENT:-expevo_client}
SERVER=${SERVER:-expevo_server}
VETH_C=${VETH_C:-veth_ex_c}
VETH_S=${VETH_S:-veth_ex_s}
CIP=${CIP:-10.226.88.1}
SIP=${SIP:-10.226.88.2}
RATE=${1:-10}

cleanup() { bash "$(dirname "$0")/cleanup_network.sh" >/dev/null 2>&1 || true; }
cleanup

ip netns add "$CLIENT"
ip netns add "$SERVER"
ip link add "$VETH_C" type veth peer name "$VETH_S"
ip link set "$VETH_C" netns "$CLIENT"
ip link set "$VETH_S" netns "$SERVER"
ip -n "$CLIENT" addr add "$CIP/24" dev "$VETH_C"
ip -n "$SERVER" addr add "$SIP/24" dev "$VETH_S"
ip -n "$CLIENT" link set lo up
ip -n "$SERVER" link set lo up
ip -n "$CLIENT" link set "$VETH_C" up
ip -n "$SERVER" link set "$VETH_S" up

ip netns exec "$CLIENT" tc qdisc replace dev "$VETH_C" root tbf rate "${RATE}mbit" burst 32kb latency 100ms
echo "topology up: $CLIENT($CIP) <-> $SERVER($SIP), shaped ${RATE}mbit on $CLIENT/$VETH_C"
ip netns exec "$CLIENT" tc -s qdisc show dev "$VETH_C" | head -2
