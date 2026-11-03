"""Compose experiment_report.md from the persisted tables (no hand-typed numbers)."""
import argparse
import csv
import json
import os

from .common import load_config, read_json


def csv_rows(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    args = ap.parse_args()
    cfg = load_config(args.config)
    run_dir = os.path.abspath(os.path.join(cfg["runtime"]["runs_dir"], cfg["run_id"]))
    t = os.path.join(run_dir, "tables")
    foot = csv_rows(os.path.join(t, "lifecycle_footprint.csv"))
    ref = csv_rows(os.path.join(t, "refinement_metrics.csv"))
    lat = csv_rows(os.path.join(t, "upload_latency.csv"))
    diag = csv_rows(os.path.join(t, "bm25_score_diagnostics.csv"))
    totals = read_json(os.path.join(t, "totals.json"), {})
    man = read_json(os.path.join(run_dir, "manifest.json"), {})

    api = {}
    for k, v in (man.get("stages") or {}).items():
        if isinstance(v, dict) and "api" in v:
            api[k.replace("manifest_", "").replace(".json", "")] = v["api"]
    L = []
    L.append(f"# Experiment report — {cfg['run_id']}\n")
    L.append("## 1. Setup\n")
    L.append(f"- model_id: `{next(iter(api.values()))['model_id'] if api else '?'}`")
    L.append(f"- dataset: `{cfg['data']['dataset_repo']}` split `{cfg['data']['split']}` "
             f"revision `{cfg['data']['dataset_revision']}`")
    L.append(f"- seed: `{cfg['seed']}`; sampled per subject: "
             f"{cfg['data']['n_sampled_per_subject']} (construction "
             f"{int(round(cfg['data']['n_sampled_per_subject']*cfg['data']['construction_frac']))}, "
             f"heldout rest); repeats: {cfg['data']['repeats']}")
    L.append(f"- thresholds: {cfg['refine']['thresholds']}; BM25 k1={cfg['refine']['bm25']['k1']}, "
             f"b={cfg['refine']['bm25']['b']}\n")

    L.append("## 2. Lifecycle footprint (canonical serialization)\n")
    L.append("| subject | questions | raw eps | distilled | full repo | refined@100 | raw MB | dist MB | refined MB | upload ↓ | storage ↓ |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for r in foot:
        L.append(f"| {r['subject']} | {r['n_questions']} | {r['n_raw']} | {r['n_distilled']} | "
                 f"{r['full_count']} | {r.get('refined_count_bm100','')} | "
                 f"{int(r['raw_total_bytes'])/1e6:.4f} | {int(r['distilled_total_bytes'])/1e6:.4f} | "
                 f"{int(float(r.get('refined_bytes_bm100',0)))/1e6:.4f} | "
                 f"{r['upload_reduction_pct']}% | {r.get('storage_reduction_pct_bm100','')}% |")
    tt = totals.get("totals", {})
    if tt:
        L.append(f"| **total** | | {tt['n_raw']} | {tt['n_dist']} | | | "
                 f"{tt['raw']/1e6:.4f} | {tt['dist']/1e6:.4f} | {tt['ref100']/1e6:.4f} | "
                 f"{totals['overall_upload_reduction_pct']}% | "
                 f"{totals.get('overall_storage_reduction_bm100_pct')}% |")
    L.append("")

    L.append("## 3. Refinement sweep\n")
    L.append("| subject | τ | refined count | ratio | storage ↓ | items ↓ | overflow |")
    L.append("|---|---|---|---|---|---|---|")
    for r in sorted(ref, key=lambda x: (x["subject"], -int(x["threshold"]))):
        L.append(f"| {r['subject']} | {r['threshold']} | {r['refined_count']} | "
                 f"{r['normalized_entry_ratio']} | {r['storage_reduction_pct']}% | "
                 f"{r['item_count_reduction_pct']}% | {r['overflow_items']} |")
    L.append("")

    L.append("## 4. BM25 score diagnostics (raw scale, no rescaling)\n")
    L.append("| subject | n | self median | off p50 | off p90 | off p99 | off max | frac≥40 | frac≥100 |")
    L.append("|---|---|---|---|---|---|---|---|---|")
    for d in diag:
        L.append(f"| {d['subject']} | {d['n']} | {float(d['self_median']):.1f} | {float(d['off_p50']):.2f} | "
                 f"{float(d['off_p90']):.2f} | {float(d['off_p99']):.2f} | {float(d['off_max']):.1f} | "
                 f"{float(d['frac_pairs_ge_40'])*100:.3f}% | {float(d['frac_pairs_ge_100'])*100:.3f}% |")
    L.append("")

    # tau=60 variant (exploratory) -------------------------------------------------
    alt = [r for r in ref if int(float(r["threshold"])) == 60]
    if alt:
        L.append("### 2b. Exploratory variant: BM25 τ = 60 (not the official setting)\n")
        L.append("| subject | full count | τ=60 count | ratio | storage ↓ |")
        L.append("|---|---|---|---|---|")
        for r in sorted(alt, key=lambda x: x["subject"]):
            L.append(f"| {r['subject']} | {r['full_count']} | {r['refined_count']} | "
                     f"{r['normalized_entry_ratio']} | {r['storage_reduction_pct']}% |")
        L.append("")
        L.append("The official main figure (`fig_lifecycle_footprint`) uses τ = 100. The τ = 60 bars are "
                 "reported as an exploratory alternative (`fig_lifecycle_footprint_tau60`) and must not "
                 "replace the formal 100/80/60/40 sweep.\n")

    L.append("## 5. Modeled upload time (D/R, not measured latency)\n")
    rates = sorted({int(r["rate_mbps"]) for r in lat})
    L.append("| subject | " + " | ".join(f"{r} Mbps" for r in rates) + " |")
    L.append("|---" * (len(rates) + 1) + "|")
    for s in sorted({r["subject"] for r in lat}):
        vals = {int(r["rate_mbps"]): float(r["distilled_avg_ms_per_episode"]) for r in lat if r["subject"] == s}
        L.append(f"| {s} | " + " | ".join(f"{vals.get(rr,0):.3f} ms" for rr in rates) + " |")
    L.append("")

    L.append("## 6. API usage\n")
    L.append("| stage | billed calls | cache hits | prompt tok | completion tok | est. cost (USD) |")
    L.append("|---|---|---|---|---|---|")
    for k, a in api.items():
        L.append(f"| {k} | {a['api_calls_billed']} | {a['cache_hits']} | {a['prompt_tokens']} | "
                 f"{a['completion_tokens']} | {a['estimated_cost_usd']} |")
    L.append("")

    L.append("## 7. Notes and limitations\n")
    L.append("- The model served by the provider is `" + (next(iter(api.values()))['model_id'] if api else "?") +
             "`; the original HGF checkpoint `meta-llama/Meta-Llama-3-8B-Instruct` is no longer served, so the "
             "Llama-3.1-8B-Instruct substitute is used consistently for inference, distillation and condensation.")
    L.append("- BM25 absolute scores depend on corpus size; at this scale τ=100/80 merge very little, which is "
             "reported as measured rather than tuned away.")
    L.append("- Serialized bytes are an application-layer payload model: no TCP/TLS/header overhead.")
    ovf = sum(int(r["overflow_items"]) for r in ref)
    if ovf:
        L.append(f"- {ovf} experiences stayed unmerged because their group exceeded the condensation "
                 "context budget (`context_overflow_unmerged`); the affected reductions are therefore "
                 "lower bounds, not optimised results.")
    L.append("- Resource experiment only: no heldout accuracy is reported (`not_evaluated`).")
    L.append("")

    path = os.path.join(run_dir, "experiment_report.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    print(f"[report] wrote {path}")


if __name__ == "__main__":
    main()
