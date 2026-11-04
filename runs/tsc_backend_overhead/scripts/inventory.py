#!/usr/bin/env python3
"""Phase A: verify the frozen inputs, freeze the 55 query keys, record hashes and hardware."""
import hashlib, json, os, platform, subprocess, sys
from collections import Counter

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(os.path.dirname(HERE))
P7 = os.path.join(ROOT, "p7", "expevo_lifecycle", "runs", "p7_full100")
P10 = os.path.join(ROOT, "p7", "expevo_lifecycle", "runs", "p10_backend_refinement")
SUBJECT = "high_school_geography"


def read_jsonl(p):
    with open(p, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def sha_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def sha_ids(ids):
    h = hashlib.sha256()
    for i in ids:
        h.update(i.encode())
    return h.hexdigest()


def main():
    full_path = f"{P7}/full_repositories/{SUBJECT}.jsonl"
    ref_path = f"{P7}/refined/{SUBJECT}/bm25_40.jsonl"
    full = read_jsonl(full_path)
    ref = read_jsonl(ref_path)
    assert len(full) == 6000, len(full)
    assert len(ref) == 942, len(ref)
    assert all("text" in x for x in full) and all("text" in x for x in ref)
    full_ids = [x["experience_id"] for x in full]
    ref_ids = [x["refined_id"] for x in ref]
    assert len(set(full_ids)) == 6000 and len(set(ref_ids)) == 942
    # every refined entry must be backed by real full entries
    src = [s for x in ref for s in x["source_experience_ids"]]
    assert set(src) <= set(full_ids), "refined entry references an unknown experience"
    assert len(set(src)) == 6000, f"refined repository covers {len(set(src))} of 6000 experiences"

    # 55 queries: 15 original + 40 extended, unique keys, no gold answer kept
    orig = read_jsonl(f"{P7}/heldout/{SUBJECT}.jsonl")
    ext = [q for q in read_jsonl(os.path.join(P10, "eval/heldout_extended.jsonl")) if q["subject"] == SUBJECT]
    assert len(orig) == 15 and len(ext) == 40, (len(orig), len(ext))
    queries = []
    for set_name, rows in (("original", orig), ("extended", ext)):
        for q in rows:
            queries.append({"query_key": f"{set_name}::{q['qid']}", "question_set": set_name,
                            "qid": q["qid"], "question": q["question"], "choices": q["choices"],
                            "query_text": f"{q['question']} {' '.join(q['choices'])}"})
    keys = [q["query_key"] for q in queries]
    assert len(keys) == 55 and len(set(keys)) == 55
    assert len({q["qid"] for q in queries}) == 55
    json.dump(queries, open(os.path.join(HERE, "manifests", "queries.json"), "w"), indent=1)

    hw = {"platform": platform.platform(), "machine": platform.machine(), "python": platform.python_version(),
          "logical_cpus": os.cpu_count(),
          "cpu_model": next((l.split(":", 1)[1].strip() for l in open("/proc/cpuinfo") if "model name" in l), "N/A"),
          "ram_gib": round(int(next(l.split()[1] for l in open("/proc/meminfo") if l.startswith("MemTotal"))) / 1048576, 1)}
    pkgs = {}
    for mod in ("numpy", "rank_bm25", "pandas"):
        try:
            pkgs[mod] = __import__(mod).__version__
        except Exception:
            pkgs[mod] = "N/A"
    try:
        commit = subprocess.run(["git", "-C", ROOT, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    except Exception:
        commit = "N/A"

    manifest = {
        "subject": SUBJECT, "threshold": 40,
        "full_repository": {"path": os.path.relpath(full_path, ROOT), "entries": len(full),
                            "bytes": os.path.getsize(full_path), "sha256_file": sha_file(full_path),
                            "sha256_ids": sha_ids(full_ids)},
        "refined_repository": {"path": os.path.relpath(ref_path, ROOT), "entries": len(ref),
                               "bytes": os.path.getsize(ref_path), "sha256_file": sha_file(ref_path),
                               "sha256_ids": sha_ids(ref_ids),
                               "source_experiences_covered": len(set(src))},
        "entry_reduction_percent": round(100 * (1 - len(ref) / len(full)), 2),
        "queries": {"count": len(queries), "original": 15, "extended": 40,
                    "sha256_keys": sha_ids(keys),
                    "source_files": [os.path.relpath(f"{P7}/heldout/{SUBJECT}.jsonl", ROOT),
                                     os.path.relpath(os.path.join(P10, "eval/heldout_extended.jsonl"), ROOT)]},
        "hardware": hw, "packages": pkgs, "commit": commit,
        "api_log": {"path": os.path.relpath(f"{P7}/tables/api_usage.csv", ROOT),
                    "sha256_file": sha_file(f"{P7}/tables/api_usage.csv")},
    }
    json.dump(manifest, open(os.path.join(HERE, "manifests", "input_manifest.json"), "w"), indent=1)
    print(json.dumps({k: manifest[k] for k in ("entry_reduction_percent",)}, indent=0))
    print("full", len(full), "refined", len(ref), "queries", len(queries))
    print("covers", manifest["refined_repository"]["source_experiences_covered"], "of 6000 experiences")
    print("cpu:", hw["cpu_model"], "| cpus:", hw["logical_cpus"], "| ram GiB:", hw["ram_gib"],
          "| numpy", pkgs["numpy"], "| commit", commit[:8])


if __name__ == "__main__":
    main()
