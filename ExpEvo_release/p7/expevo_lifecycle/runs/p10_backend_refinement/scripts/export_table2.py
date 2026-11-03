#!/usr/bin/env python3
"""Emit Table 2 (.tex + .md) from tables/quality_resource_table2.csv -- no hand-typed numbers."""
import csv
import os

OUT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NAME = {"Full": "Full", "BM25_100": "BM25 100", "BM25_80": "BM25 80", "BM25_60": "BM25 60", "BM25_40": "BM25 40"}


def main():
    rows = list(csv.DictReader(open(os.path.join(OUT, "tables", "quality_resource_table2.csv"))))
    missing = [r["setting"] for r in rows if r["accuracy_macro_pct"] == ""]
    if missing:
        raise SystemExit(f"refusing to emit a final table with missing accuracy: {missing}")
    assert len(rows) == 5, len(rows)

    tex = [r"\begin{table*}[t]", r"    \centering",
           r"    \caption{Downstream inference accuracy and backend resource usage across different",
           r"    refinement settings. Accuracy is macro averaged over four MMLU subjects, while storage",
           r"    and indexed entries are aggregated across their repositories.}",
           r"    \label{tab:quality_resource}",
           r"    \begin{tabular}{lcccccc}", r"        \hline",
           r"        Setting & Accuracy (\%) & $\Delta$ (pp) & Storage (MB) & Entries",
           r"        & Storage red. (\%) & Entry red. (\%) \\", r"        \hline"]
    for r in rows:
        tex.append(f"        {NAME[r['setting']]} & {float(r['accuracy_macro_pct']):.2f} & "
                   f"{r['accuracy_delta_pp']} & {float(r['storage_total_mb']):.3f} & "
                   f"{int(r['indexed_entries_total']):,} & {float(r['storage_reduction_pct']):.1f} & "
                   f"{float(r['entry_reduction_pct']):.1f} \\\\")
    tex += [r"        \hline", r"    \end{tabular}", r"\end{table*}", ""]
    open(os.path.join(OUT, "tables", "table2_quality_resource.tex"), "w").write("\n".join(tex))

    md = ["| Setting | Accuracy (%) | Δ (pp) | Storage (MB) | Indexed entries | Storage reduction (%) | Entry reduction (%) |",
          "|---|---:|---:|---:|---:|---:|---:|"]
    for r in rows:
        md.append(f"| {NAME[r['setting']]} | {float(r['accuracy_macro_pct']):.2f} | {r['accuracy_delta_pp']} | "
                  f"{float(r['storage_total_mb']):.3f} | {int(r['indexed_entries_total']):,} | "
                  f"{float(r['storage_reduction_pct']):.1f} | {float(r['entry_reduction_pct']):.1f} |")
    md += ["", "Accuracy: macro average over the four subject-level held-out accuracies "
               "(55 questions x 10 samples each, 15 original plus 40 extended held-out questions). "
               "Storage and entries: totals over the four repositories. Δ is in percentage points relative to Full."]
    open(os.path.join(OUT, "tables", "table2_quality_resource.md"), "w").write("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
