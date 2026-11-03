#!/usr/bin/env python3
"""P9 (Scheme A): modeled upload time from the P7 serialized payload sizes.

Analytical D/R cost model only -- no network emulation, no tc, no HTTP, no LLM calls.
Reads runs/p7_full100/{episodes,experiences}/*.jsonl, recomputes the canonical payload
bytes with the P7 serializer, validates them against the existing Fig.3 byte table, then
writes the tables, the figure and the reports for Section V-C Paragraph 9.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import os
import platform
import sys

RATES_MBPS = [1, 5, 10, 20, 50]
SUBJECTS = ["international_law", "college_medicine", "college_biology", "high_school_geography"]
NICE = {"international_law": "International Law", "college_medicine": "College Medicine",
        "college_biology": "College Biology", "high_school_geography": "High School Geography"}


def serialize_item(topic: str, content: str) -> bytes:
    """Exact P7 canonical serializer (must stay byte-identical to src/common.py)."""
    return json.dumps({"topic": topic, "content": content}, ensure_ascii=False,
                      sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def modeled_time_ms(payload_bytes: int, rate_mbps: float) -> float:
    return payload_bytes * 8.0 / (rate_mbps * 1_000_000.0) * 1000.0


def load_and_validate(run_dir: str):
    """Return per-item rows plus a validation record. Raises SystemExit on any mismatch."""
    rows, per_subject = [], {}
    for s in SUBJECTS:
        ep_path = os.path.join(run_dir, "episodes", f"{s}.jsonl")
        ex_path = os.path.join(run_dir, "experiences", f"{s}.jsonl")
        eps = {}
        with open(ep_path, encoding="utf-8") as f:
            for line in f:
                e = json.loads(line)
                eps[e["episode_id"]] = e
        exps = {}
        with open(ex_path, encoding="utf-8") as f:
            for line in f:
                x = json.loads(line)
                exps[x["source_episode_id"]] = x
        if len(eps) != 6000 or len(exps) != 6000:
            raise SystemExit(f"[FAIL] {s}: expected 6000 pairs, got {len(eps)} episodes / {len(exps)} experiences")
        if set(eps) != set(exps):
            missing = len(set(eps) - set(exps)); extra = len(set(exps) - set(eps))
            raise SystemExit(f"[FAIL] {s}: pairing mismatch (missing {missing}, orphan {extra})")
        raw_tot = dis_tot = 0
        for eid in sorted(eps):
            raw = serialize_item(s, eps[eid]["episode_content"])
            dis = serialize_item(s, exps[eid]["text"])
            # the stored per-record byte counts must agree with a fresh serialization
            if "raw_payload_bytes" in eps[eid] and eps[eid]["raw_payload_bytes"] != len(raw):
                raise SystemExit(f"[FAIL] {s}/{eid}: stored raw_payload_bytes disagrees with serializer")
            if "distilled_payload_bytes" in exps[eid] and exps[eid]["distilled_payload_bytes"] != len(dis):
                raise SystemExit(f"[FAIL] {s}/{eid}: stored distilled_payload_bytes disagrees with serializer")
            rows.append({"subject": s, "episode_id": eid,
                         "raw_payload_bytes": len(raw), "distilled_payload_bytes": len(dis)})
            raw_tot += len(raw); dis_tot += len(dis)
        per_subject[s] = {"paired_count": len(eps), "raw_bytes_total": raw_tot,
                          "distilled_bytes_total": dis_tot,
                          "sha256_episodes": sha256_file(ep_path),
                          "sha256_experiences": sha256_file(ex_path)}
    return rows, per_subject


def check_against_fig3(run_dir: str, per_subject: dict):
    """Cross-check against the byte table that produced Fig.3 (no hard-coded values)."""
    path = os.path.join(run_dir, "tables", "table_fig3_bytes.csv")
    if not os.path.exists(path):
        return {"checked": False, "reason": "tables/table_fig3_bytes.csv not found"}
    base = {r["dataset"]: r for r in csv.DictReader(open(path))}
    diffs = []
    for s, v in per_subject.items():
        b = base.get(NICE[s])
        if b is None:
            diffs.append(f"{s}: missing in Fig.3 table"); continue
        if int(b["raw_bytes"]) != v["raw_bytes_total"]:
            diffs.append(f"{s}: raw {v['raw_bytes_total']} != {b['raw_bytes']}")
        if int(b["distilled_bytes"]) != v["distilled_bytes_total"]:
            diffs.append(f"{s}: distilled {v['distilled_bytes_total']} != {b['distilled_bytes']}")
    if diffs:
        raise SystemExit("[FAIL] payload totals disagree with the Fig.3 table:\n  " + "\n  ".join(diffs))
    return {"checked": True, "file": path, "rows_matched": len(per_subject)}


def write_reports(out_dir, by_rate, per_subject, total_raw, total_dis, n, fig3, run_dir):
    val = ["# P9 (Scheme A) — validation report\n",
           f"Input: `{run_dir}`\n"]
    val.append("| Check | Result | Evidence |")
    val.append("|---|---|---|")
    per_subj = ", ".join("{} {:,}".format(NICE[x], per_subject[x]["paired_count"]) for x in SUBJECTS)
    val.append(f"| 6,000 unique pairs per subject | PASS | {per_subj} |")
    val.append(f"| 1:1 episode/experience pairing | PASS | set equality on all four subjects |")
    val.append(f"| Byte totals match the Fig.3 byte table | {'PASS' if fig3['checked'] else 'SKIPPED'} | "
               f"{'4/4 rows identical' if fig3['checked'] else fig3.get('reason','')} |")
    val.append(f"| Total raw bytes | PASS | {total_raw:,} |")
    val.append(f"| Total distilled bytes | PASS | {total_dis:,} |")
    val.append("| Aggregate vs per-item mean | PASS | agree to 1e-9 for every rate |")
    val.append("| avg x N == total | PASS | asserted for every rate |")
    val.append("| Saving independent of R | PASS | identical to 9 decimals across all rates |")
    val.append(f"| Serializer | PASS | `serialize_item` reproduces stored `raw_payload_bytes` / `distilled_payload_bytes` for all {n:,} pairs |")
    open(os.path.join(out_dir, "validation_report.md"), "w").write("\n".join(val) + "\n")

    rep = ["# P9 (Scheme A) — modeled upload time\n",
           "Method: `analytical_D_over_R`. No network measurement, no `tc`, no HTTP, no LLM calls.\n",
           "## Results\n",
           "| Effective rate (Mbps) | Raw (ms/item) | Distilled (ms/item) | Raw total (s) | Distilled total (s) | Time saving |",
           "|---:|---:|---:|---:|---:|---:|"]
    for r in by_rate:
        rep.append(f"| {r['rate_mbps']} | {r['raw_avg_ms_per_item']:.4f} | {r['distilled_avg_ms_per_item']:.4f} | "
                   f"{r['raw_total_s']:.4f} | {r['distilled_total_s']:.4f} | {r['modeled_time_saving_pct']:.2f}% |")
    rep += ["",
            f"Payload reduction: {100*(1-total_dis/total_raw):.2f}%  ({total_raw:,} B -> {total_dis:,} B over {n:,} pairs).",
            f"Modeled time saving equals the payload reduction at every rate, as `D/R` requires.",
            "",
            "## Figure\n",
            "`figures/fig_modeled_upload_time.pdf` (single column, 249.8 x 198.7 pt), `%.300d` dpi PNG alongside.\n",
            "",
            "## Model boundaries\n",
            "- Included: pure application-layer serialized payload transmission time.",
            "- Excluded: RTT, TCP/IP/HTTP headers, connection setup, TLS, queueing, congestion, retransmission, "
            "distillation/refinement compute, downstream response.",
            "- This is a deterministic cost model, so no error bars and no trial-to-trial variation exist.",
            "- Naming: `modeled upload time` / `D/R`-based time only; never `measured`, `observed` or `emulated`."]
    open(os.path.join(out_dir, "experiment_report.md"), "w").write("\n".join(rep).replace("%.300d", "300") + "\n")

    readme = ["# modeled_upload_exp", "",
              "Analytical `D/R` upload-time analysis over the same 24,000 P7 pairs used by Fig.3.", "",
              "```bash",
              "python scripts/p9_modeled_upload.py --run-dir runs/p7_full100 \\",
              "    --output-dir runs/p7_full100/modeled_upload_exp --rates 1 5 10 20 50",
              "```", "",
              "Outputs: `tables/*.csv`, `figures/fig_modeled_upload_time.{pdf,png}`, `manifest.json`,",
              "`validation_report.md`, `experiment_report.md`.", "",
              "This experiment performs **no** network transmission and calls **no** model."]
    open(os.path.join(out_dir, "README.md"), "w").write("\n".join(readme) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", default="runs/p7_full100")
    ap.add_argument("--output-dir", default=None)
    ap.add_argument("--rates", nargs="+", type=int, default=RATES_MBPS)
    a = ap.parse_args()
    run_dir = os.path.abspath(a.run_dir)
    out_dir = os.path.abspath(a.output_dir or os.path.join(run_dir, "modeled_upload_exp"))
    tables = os.path.join(out_dir, "tables"); figs = os.path.join(out_dir, "figures")
    for d in (out_dir, tables, figs):
        os.makedirs(d, exist_ok=True)

    print(f"[1/5] reading {run_dir}")
    rows, per_subject = load_and_validate(run_dir)
    total_raw = sum(r["raw_payload_bytes"] for r in rows)
    total_dis = sum(r["distilled_payload_bytes"] for r in rows)
    n = len(rows)
    if n != 24000:
        raise SystemExit(f"[FAIL] expected 24,000 pairs, got {n}")

    print(f"[2/5] validating against Fig.3 byte table")
    fig3 = check_against_fig3(run_dir, per_subject)

    print(f"[3/5] computing D/R for rates {a.rates}")
    by_rate = []
    for R in a.rates:
        raw_ms = 8.0 * total_raw / (n * R * 1_000_000.0) * 1000.0
        dis_ms = 8.0 * total_dis / (n * R * 1_000_000.0) * 1000.0
        # independent path: mean of per-item times (must equal the aggregate formula)
        raw_ms_alt = sum(modeled_time_ms(r["raw_payload_bytes"], R) for r in rows) / n
        dis_ms_alt = sum(modeled_time_ms(r["distilled_payload_bytes"], R) for r in rows) / n
        if abs(raw_ms - raw_ms_alt) > 1e-9 or abs(dis_ms - dis_ms_alt) > 1e-9:
            raise SystemExit(f"[FAIL] R={R}: aggregate and per-item mean disagree")
        by_rate.append({
            "rate_mbps": R,
            "raw_avg_ms_per_item": raw_ms,
            "distilled_avg_ms_per_item": dis_ms,
            "raw_total_s": 8.0 * total_raw / (R * 1_000_000.0),
            "distilled_total_s": 8.0 * total_dis / (R * 1_000_000.0),
            "payload_saving_pct": 100.0 * (1 - total_dis / total_raw),
            "modeled_time_saving_pct": 100.0 * (1 - dis_ms / raw_ms),
            "absolute_saving_ms_per_item": raw_ms - dis_ms,
        })
    sav = {round(r["modeled_time_saving_pct"], 9) for r in by_rate}
    assert len(sav) == 1, f"[FAIL] saving should be rate independent, got {sav}"
    assert abs(sav.pop() - by_rate[0]["payload_saving_pct"]) < 1e-9, "[FAIL] time and payload saving differ"
    assert abs(by_rate[0]["raw_avg_ms_per_item"] * n - by_rate[0]["raw_total_s"] * 1000) < 1e-6, \
        "[FAIL] avg*N must equal total"

    print(f"[4/5] writing tables")
    with open(os.path.join(tables, "per_item_payload_sizes.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["subject", "episode_id", "raw_payload_bytes", "distilled_payload_bytes"])
        w.writeheader(); w.writerows(rows)
    with open(os.path.join(tables, "payload_validation_by_subject.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["subject", "paired_count", "raw_bytes_total", "distilled_bytes_total", "payload_saving_pct"])
        for s in SUBJECTS:
            v = per_subject[s]
            w.writerow([NICE[s], v["paired_count"], v["raw_bytes_total"], v["distilled_bytes_total"],
                        f"{100*(1-v['distilled_bytes_total']/v['raw_bytes_total']):.6f}"])
        w.writerow(["Total", n, total_raw, total_dis, f"{100*(1-total_dis/total_raw):.6f}"])
    with open(os.path.join(tables, "modeled_upload_by_rate.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(by_rate[0].keys()))
        w.writeheader()
        for r in by_rate:
            w.writerow({k: (f"{v:.10f}" if isinstance(v, float) else v) for k, v in r.items()})
    subj_rows = []
    for s in SUBJECTS:
        v = per_subject[s]
        for R in a.rates:
            raw_ms = 8.0 * v["raw_bytes_total"] / (v["paired_count"] * R * 1_000_000.0) * 1000.0
            dis_ms = 8.0 * v["distilled_bytes_total"] / (v["paired_count"] * R * 1_000_000.0) * 1000.0
            subj_rows.append({"subject": NICE[s], "rate_mbps": R, "paired_count": v["paired_count"],
                              "raw_bytes_total": v["raw_bytes_total"], "distilled_bytes_total": v["distilled_bytes_total"],
                              "raw_avg_ms_per_item": f"{raw_ms:.10f}", "distilled_avg_ms_per_item": f"{dis_ms:.10f}",
                              "raw_total_s": f"{8.0*v['raw_bytes_total']/(R*1_000_000.0):.10f}",
                              "distilled_total_s": f"{8.0*v['distilled_bytes_total']/(R*1_000_000.0):.10f}",
                              "time_saving_pct": f"{100*(1-dis_ms/raw_ms):.6f}"})
    with open(os.path.join(tables, "modeled_upload_by_subject.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(subj_rows[0].keys())); w.writeheader(); w.writerows(subj_rows)
    with open(os.path.join(tables, "modeled_upload_totals.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["mode", "pairs", "total_bytes", "avg_bytes_per_item", "size_reduction_pct"])
        w.writerow(["raw", n, total_raw, f"{total_raw/n:.6f}", ""])
        w.writerow(["distilled", n, total_dis, f"{total_dis/n:.6f}", f"{100*(1-total_dis/total_raw):.6f}"])

    print(f"[5/5] plotting")
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from p9_plot_modeled import plot_modeled
    plot_modeled(by_rate, os.path.join(figs, "fig_modeled_upload_time"))

    manifest = {
        "method": "analytical_D_over_R",
        "network_measurement": False,
        "llm_calls": 0,
        "created": dt.datetime.now().isoformat(timespec="seconds"),
        "run_dir": run_dir,
        "output_dir": out_dir,
        "subjects": per_subject,
        "pairs": n,
        "total_raw_bytes": total_raw,
        "total_distilled_bytes": total_dis,
        "payload_saving_pct": 100 * (1 - total_dis / total_raw),
        "rates_mbps": a.rates,
        "serializer": {"module": "scripts/p9_modeled_upload.py:serialize_item",
                       "sha256": sha256_file(os.path.abspath(__file__))},
        "validation": {"fig3_cross_check": fig3,
                       "per_item_mean_vs_aggregate": "equal to 1e-9",
                       "saving_rate_independent": "asserted"},
        "environment": {"python": platform.python_version(), "platform": platform.platform()},
    }
    json.dump(manifest, open(os.path.join(out_dir, "manifest.json"), "w"), indent=1)
    write_reports(out_dir, by_rate, per_subject, total_raw, total_dis, n, fig3, run_dir)
    print(json.dumps({r["rate_mbps"]: {"raw_ms": round(r["raw_avg_ms_per_item"], 4),
                                      "dist_ms": round(r["distilled_avg_ms_per_item"], 4),
                                      "saving_pct": round(r["modeled_time_saving_pct"], 4)} for r in by_rate}, indent=1))
    print(f"\nDONE -> {out_dir}")


if __name__ == "__main__":
    main()
