# Fig. 3 / Fig. 4 configuration audit (arxiv v1 numbering: Figs. 4 and 5)

Scope: the "Plain / Memory / Experience" experiment and the "Experience Accumulation" experiment of the
original paper. Nothing was re-run; every value below was read from the frozen code, configs, payloads
and the API usage log.

## Numbering note (read first)

In arXiv 2509.18771v1 the figures are: **Fig. 3 = experience degradation**, **Fig. 4 = Plain / Memory /
Experience**, **Fig. 5 = accumulation over epochs (+ confidence panel)**. The request calls the first two
"Fig. 3" and "Fig. 4", which matches a renumbered draft. The table therefore labels each row with both:
`draft Fig. 3 (= arXiv Fig. 4)` and `draft Fig. 4 (= arXiv Fig. 5)`.

## Verification table

| # | Item | Value actually used | Evidence (path:line) | Status |
|---|---|---|---|---|
| 1 | Model, reproduction | `meta-llama/llama-3.1-8b-instruct` | `repro/engine.py:55`; `repro/out/fig4.json` (`"model"`); `repro/out/fig5_v2.json`; `repro/out/usage.jsonl` (117,570 calls, one model id) | verified |
| 2 | Model, original paper | `Meta-Llama-3-8B-Instruct` (never re-run here) | `older_version/residual_scaling_client/config.py:16`; `repro/README.md` §Documented deviations #1 | verified in code, not reproduced |
| 3 | Inference prompt | client prompt verbatim: system "You are a helpful AI assistant … `####`", user `Options: '…'` + `Context: '[…]'` + `Request: …`; plus the D1 line "End your reply with exactly one line of the form: `#### <chosen option text>`" needed by chat models | `ExperienceScaling/experience_scaling_client/prompt_manager.py:62-82`; `repro/engine.py:205-240`; `repro/check_prompts.py` reports exact_match for all five prompt families | verified |
| 4 | Experience prompt, draft Fig. 3 | multiple-choice distillation: "Summary this input into one sentence … Correct answer … Wrong answer" | `prompt_manager.py:88-104`; `repro/engine.py:165-175` | verified |
| 5 | Experience prompt, draft Fig. 4 | same distillation in the reported run (v2); the discarded first run used the generic summarisation prompt | `repro/run_fig5_v2.py:37-44`; `repro/engine.py:263-275`; `repro/out/fig5.json` vs `fig5_v2.json` | verified |
| 6 | Memory baseline | raw conversation string `Question: '…', CORRECT answer: '…', WRONG answer: '…'` | `ExperienceScaling/.../teacher_model.py:92-96`; `repro/run_fig4.py:56-59,71-73` | verified |
| 7 | Temperature | 0.7 | `ExperienceScaling/.../config.py:5`; `repro/server/config.py:17`; `repro/engine.py:57` | verified |
| 8 | Max tokens | original: local HF pipeline, `pipe_max_length 8192`, no per-call cap; reproduction: 160 (answers), 120 (confidence), 120 (distillation) | `repro/server/config.py:18`; `repro/engine.py:161-163`; `repro/runner.py:37,56` | **deviation** |
| 9 | Retrieval Top-K | 3 | `repro/server/config.py:3`; `repro/server/db/vector_db.py:67` | verified |
| 10 | Score filter | `return_bm25th = -10000` → no document is filtered out | `repro/server/config.py:4`; `vector_db.py:61` | verified |
| 11 | BM25 | `rank_bm25.BM25Okapi` defaults (k1=1.5, b=0.75), no custom parameters | `repro/server/db/vector_db.py:85` | verified |
| 12 | Context budget | none for retrieval: ≤3 documents joined with `" --- "`, no truncation; the 4096-token (`pipe_max_length//2`) budget applies only to refinement | `vector_db.py:67`; `repro/runner.py:30-34`; `vector_db.py:19` | verified (no budget) |
| 13 | Client count | **1** logical client: a single `RetroTester(id="01")` running 10 rounds | `ExperienceScaling/.../experience_model.py:126-140` | paper's "multi-client" wording **not verified** |
| 14 | Interactions, draft Fig. 3 | build: 277 construction questions × ≤3 attempts, one distillation each → 214 stored per database; evaluation: 70 questions × 3 conditions × 1 answer × 20 rounds | `repro/run_fig4.py:27-29,53-75`; `repro/out/fig4.json` | verified (reproduction ran 30 rounds) |
| 15 | Interactions, draft Fig. 4 | 200 questions × 10 answers × 10 epochs = 20,000 answers; one experience per (question, epoch); database 0 → 1800 | `repro/run_fig5_v2.py:24-29,60-80`; `repro/out/fig5_v2.json` | verified |
| 16 | Experience update timing | appended after each epoch; the reproduction appends per 20-question chunk to mimic the authors' sequential loop | `repro/run_fig5_v2.py:60-78`; `repro/README.md` deviations #4 | **deviation** |
| 17 | "Evaluation Round", draft Fig. 3 | one complete pass over the 70 held-out questions under the three conditions, one answer each, against a **frozen** database — so round-to-round variation is sampling noise, not learning | `repro/run_fig4.py:120-145`; paper Fig. 4 x-axis "Test 1 … Test 20" | verified |
| 18 | Dataset | MMLU `high_school_biology`, dev + test + validation concatenated = 347 questions; 80/20 → 277 construction / 70 held-out | `repro/engine.py:388-405`; `repro/data/mmlu/high_school_biology/*.parquet` | verified |
| 19 | Feedback source | correctness judged against the MMLU key by strict `clean_str` equality; "wrong answers" are the model's own failed attempts, no teacher model | `repro/engine.py:332-347`; `repro/run_fig4.py:53-60` | verified |
| 20 | Statistics | draft Fig. 3: percent correct of 70 questions per round, averaged over rounds; draft Fig. 4: correct/10 per question, averaged over 200 questions | `repro/run_fig4.py:139-146`; `repro/run_fig5_v2.py:74-78` | verified |

## Findings that change what may be written

1. **The paper's own numbers cannot be confirmed by the reproduction.** Over 30 rounds the reproduction
   gives Plain 45.05 %, Memory 43.90 %, Experience 45.38 % (sd 4.4–5.0), against the paper's 50.8 / 51.4 /
   55.4 (`repro/out/fig4.json`, `repro/analyze_fig4_v2.py:92`). The ordering is also unstable. The draft
   must attribute these numbers to the original paper, not to this reproduction.
2. **Client count.** The released code instantiates one retrospective tester; "multi-client" is not
   encoded in the Fig. 3/Fig. 4 path. Write "a single client answering repeatedly", or mark the
   multi-client claim as unverified.
3. **Accumulation depends on the distillation prompt.** The first run (generic summarisation prompt)
   scored 92–94 % because the experiences paraphrased the option text; the reported run uses strict
   correctness and the MC distillation prompt → 54.9 → 78.0 % (`fig5.json` vs `fig5_v2.json`).
4. **Token limits differ** between the original local pipeline and the API reproduction (8192 vs
   160/120). This must be listed as a deviation, not as the original configuration.

## Minimal text for Experimental Setup

> Both experiments use MMLU high-school biology (347 questions from the dev, test and validation
> splits). The plain, memory and experience comparison splits the questions 80/20 into 277 construction
> and 70 held-out questions, builds two 214-entry databases from the construction split (memory: the raw
> conversation string; experience: one distilled sentence) and evaluates the held-out questions once per
> condition in each of 20 evaluation rounds against a frozen database, so round-to-round variation
> reflects sampling noise rather than learning. The accumulation experiment starts from an empty
> database and, in each of 10 epochs, re-asks 200 questions ten times with top-3 BM25 retrieval and then
> appends one distilled experience per question. Inference samples at temperature 0.7 and answers are
> scored by exact match against the MMLU key. Accuracy is averaged over the held-out questions and over
> epochs, respectively.

Chinese summary of the same paragraph is omitted here on purpose: the draft is in English.
