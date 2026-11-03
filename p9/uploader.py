"""Frontend HTTP uploader: sends one batch per POST over a persistent connection and times it."""
import argparse
import http.client
import json
import os
import socket
import time

import common


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="10.226.88.2")
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--mode", choices=["raw", "distilled"], required=True)
    ap.add_argument("--rate", type=int, required=True)
    ap.add_argument("--trials", type=int, default=5)
    ap.add_argument("--run-dir", default=common.RUN_DEFAULT)
    ap.add_argument("--out", required=True)
    ap.add_argument("--smoke", action="store_true", help="40 items per subject, 1 trial, 1 post")
    a = ap.parse_args()

    pairs = common.load_pairs(a.run_dir)
    jobs = []   # (subject, batch_id, canonical_bytes, body, sha)
    if a.smoke:
        for s in common.SUBJECTS:
            chunk = pairs[s][:10]
            items = [c[1] if a.mode == "raw" else c[2] for c in chunk]
            body = common.body_of(items)
            jobs.append((s, 0, sum(map(len, items)), body, common.sha256(body)))
        trials = 1
    else:
        for s in common.SUBJECTS:
            for b in common.make_batches(pairs[s]):
                items = b["raw_items"] if a.mode == "raw" else b["dist_items"]
                body = common.body_of(items)
                jobs.append((s, b["batch_id"], sum(map(len, items)), body, common.sha256(body)))
        trials = a.trials

    new = not os.path.exists(a.out)
    fh = open(a.out, "a", encoding="utf-8")
    if new:
        fh.write("rate_mbps,mode,trial,subject,batch_id,record_count,canonical_payload_bytes,"
                 "http_body_bytes,measured_batch_ms,server_read_ms,ack_ok\n")
        fh.flush()

    conn = http.client.HTTPConnection(a.host, a.port, timeout=180)
    conn.connect()
    try:
        conn.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    except Exception:
        pass
    for trial in range(1, trials + 1):
        # warmup on the same connection (one valid 1-record request, not measured)
        warm = jobs[0][3].split(b"\n")[0] + b"\n"
        conn.request("POST", "/upload", warm, {"Content-Type": "application/x-ndjson",
                                               "X-Record-Count": "1", "Accept-Encoding": "identity"})
        wresp = conn.getresponse(); wresp.read()
        if wresp.status != 200:
            raise SystemExit(f"warmup failed: HTTP {wresp.status}")
        for subj, bid, canon, body, digest in jobs:
            nrec = body.count(b"\n")
            t0 = time.perf_counter_ns()
            conn.request("POST", "/upload", body, {"Content-Type": "application/x-ndjson",
                                                   "X-Record-Count": str(nrec),
                                                   "Accept-Encoding": "identity"})
            resp = conn.getresponse()
            data = resp.read()
            t1 = time.perf_counter_ns()
            ack = json.loads(data)
            ok = (resp.status == 200 and ack["received_bytes"] == len(body)
                  and ack["sha256"] == digest and ack["record_count"] == nrec)
            if not ok:
                raise SystemExit(f"ACK mismatch: {ack} vs body {len(body)} sha {digest}")
            fh.write(f"{a.rate},{a.mode},{trial},{subj},{bid},{nrec},{canon},{len(body)},"
                     f"{(t1 - t0) / 1e6:.3f},{ack.get('server_read_ms', '')},1\n")
            fh.flush()
    fh.close()
    print(f"done {a.mode} @ {a.rate} Mbps -> {a.out}", flush=True)


if __name__ == "__main__":
    main()
