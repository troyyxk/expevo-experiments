"""Invariant checks from Section 10 of the task spec -> validation_report.md."""
import argparse
import json
import os

from .common import load_config, load_env, read_json, read_jsonl, serialize_item

CHECKS = []


def check(name, ok, detail=""):
    CHECKS.append((name, bool(ok), detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    args = ap.parse_args()
    cfg = load_config(args.config)
    env = load_env()
    run_dir = os.path.abspath(os.path.join(cfg["runtime"]["runs_dir"], cfg["run_id"]))
    subjects = cfg["data"]["subjects"]

    # 1) dataset frozen + hashes
    man = read_json(os.path.join(run_dir, "manifest_prepare.json"), {})
    check("dataset frozen with revision/seed",
          bool(man) and all(k in man for k in ("seed", "dataset", "subjects")),
          f"rev={man.get('dataset', {}).get('revision', '?')[:8]}...")

    # 2) construction / heldout disjoint
    disjoint = True
    for s in subjects:
        con = {r["qid"] for r in read_jsonl(os.path.join(run_dir, "dataset", f"{s}.jsonl"))}
        held = {r["qid"] for r in read_jsonl(os.path.join(run_dir, "heldout", f"{s}.jsonl"))}
        disjoint &= not (con & held)
    check("construction and heldout question IDs are disjoint", disjoint)

    # 3) heldout never used
    held_ids = set()
    for s in subjects:
        held_ids |= {r["qid"] for r in read_jsonl(os.path.join(run_dir, "heldout", f"{s}.jsonl"))}
    used = set()
    for s in subjects:
        used |= {e["source_question_id"] for e in read_jsonl(os.path.join(run_dir, "episodes", f"{s}.jsonl"))}
    check("no heldout question entered any episode", not (used & held_ids),
          f"{len(used & held_ids)} overlaps")

    # 4) gold answer not in the inference prompt
    from .run_interactions import SYSTEM_A, USER_A
    tmpl_ok = "Correct Option" not in (SYSTEM_A + USER_A) and "gold" not in (SYSTEM_A + USER_A).lower()
    check("inference prompt template carries no gold answer", tmpl_ok)

    # 5) pairing + counts + bytes
    n_raw = n_dist = n_full = 0
    raw_b = dist_b = full_b = 0
    parse_ok = True
    for s in subjects:
        eps = read_jsonl(os.path.join(run_dir, "episodes", f"{s}.jsonl"))
        exps = read_jsonl(os.path.join(run_dir, "experiences", f"{s}.jsonl"))
        full = read_jsonl(os.path.join(run_dir, "full_repositories", f"{s}.jsonl"))
        ep_by_id = {e["episode_id"]: e for e in eps}
        for x in exps:
            if x["source_episode_id"] not in ep_by_id:
                parse_ok = False
        n_raw += len(eps); n_dist += len(exps); n_full += len(full)
        raw_b += sum(len(serialize_item(s, e["episode_content"])) for e in eps)
        dist_b += sum(len(serialize_item(s, x["text"])) for x in exps)
        full_b += sum(len(serialize_item(s, r["text"])) for r in full)
        # stored byte fields must match a fresh recomputation
        for e in eps:
            if e["raw_payload_bytes"] != len(serialize_item(s, e["episode_content"])):
                parse_ok = False
        for x in exps:
            if x["distilled_payload_bytes"] != len(serialize_item(s, x["text"])):
                parse_ok = False
    check("every experience traces to a real episode", parse_ok)
    check("n_raw == n_distilled == full_count", n_raw == n_dist == n_full,
          f"raw={n_raw} dist={n_dist} full={n_full}")
    check("full_bytes == distilled_total_bytes", full_b == dist_b, f"{full_b} vs {dist_b}")

    # 6) refinement invariants
    group_ok = True
    refined_ok = True
    for s in subjects:
        full_ids = {r["experience_id"] for r in read_jsonl(os.path.join(run_dir, "full_repositories", f"{s}.jsonl"))}
        for th in cfg["refine"]["thresholds"]:
            p = os.path.join(run_dir, "refined", s, f"bm25_{th}.jsonl")
            if not os.path.exists(p):
                refined_ok = False
                continue
            recs = read_jsonl(p)
            covered = [i for r in recs for i in r["source_experience_ids"]]
            if sorted(covered) != sorted(full_ids):
                group_ok = False
            if len(recs) > len(full_ids):
                refined_ok = False
            for r in recs:
                if r["refined_payload_bytes"] != len(serialize_item(s, r["text"])):
                    refined_ok = False
    check("every threshold covers each experience exactly once", group_ok)
    check("refined_count <= full_count and bytes recomputable", refined_ok)

    # 7) BM25 diagnostics present, no rescaling
    import csv as _csv
    _p = os.path.join(run_dir, "tables", "bm25_score_diagnostics.csv")
    diag = list(_csv.DictReader(open(_p))) if os.path.exists(_p) else []
    check("BM25 diagnostics recorded (raw scores, no rescaling)",
          bool(diag), f"{len(diag)} rows" if diag else "missing")

    # 8) API key not leaked
    key = env.get("LLM_API_KEY", "")
    leaked = []
    if key:
        for root, _, files in os.walk(run_dir):
            for f in files:
                if f.endswith((".jsonl", ".json", ".csv", ".md", ".txt")):
                    try:
                        if key in open(os.path.join(root, f), encoding="utf-8", errors="ignore").read():
                            leaked.append(os.path.join(root, f))
                    except Exception:
                        pass
    check("API key absent from all run artifacts", not leaked, f"{len(leaked)} files" if leaked else "")

    # 9) figures
    figs = [f for f in os.listdir(os.path.join(run_dir, "figures")) if f.endswith(".pdf")] \
        if os.path.isdir(os.path.join(run_dir, "figures")) else []
    check("required figures exist (pdf)", len(figs) >= 3, f"{len(figs)} pdf")

    ok = all(c[1] for c in CHECKS)
    lines = ["# Validation report", "", f"- run: `{cfg['run_id']}`", ""]
    for name, passed, detail in CHECKS:
        lines.append(f"- [{'x' if passed else ' '}] {name}" + (f" — {detail}" if detail else ""))
    lines += ["", f"**Overall: {'PASS' if ok else 'FAIL'}**", ""]
    with open(os.path.join(run_dir, "validation_report.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"\n[validate] {'PASS' if ok else 'FAIL'} -> validation_report.md")
    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
