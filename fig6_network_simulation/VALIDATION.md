# Validation — Fig. 6 queueing simulation

`python3 src/tests_sim.py` → **0 failure(s)**. Ten checks, all passing:

| # | Test | Assertion | Result |
|---|---|---|---|
| 1 | Single event | `L = 8(D+H)/R` exactly (8.0000 ms for 1000 B at 1 Mbps) | PASS |
| 2 | No contention | arrivals far apart ⇒ queue delay 0 | PASS |
| 3 | Paired counterfactual | raw and distilled share one arrival array and one payload permutation; independent recomputation reproduces `run_one` | PASS |
| 4 | FIFO invariants | `F ≥ B ≥ A` for 20,000 congested events | PASS |
| 5 | Server sequentiality | start times non-decreasing, finish times strictly increasing | PASS |
| 6 | Non-negative queueing | `Q_i ≥ 0` | PASS |
| 7 | Pool conservation | 24,000 unique pairs; raw 22,080,160 B, distilled 4,970,488 B | PASS |
| 8 | Utilisation tracks load | 0.303 at target 0.30; 0.857 at target 0.85 | PASS |
| 9 | Hand calculation | arrivals 0/1/2 s, service 4 s ⇒ finish 4/8/12 s, queue 0/3/6 s | PASS |
| 10 | Reproducibility | identical seed ⇒ identical P95 and mean | PASS |

## Experimental controls (checked explicitly)

**Client scaling (panel a).** The per-client rate is held at 1 upload/s and the client count is varied,
so the aggregate arrival rate is `M` uploads/s (10, 20, 50, 100). Raw and distilled are submitted with
the *same* arrival array and the same payload permutation; only the service time differs. The measured
utilisation of raw uploads rises 0.074 → 0.737, which confirms that the experiment scales the load
rather than just relabelling clients.

**Load sweep (panel b).** For every point a single `λ_total` is drawn from `ρ_raw = λ_total·8(D̄_raw)/R`
with the *measured* mean payload, and the identical arrivals are replayed for both representations.
The measured `ρ_raw` matches the target (0.300 / 0.600 / 0.850 / 0.950), and the distilled streams land
at `ρ_exp = 0.225·ρ_raw` (0.068 / 0.135 / 0.191 / 0.214), which is exactly the payload ratio. The two
representations are therefore compared under *identical request workloads*, not under matched
utilisation.

**Warm-up.** Every run starts from an empty queue and processes all 24,000 events. Discarding the first
10 % or 20 % of events as warm-up changes the P95 at `ρ_raw = 0.95` from 293.8 ms to 298.4 ms and
297.3 ms respectively (≤ 1.6 %) and leaves the paired reduction at 98.7 % in all three cases, so the
reported statistics are not transient contamination. All events are kept to match the fixed-size
trace specified for each run.

**Error bars.** Bars are one standard deviation across the 30 independent seeds. The seed-level 95 %
confidence interval of the mean (`t` with 29 degrees of freedom) is reported in `results/table_fig6.csv`;
at the most variable point, `ρ_raw = 0.95`, the raw P95 is 264.2 ms ± 28.0 ms (95 % CI).

## Analytical cross-check

At low load the simulator must reduce to Eq. (2). With ten clients at 1 Mbps:

| Representation | Simulated mean | `8D/R` from the measured bytes | Difference |
|---|---:|---:|---:|
| Raw episodes | 7.71 ms | 7.36 ms | +0.35 ms (7 % utilisation) |
| Distilled experiences | 1.67 ms | 1.66 ms | +0.01 ms (2 % utilisation) |

## Scope

No TCP retransmission, no wireless MAC/PHY contention, no connection setup, no inference or distillation
compute. The reported quantity is a queueing-plus-transmission completion time under an explicit
shared-link assumption, not an end-to-end service latency nor a field wireless measurement.
