# Fig. 6 — trace-driven multi-client upload simulation

Replaces the purely analytical `D/R` figure with a discrete-event queueing simulation driven by the
**measured** per-event payload sizes of the 24,000 P7 experience pairs. No LLM calls, no regeneration
of experiences, and no change to Fig. 5 or Table II.

## Model

- `M` logical clients → one shared FIFO uplink of constant rate `R` → shared backend.
- Arrivals: Poisson, one upload per second per client (an explicitly synthetic workload).
- Service time: `S_i = 8(D_i + H)/R`, `H = 0` in the baseline, `H = 60` bytes in the sensitivity run.
- FCFS recursion `B_i = max(A_i, F_{i-1})`, `F_i = B_i + S_i`; queueing delay `Q_i = B_i - A_i`,
  completion time `L_i = F_i - A_i`.
- Raw and distilled representations share arrivals, client assignment, rate and seeds: a paired
  counterfactual comparison.

## Files

| Path | Content |
|---|---|
| `src/extract_payloads.py` | rebuilds `data/payload_pairs.csv` from the P7 run and validates the totals |
| `src/sim_uploads.py` | simulator + experiment matrix, writes `results/per_run.csv`, `summary.csv`, `config.json` |
| `src/tests_sim.py` | ten correctness checks (single event, FIFO invariants, pairing, conservation, reproducibility) |
| `src/plot_fig6.py` | final two-panel figure |
| `results/table_fig6.csv` | the numbers behind every plotted point |
| `latex/fig6_replacement.tex` | LaTeX figure block (keeps `\label{fig:upload_time}`) |
| `latex/vc_c3_replacement.tex` | rewritten C3 paragraph with the simulated numbers |

## Reproduce

```bash
cd fig6_network_simulation
python3 src/extract_payloads.py          # 24,000 pairs, validates 22.080/4.970 MB
python3 src/tests_sim.py                 # expect "0 failure(s)"
python3 src/sim_uploads.py --seeds 30    # E1 + E2 + E3, ~7 s
python3 src/plot_fig6.py                 # images/fig_upload_completion_simulation.pdf
```

## Scenarios

| ID | Matrix | Purpose |
|---|---|---|
| E1 | `M = 10, 20, 50, 100`, λ_client = 1/s, R = 1 Mbps | client scaling, panel (a) |
| E2 | `M = 50`, R = 1 Mbps, ρ_raw = 0.30, 0.60, 0.85, 0.95 | offered-load sweep, panel (b) |
| E3 | R = 1, 5 Mbps × H = 0, 60 B at M = 50 | rate and overhead sensitivity (table only) |

Every scenario uses 24,000 events and 30 seeds; error bars are one standard deviation across seeds.
Panel (a) plots P95 completion time versus clients; panel (b) plots the paired P95 reduction
`1 - P95_exp/P95_raw` versus the offered load, against the 77.5 % payload-ratio baseline.
