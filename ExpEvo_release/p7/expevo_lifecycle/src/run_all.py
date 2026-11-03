"""Orchestrate all stages for one config."""
import argparse
import os
import subprocess
import sys
import time

import copy

from .common import load_config, now_iso, read_json, write_json


def redacted(cfg):
    c = copy.deepcopy(cfg)
    if isinstance(c.get("api"), dict) and "api_key" in c["api"]:
        c["api"]["api_key"] = "<redacted>"
    return c


def run(module, config, extra=()):
    t0 = time.time()
    print(f"\n=== {module} ===", flush=True)
    cmd = [sys.executable, "-m", f"src.{module}", "--config", config, *extra]
    subprocess.run(cmd, check=True)
    print(f"=== {module} done in {time.time() - t0:.0f}s ===", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--mode", default="smoke", choices=["smoke", "pilot", "full"])
    ap.add_argument("--skip-interactions", action="store_true")
    args = ap.parse_args()

    cfg = load_config(args.config)
    if args.mode == "full" and "full" not in args.config:
        raise SystemExit("refusing to run a non-full config in full mode")
    if args.mode != "full" and "full" in args.config:
        print("WARNING: full config used without --mode full; budget guards still apply")

    stages = ["prepare_mmlu", "run_interactions", "distill", "route_and_store",
              "refine", "metrics", "plots", "validate"]
    if args.skip_interactions:
        stages = stages[3:]
    t0 = time.time()
    for st in stages:
        run(st, args.config)

    run_dir = os.path.abspath(os.path.join(cfg["runtime"]["runs_dir"], cfg["run_id"]))
    parts = {}
    for f in sorted(os.listdir(run_dir)):
        if f.startswith("manifest_") and f.endswith(".json"):
            parts[f] = read_json(os.path.join(run_dir, f))
    write_json(os.path.join(run_dir, "manifest.json"), {
        "run_id": cfg["run_id"],
        "config": redacted(cfg),
        "stages": parts,
        "started_by": "run_all",
        "finished_at": now_iso(),
        "wall_seconds": round(time.time() - t0, 1),
    })
    print(f"\nALL STAGES DONE in {time.time() - t0:.0f}s -> {run_dir}")


if __name__ == "__main__":
    main()
