#!/usr/bin/env python3
"""Emit the compact 3-row Table (.tex + .md) from results/table_collaborative_sharing.csv."""
import csv, os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
rows = list(csv.DictReader(open(os.path.join(HERE, "results", "table_collaborative_sharing.csv"))))
assert len(rows) == 3

tex = [r"\begin{table}[t]", r"    \centering",
       r"    \caption{Controlled cross-client experience sharing on MMLU High School Geography.",
       r"    All settings use the same 55 unseen questions and ten responses per question.",
       r"    Shared-matched averages three preselected entry-count-matched pools.}",
       r"    \label{tab:collaborative_sharing}", r"    \footnotesize", r"    \setlength{\tabcolsep}{3pt}",
       r"    \renewcommand{\arraystretch}{1.1}",
       r"    \begin{tabular}{lrrl}", r"        \hline",
       r"        Setting & Entries & Sources & Accuracy (\%) [95\% CI] \\", r"        \hline"]
for r in rows:
    tex.append(f"        {r['setting']} & {int(r['entries']):,} & {r['sources']} & "
               f"{r['accuracy_percent']} [{r['ci_lower']}, {r['ci_upper']}] \\\\")
tex += [r"        \hline", r"    \end{tabular}", r"\end{table}", ""]
open(os.path.join(HERE, "latex", "table_collaborative_sharing.tex"), "w").write("\n".join(tex))

md = ["| Setting | Entries | Sources | Accuracy (%, 95% CI) |", "|---|---:|---:|---|"]
for r in rows:
    md.append(f"| {r['setting']} | {int(r['entries']):,} | {r['sources']} | "
              f"{r['accuracy_percent']} [{r['ci_lower']}, {r['ci_upper']}] |")
open(os.path.join(HERE, "results", "table_collaborative_sharing.md"), "w").write("\n".join(md) + "\n")
print("\n".join(md))
