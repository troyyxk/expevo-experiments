"""Shared helpers for the P9 real-network upload experiment (stdlib only)."""
import hashlib
import json
import os

_CANDIDATES = [
    os.environ.get("EXPEVO_RUN_DIR"),
    "/data/xingkun/exp_scale/p7/expevo_lifecycle/runs/p7_full100",
    os.path.expanduser("~/exp_scale_handoff/p7/expevo_lifecycle/runs/p7_full100"),
]
RUN_DEFAULT = next((p for p in _CANDIDATES if p and os.path.isdir(os.path.join(p, "episodes"))), None)
SUBJECTS = ["international_law", "college_medicine", "college_biology", "high_school_geography"]
BATCH_SIZE = 1000


def serialize_item(topic: str, content: str) -> bytes:
    """Exactly the P7 canonical serializer."""
    return json.dumps(
        {"topic": topic, "content": content},
        ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")


def load_pairs(run_dir=None):
    """Return {subject: [(episode_id, raw_bytes, distilled_bytes), ...]} sorted by episode_id."""
    run_dir = run_dir or RUN_DEFAULT
    if not run_dir:
        raise SystemExit("cannot locate runs/p7_full100; set EXPEVO_RUN_DIR or pass --run-dir")
    out = {}
    for s in SUBJECTS:
        eps = {}
        with open(os.path.join(run_dir, "episodes", f"{s}.jsonl"), encoding="utf-8") as f:
            for line in f:
                e = json.loads(line)
                eps[e["episode_id"]] = serialize_item(s, e["episode_content"])
        exps = {}
        with open(os.path.join(run_dir, "experiences", f"{s}.jsonl"), encoding="utf-8") as f:
            for line in f:
                x = json.loads(line)
                exps[x["source_episode_id"]] = serialize_item(s, x["text"])
        ids = sorted(eps)
        if len(ids) != 6000 or set(ids) != set(exps):
            raise SystemExit(f"{s}: pairing mismatch ({len(ids)} episodes, {len(exps)} experiences)")
        out[s] = [(i, eps[i], exps[i]) for i in ids]
    return out


def make_batches(pairs, batch_size=BATCH_SIZE):
    """Split one subject's pairs into non-overlapping batches; body = b'\\n'.join(items)+b'\\n'."""
    batches = []
    for b, start in enumerate(range(0, len(pairs), batch_size)):
        chunk = pairs[start:start + batch_size]
        batches.append({
            "batch_id": b,
            "episode_ids": [c[0] for c in chunk],
            "raw_items": [c[1] for c in chunk],
            "dist_items": [c[2] for c in chunk],
        })
    return batches


def body_of(items):
    return b"\n".join(items) + b"\n"


def sha256(b):
    return hashlib.sha256(b).hexdigest()
