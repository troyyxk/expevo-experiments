#!/usr/bin/env python3
"""Derive the paired payload table from the P7 run, with the paper's serialization.

No LLM calls. The output is the single input to the queue simulation.
"""
import csv, hashlib, json, os, sys

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


P7 = _p7_run()
OUT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SUBJECTS = ["international_law", "college_medicine", "college_biology", "high_school_geography"]


def serialize_item(topic, content):
    return json.dumps({"topic": topic, "content": content}, ensure_ascii=False,
                      sort_keys=True, separators=(",", ":")).encode("utf-8")


def main():
    rows = []
    for s in SUBJECTS:
        exps = {}
        for line in open(f"{P7}/experiences/{s}.jsonl", encoding="utf-8"):
            x = json.loads(line)
            exps[x["source_episode_id"]] = x["text"]
        for line in open(f"{P7}/episodes/{s}.jsonl", encoding="utf-8"):
            e = json.loads(line)
            eid = e["episode_id"]
            if eid not in exps:
                sys.exit(f"[FAIL] {eid}: no distilled experience")
            rows.append({"event_id": eid, "subject": s,
                         "raw_bytes": len(serialize_item(s, e["episode_content"])),
                         "distilled_bytes": len(serialize_item(s, exps[eid]))})
    ids = [r["event_id"] for r in rows]
    assert len(rows) == 24000 and len(set(ids)) == 24000, (len(rows), len(set(ids)))
    raw = sum(r["raw_bytes"] for r in rows)
    dis = sum(r["distilled_bytes"] for r in rows)
    assert raw == 22080160 and dis == 4970488, (raw, dis)
    os.makedirs(f"{OUT}/data", exist_ok=True)
    path = f"{OUT}/data/payload_pairs.csv"
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["event_id", "subject", "raw_bytes", "distilled_bytes"])
        w.writeheader()
        for i, r in enumerate(rows, 1):
            w.writerow({"event_id": i, "subject": r["subject"],
                        "raw_bytes": r["raw_bytes"], "distilled_bytes": r["distilled_bytes"]})
    sha = hashlib.sha256(open(path, "rb").read()).hexdigest()
    print(f"wrote {path}: {len(rows)} pairs, raw={raw:,} B, distilled={dis:,} B "
          f"({100*(1-dis/raw):.2f}% reduction), sha256={sha[:16]}")


if __name__ == "__main__":
    main()
