"""Backend HTTP receiver: reads the full body, validates NDJSON entries, returns a small ACK."""
import argparse
import json
import socket
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import common


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    disable_nagle_algorithm = True      # avoid delayed-ACK stalls on small ACK writes
    expected = 1000

    def setup(self):
        super().setup()
        try:
            self.connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except Exception:
            pass

    def log_message(self, *a):
        pass

    def do_POST(self):
        t0 = time.perf_counter_ns()
        n = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(n)
        t1 = time.perf_counter_ns()
        lines = body.split(b"\n")
        if lines and lines[-1] == b"":
            lines = lines[:-1]
        declared = int(self.headers.get("X-Record-Count", str(self.expected)))
        ok = len(lines) == declared and all(x.startswith(b"{") and x.endswith(b"}") for x in lines)
        ack = {
            "received_bytes": len(body),
            "record_count": len(lines),
            "sha256": common.sha256(body),
            "valid": ok,
            "server_read_ms": round((t1 - t0) / 1e6, 3),
        }
        payload = json.dumps(ack).encode()
        self.send_response(200 if ok else 400)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bind", default="10.226.88.2")
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--expect", type=int, default=1000)
    ap.add_argument("--smoke", action="store_true")
    a = ap.parse_args()
    Handler.expected = 10 if a.smoke else a.expect
    srv = ThreadingHTTPServer((a.bind, a.port), Handler)
    srv.daemon_threads = True
    print(f"receiver listening on {a.bind}:{a.port} expect={Handler.expected}", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
