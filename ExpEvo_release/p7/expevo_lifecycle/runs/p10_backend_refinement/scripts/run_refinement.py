#!/usr/bin/env python3
"""Phase A/B: reuse the P7 refined repositories, validate lineage, recompute resource metrics.

No LLM calls. Copies the reusable artifacts into this run directory so that P10 is self-contained,
then rebuilds the 4x5 resource matrix from the repository contents (canonical serialization only).
"""
import csv
import hashlib
import json
import os
import shutil
import sys

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
THRESHOLDS = [100, 80, 60, 40]
SETTINGS = [("Full", None)] + [(f"BM25_{t}", t) for t in THRESHOLDS]
RUN_ID = "p10_backend_refinement"


def serialize_item(topic: str, content: str) -> bytes:
    return json.dumps({"topic": topic, "content": content}, ensure_ascii=False,
                      sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def read_jsonl(p):
    with open(p, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def main():
    os.makedirs(os.path.join(OUT, "refined"), exist_ok=True)
    os.makedirs(os.path.join(OUT, "tables"), exist_ok=True)
    print(f"[p10] P7 source: {P7}")
    rows, run_manifest, problems = [], [], []
    totals = {name: {"bytes": 0, "entries": 0, "full_bytes": 0, "full_entries": 0} for name, _ in SETTINGS}

    for s in SUBJECTS:
        full_path = os.path.join(P7, "full_repositories", f"{s}.jsonl")
        full = read_jsonl(full_path)
        full_ids = {e["experience_id"] for e in full}
        full_bytes = sum(len(serialize_item(s, e["text"])) for e in full)
        if len(full) != 6000 or len(full_ids) != 6000:
            problems.append(f"{s}: full repo has {len(full)} items / {len(full_ids)} unique ids")
        full_sha = sha_file(full_path)

        # Full setting row
        rows.append(dict(run_id=RUN_ID, subject=s, setting="Full", threshold="",
                         source_full_sha256=full_sha,
                         repository_sha256=full_sha, full_count=len(full), entry_count=len(full),
                         full_bytes=full_bytes, stored_bytes=full_bytes,
                         storage_mb=f"{full_bytes/1e6:.6f}", normalized_entry_ratio="1.000000",
                         storage_reduction_pct="0.000000", entry_reduction_pct="0.000000",
                         reused_existing="true", refinement_status="identity"))
        totals["Full"]["bytes"] += full_bytes; totals["Full"]["entries"] += len(full)
        totals["Full"]["full_bytes"] += full_bytes; totals["Full"]["full_entries"] += len(full)

        for t in THRESHOLDS:
            name = f"BM25_{t}"
            src = os.path.join(P7, "refined", s, f"bm25_{t}.jsonl")
            if not os.path.exists(src):
                problems.append(f"{s}: missing {src}")
                continue
            items = read_jsonl(src)
            ids = [x["refined_id"] for x in items]
            if len(ids) != len(set(ids)):
                problems.append(f"{s}/{name}: duplicate refined_id")
            lineage, bad = [], 0
            for x in items:
                srcs = x.get("source_experience_ids") or []
                if not srcs:
                    bad += 1
                for sid in srcs:
                    if not sid.startswith(f"exp:{s}/"):
                        problems.append(f"{s}/{name}: foreign source id {sid}")
                    lineage.append(sid)
            cov = len(lineage) == len(set(lineage)) == len(full_ids) and set(lineage) == full_ids
            if not cov:
                problems.append(f"{s}/{name}: lineage is not an exact partition "
                                f"({len(lineage)} links, {len(set(lineage))} unique, {len(full_ids)} expected)")
            if bad:
                problems.append(f"{s}/{name}: {bad} items without source_experience_ids")
            stored = sum(len(serialize_item(s, x["text"])) for x in items)
            # copy for self-containment
            dst_dir = os.path.join(OUT, "refined", s)
            os.makedirs(dst_dir, exist_ok=True)
            dst = os.path.join(dst_dir, f"bm25_{t}.jsonl")
            if not os.path.exists(dst):
                shutil.copy2(src, dst)
            rows.append(dict(run_id=RUN_ID, subject=s, setting=name, threshold=t,
                             source_full_sha256=full_sha, repository_sha256=sha_file(src),
                             full_count=len(full), entry_count=len(items),
                             full_bytes=full_bytes, stored_bytes=stored,
                             storage_mb=f"{stored/1e6:.6f}",
                             normalized_entry_ratio=f"{len(items)/len(full):.6f}",
                             storage_reduction_pct=f"{100*(1-stored/full_bytes):.6f}",
                             entry_reduction_pct=f"{100*(1-len(items)/len(full)):.6f}",
                             reused_existing="true", refinement_status="reused_from_p7"))
            totals[name]["bytes"] += stored; totals[name]["entries"] += len(items)
            totals[name]["full_bytes"] += full_bytes; totals[name]["full_entries"] += len(full)
            run_manifest.append(dict(subject=s, setting=name, threshold=t, reused=True,
                                     source_path=src, copied_to=dst, repository_sha256=sha_file(src)))

    if problems:
        print("[p10] BLOCKERS:")
        for p in problems:
            print("  -", p)
        sys.exit(1)

    with open(os.path.join(OUT, "tables", "refinement_resource_by_subject.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    with open(os.path.join(OUT, "refinement_run_manifest.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(run_manifest[0].keys())); w.writeheader(); w.writerows(run_manifest)

    with open(os.path.join(OUT, "tables", "refinement_resource_totals.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["setting", "total_storage_bytes", "total_storage_mb", "total_entries",
                    "storage_reduction_pct", "entry_reduction_pct"])
        base_b, base_n = totals["Full"]["bytes"], totals["Full"]["entries"]
        for name, _ in SETTINGS:
            v = totals[name]
            w.writerow([name, v["bytes"], f"{v['bytes']/1e6:.6f}", v["entries"],
                        f"{100*(1-v['bytes']/base_b):.6f}", f"{100*(1-v['entries']/base_n):.6f}"])

    manifest = {
        "run_id": RUN_ID,
        "source_run": P7,
        "subjects": SUBJECTS,
        "settings": [n for n, _ in SETTINGS],
        "thresholds": THRESHOLDS,
        "full_counts": {s: 6000 for s in SUBJECTS},
        "full_bytes_total": totals["Full"]["bytes"],
        "full_sha256": {s: sha_file(os.path.join(P7, "full_repositories", f"{s}.jsonl")) for s in SUBJECTS},
        "heldout_sha256": {s: sha_file(os.path.join(P7, "heldout", f"{s}.jsonl")) for s in SUBJECTS},
        "refinement_reused": len(run_manifest),
        "refinement_new": 0,
        "serializer": "scripts/run_refinement.py:serialize_item (identical to src/common.py)",
        "bm25": {"implementation": "rank_bm25.BM25Okapi", "k1": 1.5, "b": 0.75,
                 "note": "directed similarity matrix, raw scores, no rescaling"},
    }
    json.dump(manifest, open(os.path.join(OUT, "input_manifest.json"), "w"), indent=1)

    print(f"[p10] validated {len(rows)} subject-setting pairs, {len(run_manifest)} refined repos reused")
    print("\nsetting  storage_MB  entries  storage_red%  entry_red%")
    for name, _ in SETTINGS:
        v = totals[name]
        print(f"{name:<9} {v['bytes']/1e6:9.4f} {v['entries']:7d} {100*(1-v['bytes']/base_b):12.2f} {100*(1-v['entries']/base_n):11.2f}")


if __name__ == "__main__":
    main()
