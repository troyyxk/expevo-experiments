"""Compute every reported number from the persisted records (no hard-coded values)."""
import argparse
import csv
import os

from .common import load_config, read_json, read_jsonl, serialize_item, write_json

RATES_MBPS = [1, 5, 10, 20, 50]


def load_subject(run_dir, subject):
    eps = read_jsonl(os.path.join(run_dir, "episodes", f"{subject}.jsonl"))
    exps = read_jsonl(os.path.join(run_dir, "experiences", f"{subject}.jsonl"))
    full = read_jsonl(os.path.join(run_dir, "full_repositories", f"{subject}.jsonl"))
    refined = {}
    total_bytes = {}
    for th in [100, 80, 60, 40]:
        p = os.path.join(run_dir, "refined", subject, f"bm25_{th}.jsonl")
        if os.path.exists(p):
            refined[th] = read_jsonl(p)
    return eps, exps, full, refined


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    args = ap.parse_args()
    cfg = load_config(args.config)
    run_dir = os.path.abspath(os.path.join(cfg["runtime"]["runs_dir"], cfg["run_id"]))
    tables = os.path.join(run_dir, "tables")
    os.makedirs(tables, exist_ok=True)

    rows, ref_rows, lat_rows = [], [], []
    totals = {"raw": 0, "dist": 0, "full": 0, "ref100": 0, "n_raw": 0, "n_dist": 0}

    for subject in cfg["data"]["subjects"]:
        eps, exps, full, refined = load_subject(run_dir, subject)
        raw_bytes = sum(len(serialize_item(subject, e["episode_content"])) for e in eps)
        dist_bytes = sum(len(serialize_item(subject, x["text"])) for x in exps)
        full_bytes = sum(len(serialize_item(subject, r["text"])) for r in full)
        n_q = len({e["source_question_id"] for e in eps})
        rows.append({
            "subject": subject,
            "n_questions": n_q,
            "n_raw": len(eps),
            "n_distilled": len(exps),
            "raw_total_bytes": raw_bytes,
            "distilled_total_bytes": dist_bytes,
            "full_count": len(full),
            "full_bytes": full_bytes,
            "upload_reduction_pct": round(100 * (1 - dist_bytes / raw_bytes), 2),
        })
        for th, recs in sorted(refined.items(), reverse=True):
            ref_bytes = sum(len(serialize_item(subject, r["text"])) for r in recs)
            n_overflow = sum(1 for r in recs if r.get("status") == "context_overflow_unmerged")
            ref_rows.append({
                "subject": subject, "threshold": th,
                "full_count": len(full), "full_bytes": full_bytes,
                "refined_count": len(recs), "refined_bytes": ref_bytes,
                "storage_reduction_pct": round(100 * (1 - ref_bytes / full_bytes), 2),
                "item_count_reduction_pct": round(100 * (1 - len(recs) / len(full)), 2),
                "normalized_entry_ratio": round(len(recs) / len(full), 4),
                "overflow_items": n_overflow,
            })
            if th == 100:
                rows[-1].update({
                    "refined_count_bm100": len(recs),
                    "refined_bytes_bm100": ref_bytes,
                    "storage_reduction_pct_bm100": round(100 * (1 - ref_bytes / full_bytes), 2),
                    "item_count_reduction_pct_bm100": round(100 * (1 - len(recs) / len(full)), 2),
                    "normalized_entry_ratio_bm100": round(len(recs) / len(full), 4),
                })
        raw_per = raw_bytes / max(len(eps), 1)
        dist_per = dist_bytes / max(len(eps), 1)
        for r in RATES_MBPS:
            lat_rows.append({
                "subject": subject, "rate_mbps": r,
                "raw_avg_ms_per_episode": round(8 * raw_per / (r * 1e6) * 1000, 4),
                "distilled_avg_ms_per_episode": round(8 * dist_per / (r * 1e6) * 1000, 4),
                "raw_bits_per_episode": round(8 * raw_per, 1),
                "distilled_bits_per_episode": round(8 * dist_per, 1),
            })
        if 100 in refined:
            totals["raw"] += raw_bytes
            totals["dist"] += dist_bytes
            totals["full"] += full_bytes
            totals["ref100"] += sum(len(serialize_item(subject, x["text"])) for x in refined[100])
            totals["n_raw"] += len(eps)
            totals["n_dist"] += len(exps)

    with open(os.path.join(tables, "lifecycle_footprint.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    with open(os.path.join(tables, "refinement_metrics.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(ref_rows[0].keys()))
        w.writeheader(); w.writerows(ref_rows)
    with open(os.path.join(tables, "upload_latency.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(lat_rows[0].keys()))
        w.writeheader(); w.writerows(lat_rows)

    summary = {
        "totals": totals,
        "overall_upload_reduction_pct": round(100 * (1 - totals["dist"] / totals["raw"]), 2),
        "overall_storage_reduction_bm100_pct": round(100 * (1 - totals["ref100"] / totals["full"]), 2)
        if totals["full"] else None,
    }
    write_json(os.path.join(tables, "totals.json"), summary)

    print(f"{'subject':<24}{'raw MB':>9}{'dist MB':>9}{'ref100 MB':>10}{'upload%':>9}{'storage%':>10}")
    for r in rows:
        print(f"{r['subject']:<24}{r['raw_total_bytes']/1e6:>9.4f}{r['distilled_total_bytes']/1e6:>9.4f}"
              f"{r.get('refined_bytes_bm100',0)/1e6:>10.4f}{-r['upload_reduction_pct']:>9.1f}"
              f"{-r.get('storage_reduction_pct_bm100',0):>10.1f}")
    print(f"\nTOTAL raw={totals['raw']/1e6:.4f} MB distilled={totals['dist']/1e6:.4f} MB "
          f"refined@100={totals['ref100']/1e6:.4f} MB")
    print(f"overall upload reduction {summary['overall_upload_reduction_pct']:.1f}% | "
          f"storage reduction @BM25-100 {summary['overall_storage_reduction_bm100_pct']:.1f}%")


if __name__ == "__main__":
    main()
