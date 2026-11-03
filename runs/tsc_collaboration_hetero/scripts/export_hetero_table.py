#!/usr/bin/env python3
"""Step 7: compact 3-row table (.tex + .md) from results/table_hetero.csv."""
import csv, os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
rows = list(csv.DictReader(open(os.path.join(HERE, "results", "table_hetero.csv"))))
assert len(rows) == 3

tex = [r"\begin{table}[t]", r"    \centering",
       r"    \caption{Retrospective heterogeneous client coverage on MMLU High School Geography.",
       r"    Each client keeps only its own 25 experiences on its 15 assigned construction questions.",
       r"    All settings answer the same 55 unseen questions with ten responses each.}",
       r"    \label{tab:hetero_sharing}", r"    \footnotesize",
       r"    \setlength{\tabcolsep}{3pt}", r"    \renewcommand{\arraystretch}{1.1}",
       r"    \begin{tabular}{lrrrl}", r"        \hline",
       r"        Setting & Entries & Sources & Construction Q. & Accuracy (\%) [95\% CI] \\",
       r"        \hline"]
for r in rows:
    tex.append(f"        {r['setting']} & {int(r['entries']):,} & {r['sources']} & "
               f"{r['construction_questions']} & {r['accuracy_percent']} [{r['ci_lower']}, {r['ci_upper']}] \\\\")
tex += [r"        \hline", r"    \end{tabular}", r"\end{table}", ""]
open(os.path.join(HERE, "latex", "table_hetero.tex"), "w").write("\n".join(tex))

md = ["| Setting | Entries | Sources | Construction Q. | Accuracy (%, 95% CI) |", "|---|---:|---:|---:|---|"]
for r in rows:
    md.append(f"| {r['setting']} | {int(r['entries']):,} | {r['sources']} | {r['construction_questions']} | "
              f"{r['accuracy_percent']} [{r['ci_lower']}, {r['ci_upper']}] |")
open(os.path.join(HERE, "results", "table_hetero.md"), "w").write("\n".join(md) + "\n")
print("\n".join(md))
