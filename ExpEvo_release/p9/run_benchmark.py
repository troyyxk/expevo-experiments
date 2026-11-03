"""Driver (run as root on the target host): tc shaping -> iperf3 calibration -> upload trials."""
import argparse, json, math, os, re, shutil, socket, subprocess, sys, time

def _release_root(start=None):
    """Locate the release root (the directory that contains p7/expevo_lifecycle/runs)."""
    d = os.path.dirname(os.path.abspath(start or __file__))
    for _ in range(8):
        if os.path.isdir(os.path.join(d, "p7", "expevo_lifecycle", "runs")):
            return d
        nd = os.path.dirname(d)
        if nd == d:
            break
        d = nd
    return None


def _p7_run(name="p7_full100"):
    """P7 run directory: EXPEVO_P7_RUN overrides, otherwise resolved inside the release."""
    env = os.environ.get("EXPEVO_P7_RUN")
    if env and os.path.isdir(env):
        return env
    root = _release_root()
    if root:
        p = os.path.join(root, "p7", "expevo_lifecycle", "runs", name)
        if os.path.isdir(p):
            return p
    return None


P9 = os.path.dirname(os.path.abspath(__file__))


def sh(cmd, **kw):
    return subprocess.run(cmd, shell=isinstance(cmd, str), capture_output=True, text=True, **kw)


def nsx(ns, cmd):
    return ["ip", "netns", "exec", ns] + cmd


def wait_port(ns, ip, port, timeout=20):
    t0 = time.time()
    while time.time() - t0 < timeout:
        r = subprocess.run(nsx(ns, ["python3", "-c",
              f"import socket,sys\ns=socket.socket();s.settimeout(1)\ntry:\n s.connect(('{ip}',{port}));sys.exit(0)\nexcept Exception:\n sys.exit(1)"]),
              capture_output=True)
        if r.returncode == 0:
            return True
        time.sleep(0.3)
    return False


def tc_stats(ns, dev):
    out = sh(nsx(ns, ["tc", "-s", "qdisc", "show", "dev", dev])).stdout
    m = re.search(r"Sent (\d+) bytes (\d+) pkt \(dropped (\d+), overlimits (\d+)", out)
    return {"sent_bytes": int(m.group(1)), "sent_pkts": int(m.group(2)),
            "dropped": int(m.group(3)), "overlimits": int(m.group(4))} if m else {}


def burst_kb(mbps):
    """Keep the token bucket to ~2 ms of link time so TBF slack cannot swallow a short batch."""
    return max(2, int(math.ceil(mbps * 0.25)))


def set_rate(ns, dev, mbps):
    b = f"{burst_kb(mbps)}kb"
    sh(nsx(ns, ["tc", "qdisc", "replace", "dev", dev, "root", "tbf",
                "rate", f"{mbps}mbit", "burst", b, "latency", "100ms"]))
    return b


def calibrate(ns_srv, ns_cli, ip, port, secs):
    srv = subprocess.Popen(nsx(ns_srv, ["iperf3", "-s", "-1", "-B", ip, "-p", str(port)]),
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(0.6)
    r = sh(nsx(ns_cli, ["iperf3", "-c", ip, "-p", str(port), "-t", str(secs), "-J"]))
    try:
        srv.wait(timeout=secs + 10)
    except Exception:
        srv.kill()
    if r.returncode != 0:
        return {"ok": False, "stderr": r.stderr[-400:]}
    j = json.loads(r.stdout)
    return {"ok": True,
            "sender_mbps": round(j["end"]["sum_sent"]["bits_per_second"] / 1e6, 3),
            "receiver_mbps": round(j["end"]["sum_received"]["bits_per_second"] / 1e6, 3),
            "retransmits": j["end"]["sum_sent"].get("retransmits"),
            "seconds": secs}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--p9-dir", default=P9)
    default_run = next((d for d in [
        _p7_run(),
        "/home/xingkun/exp_scale_handoff/p7/expevo_lifecycle/runs/p7_full100"] if os.path.isdir(os.path.join(d, "episodes"))), None)
    ap.add_argument("--run-dir", default=default_run)
    ap.add_argument("--out", required=True)
    ap.add_argument("--ns-client", default="expevo_client")
    ap.add_argument("--ns-server", default="expevo_server")
    ap.add_argument("--dev", default="veth_ex_c")
    ap.add_argument("--server-ip", default="10.226.88.2")
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--iperf-port", type=int, default=5201)
    ap.add_argument("--rates", default="1,5,10,20,50")
    ap.add_argument("--trials", type=int, default=5)
    ap.add_argument("--iperf-seconds", type=int, default=15)
    ap.add_argument("--chown", default="1007:1007")
    ap.add_argument("--smoke", action="store_true")
    a = ap.parse_args()

    rates = [int(x) for x in a.rates.split(",")]
    trials = 1 if a.smoke else a.trials
    os.makedirs(a.out, exist_ok=True)
    batches_csv = os.path.join(a.out, "batches.csv")
    calib_csv = os.path.join(a.out, "calibration.csv")
    meta = {"started": time.strftime("%Y-%m-%d %H:%M:%S"), "rates": rates, "trials": trials,
            "batch_size": 10 if a.smoke else 1000, "smoke": a.smoke,
            "tc": "tbf rate <R>mbit burst max(2KB, R*0.25KB) latency 100ms", "dev": a.dev,
            "namespaces": [a.ns_client, a.ns_server], "server_ip": a.server_ip,
            "python": sys.version.split()[0], "host": socket.gethostname()}
    json.dump(meta, open(os.path.join(a.out, "meta.json"), "w"), indent=1)

    # pick a free-ish port check then start receiver
    recv_log = open(os.path.join(a.out, "receiver.log"), "w")
    recv = subprocess.Popen(nsx(a.ns_server, ["python3", os.path.join(a.p9_dir, "receiver.py"),
                                              "--bind", a.server_ip, "--port", str(a.port)]),
                            stdout=recv_log, stderr=subprocess.STDOUT)
    try:
        if not wait_port(a.ns_client, a.server_ip, a.port):
            raise SystemExit("receiver did not come up")
        with open(calib_csv, "w") as cf:
            cf.write("rate_mbps,configured_mbps,burst,ok,sender_mbps,receiver_mbps,retransmits,deviation_pct,"
                     "tc_dropped,tc_overlimits,seconds\n"); cf.flush()
            for i, rate in enumerate(rates):
                burst = set_rate(a.ns_client, a.dev, rate)
                time.sleep(0.3)
                st = tc_stats(a.ns_client, a.dev)
                print(f"[tc] {rate} Mbps burst={burst} slack={burst[:-1]}KB/{rate}Mbps="
                      f"{float(burst[:-2])*8/(rate*1000)*1000:.1f} ms", flush=True)
                cal = calibrate(a.ns_server, a.ns_client, a.server_ip, a.iperf_port, a.iperf_seconds)
                dev = abs(cal.get("receiver_mbps", 0) - rate) / rate * 100 if cal["ok"] else ""
                cf.write(f"{rate},{rate},{burst},{int(cal['ok'])},{cal.get('sender_mbps','')},{cal.get('receiver_mbps','')},"
                         f"{cal.get('retransmits','')},{round(dev,2) if dev != '' else ''},"
                         f"{st.get('dropped','')},{st.get('overlimits','')},{a.iperf_seconds}\n"); cf.flush()
                print(f"[calib] {rate} Mbps -> {cal.get('receiver_mbps')} Mbps "
                      f"({dev:.1f}% off)" if cal["ok"] else f"[calib] {rate} FAILED {cal}", flush=True)
                modes = ["raw", "distilled"] if i % 2 == 0 else ["distilled", "raw"]
                for mode in modes:
                    print(f"[run] {rate} Mbps {mode} x{trials}", flush=True)
                    r = sh(nsx(a.ns_client, ["python3", os.path.join(a.p9_dir, "uploader.py"),
                                             "--host", a.server_ip, "--port", str(a.port),
                                             "--mode", mode, "--rate", str(rate), "--trials", str(trials),
                                             "--run-dir", a.run_dir, "--out", batches_csv]
                               + (["--smoke"] if a.smoke else [])), timeout=3600)
                    if r.returncode != 0:
                        open(os.path.join(a.out, "uploader_error.log"), "a").write(
                            f"{rate} {mode}\nSTDOUT:{r.stdout}\nSTDERR:{r.stderr}\n")
                        raise SystemExit(f"uploader failed at {rate} Mbps {mode}: {r.stderr[-300:]}")
        set_rate(a.ns_client, a.dev, 1000)  # leave the link unshaped-ish
    finally:
        recv.terminate()
        try:
            recv.wait(timeout=5)
        except Exception:
            recv.kill()
    meta["finished"] = time.strftime("%Y-%m-%d %H:%M:%S")
    json.dump(meta, open(os.path.join(a.out, "meta.json"), "w"), indent=1)
    if a.chown:
        sh(["chown", "-R", a.chown, a.out])
    print("benchmark complete ->", a.out, flush=True)


if __name__ == "__main__":
    main()
