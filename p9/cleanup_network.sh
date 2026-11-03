#!/usr/bin/env bash
# Remove the experiment topology and stray processes. Safe to run repeatedly.
set -uo pipefail
CLIENT=${CLIENT:-expevo_client}
SERVER=${SERVER:-expevo_server}
pkill -f "p9/receiver.py" 2>/dev/null || true
pkill -f "iperf3 -s -B 10.226.88" 2>/dev/null || true
for ns in "$CLIENT" "$SERVER"; do
  if ip netns list 2>/dev/null | awk '{print $1}' | grep -qx "$ns"; then
    ip netns del "$ns" || true
  fi
done
echo "cleaned netns: $CLIENT $SERVER"
