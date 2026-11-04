#!/usr/bin/env python3
"""Emit latex/table_backend_overhead.tex from results/backend_overhead_table.csv (values copied verbatim)."""
import csv, os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
rows = list(csv.DictReader(open(os.path.join(HERE, "results", "backend_overhead_table.csv"))))
by = {(r["group"], r["metric"]): r for r in rows}


def tex_num(s):
    return s.replace(",", "{,}")


def cell(group, metric, col):
    v = by[(group, metric)][col]
    return tex_num(v)


lines = [r"\begin{table}[t]", r"    \centering",
         r"    \caption{Backend management overhead on MMLU High School Geography: 6{,}000 entries in the",
         r"    full repository versus 942 after refinement ($\tau_{\mathrm{sim}}=40$, 84.3\,\% fewer). Local",
         r"    timings exclude file I/O and LLM inference; query statistics are the median of three measurement",
         r"    sessions (825 timed queries per repository). API rows summarise the historical uncached",
         r"    condensation requests recorded in the run log.}",
         r"    \label{tab:backend_overhead}", r"    \footnotesize", r"    \setlength{\tabcolsep}{3pt}",
         r"    \renewcommand{\arraystretch}{1.06}", r"    \begin{tabular}{lrr}", r"        \hline",
         r"        Metric & Full & Refined \\", r"        \hline",
         r"        Indexed entries & " + cell("Repository", "Indexed entries", "full") + " & " +
         cell("Repository", "Indexed entries", "refined") + r" \\",
         r"        Index build (s) & " + cell("Retrieval", "Index build (s)", "full") + " & " +
         cell("Retrieval", "Index build (s)", "refined") + r" \\",
         r"        Hot query P50 (ms) & " + cell("Retrieval", "Hot query P50 (ms)", "full") + " & " +
         cell("Retrieval", "Hot query P50 (ms)", "refined") + r" \\",
         r"        Hot query P95 (ms) & " + cell("Retrieval", "Hot query P95 (ms)", "full") + " & " +
         cell("Retrieval", "Hot query P95 (ms)", "refined") + r" \\",
         r"        \hline",
         r"        BM25 matrix build (s) & " + cell("Local refinement", "BM25 matrix build (s)", "full") + " & " +
         cell("Local refinement", "BM25 matrix build (s)", "refined") + r" \\",
         r"        Anchor grouping (s) & " + cell("Local refinement", "Anchor grouping (s)", "full") + " & " +
         cell("Local refinement", "Anchor grouping (s)", "refined") + r" \\",
         r"        \hline",
         r"        Uncached LLM calls & " + cell("LLM condensation", "Successful uncached calls", "full") + " & " +
         cell("LLM condensation", "Successful uncached calls", "refined") + r" \\",
         r"        Input / output tokens & " + cell("LLM condensation", "Input / output tokens", "full") + " & " +
         cell("LLM condensation", "Input / output tokens", "refined") + r" \\",
         r"        Request P50 / P95 (s) & " + cell("LLM condensation", "API request P50 / P95 (s)", "full") + " & " +
         cell("LLM condensation", "API request P50 / P95 (s)", "refined") + r" \\",
         r"        Logged cost (USD) & " + cell("LLM condensation", "Logged estimated cost (USD)", "full") + " & " +
         cell("LLM condensation", "Logged estimated cost (USD)", "refined") + r" \\",
         r"        \hline", r"    \end{tabular}", r"\end{table}", ""]
open(os.path.join(HERE, "latex", "table_backend_overhead.tex"), "w").write("\n".join(lines))
print("\n".join(lines))
