#!/usr/bin/env python3
"""Diagnose the non-monotonic storage at the lowest threshold.

For every subject and threshold this splits the stored repository into
  * condensed entries  (groups with >1 source that fitted the 3,500-word budget)
  * retained singletons (true singletons + members of groups rejected as too large)
and records the bytes each part contributes. The rejected-group count comes from the P7 run's own
refinement_metrics.csv, so nothing is re-derived with a different policy.
"""
import csv, json, os, statistics as st

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
TH = [100, 80, 60, 40]


def ser(topic, content):
    return json.dumps({"topic": topic, "content": content}, ensure_ascii=False,
                      sort_keys=True, separators=(",", ":")).encode("utf-8")


def read(p):
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]


metrics = {(r["subject"], int(r["threshold"])): r
           for r in csv.DictReader(open(f"{P7}/tables/refinement_metrics.csv"))}
rows = []
for s in SUBJECTS:
    full = read(f"{P7}/full_repositories/{s}.jsonl")
    src_bytes = {e["experience_id"]: len(ser(s, e["text"])) for e in full}
    for t in TH:
        items = read(f"{P7}/refined/{s}/bm25_{t}.jsonl")
        merged = [x for x in items if len(x["source_experience_ids"]) > 1]
        single = [x for x in items if len(x["source_experience_ids"]) == 1]
        bm = sum(len(ser(s, x["text"])) for x in merged)
        bs = sum(len(ser(s, x["text"])) for x in single)
        rows.append({"subject": s, "threshold": t, "entries": len(items),
                     "condensed_groups": len(merged), "retained_singletons": len(single),
                     "sources_in_condensed": sum(len(x["source_experience_ids"]) for x in merged),
                     "overflow_items_reported": int(metrics[(s, t)]["overflow_items"]),
                     "bytes_condensed": bm, "bytes_retained": bs,
                     "avg_condensed_bytes": round(bm / len(merged), 1) if merged else 0,
                     "avg_source_bytes": round(st.mean(src_bytes.values()), 1),
                     "stored_bytes": bm + bs})
os.makedirs(f"{OUT}/tables", exist_ok=True)
with open(f"{OUT}/tables/tau40_diagnosis.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
print(f"{'subject':<24}{'tau':>4}{'entries':>8}{'cond':>6}{'singl':>7}{'overflow':>9}{'MB_cond':>10}{'MB_ret':>9}")
for r in rows:
    print(f"{r['subject']:<24}{r['threshold']:>4}{r['entries']:>8}{r['condensed_groups']:>6}"
          f"{r['retained_singletons']:>7}{r['overflow_items_reported']:>9}"
          f"{r['bytes_condensed']/1e6:>10.3f}{r['bytes_retained']/1e6:>9.3f}")
print(f"\nwrote {OUT}/tables/tau40_diagnosis.csv")
