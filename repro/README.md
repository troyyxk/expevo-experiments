# Reproduction: Fig.5 / Fig.6 on MMLU `high_school_biology`

Paper: *Experience Scaling: Post-Deployment Evolution for Large Language Models*
(arXiv 2509.18771v1). Upstream repo: `../ExperienceScaling/` (paper release) and
`../older_version/` (the residual-scaling repos the authors actually ran).

## What is run

| script | paper figure | protocol |
|---|---|---|
| `run_fig5.py` | Fig.5 (repetitive / multi-client experience growth) | start from an **empty** DB; each epoch every question gets 10 independent answers, one distilled experience per (question, epoch) is appended |
| `run_fig6_build.py` | Fig.6 (over-saturated DB) | 100 train questions × 50 iterations × 3 answers, one experience appended per (question, iteration) |
| `condense.py` | Fig.6 (refinement) | the repo's own `VectorDB.group_and_combine_similar()` at BM25 thresholds 120/100/80/60/40 |
| `run_fig6_eval.py` | Fig.6 (contaminated vs refined) | 100 held-out questions × 10 answers against each DB |
| `analyze.py` | — | `out/fig5.png`, `out/fig6.png`, `out/summary.md` |

Method code is **not reimplemented**: `server/db/vector_db.py`, `server/condence_model.py`,
`server/prompt_manager.py` are imported from the paper release unchanged
(`engine.py` only adds a lazy BM25 rebuild and a cached similarity matrix so that
10k-item DBs are tractable).

## Prompt fidelity

`python check_prompts.py` diffs the prompt strings used here against
`experience_scaling_client/prompt_manager.py` in a subprocess. All five prompt
families (`question` with/without context/options, `summarize`, `confidence`)
match the release **verbatim** after removing the two documented additions below.

## Documented deviations

1. **Model**: the paper ran `Meta-Llama-3-8B-Instruct` (see
   `older_version/residual_scaling_client/config.py`). OpenRouter no longer
   serves that checkpoint; we use `meta-llama/llama-3.1-8b-instruct` (same size
   class, same family). `temperature=0.7` as in the repo.
2. **Format instruction (D1)**: the original prompts rely on the base template's
   `####` convention. The chat model ignores it (`1/6` compliance), so one line
   is appended to the system message: *"End your reply with exactly one line of
   the form: #### <the chosen option text>..."* (`6/6` compliance). The
   confidence prompt gets an analogous line.
3. **Answer extraction (D2)**: candidates are normalised (strip `Answer:`
   prefixes/quotes, map a bare option letter to its text). Two metrics are
   reported:
   * `strict` — the paper's exact-match protocol (`clean_str(answer) == clean_str(truth)`),
   * `snap` — additionally accepts the answer when exactly one option text is
     embedded in it (upper bound; shown for transparency).
   **`strict` is the headline number** because it is what the paper measures.
4. **Concurrency / order**: questions are answered in parallel and all see the
   DB snapshot taken at the start of the epoch (the paper's multi-client
   setting). The authors' single-threaded loop lets question *i* see the
   experiences written by questions `< i` in the same epoch.
5. **Scale** (API budget): Fig.5 uses 200 of the 347 questions, 10 epochs,
   10 answers each (paper: 347 questions); confidence is sampled on 1 of 10
   answers (paper: all 10). Fig.6 saturates with 5,000 experiences
   (paper's `first100` run: 9,907). DB size matters for the BM25 scale, so
   absolute thresholds are not directly comparable across scales — compare
   *compression ratio* and *direction*, not the raw numbers.

## Files

```
secret_key.txt        # OpenRouter key (chmod 600, do not commit)
engine.py             # model backend + prompts + fast VectorDB
runner.py             # epoch / batch helpers
server/               # copy of experience_scaling_server (unmodified logic)
data/mmlu/high_school_biology/*.parquet
out/                  # fig5.png, fig6.png, summary.md, usage.jsonl, DB snapshots
```

## Cost

All usage is logged per call to `out/usage.jsonl` (`cost` field from OpenRouter).
