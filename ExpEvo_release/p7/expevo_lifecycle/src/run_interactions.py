"""Frontend inference -> post-hoc feedback -> Raw Interaction Episode."""
import argparse
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

from .api_client import FatalAPIError, LLMClient, TransientAPIError
from .common import append_jsonl, load_config, now_iso, read_jsonl, serialize_item, write_json

SYSTEM_A = """You answer academic multiple choice questions.
Choose exactly one of A, B, C, or D.
Provide a short, plain-language explanation and the final answer.
Do not assume knowledge of any external answer key.
Return only a JSON object with keys "answer" and "explanation".
Example format: {"answer":"B","explanation":"..."}"""

USER_A = """Subject: {subject}
Question: {question}
A. {a}
B. {b}
C. {c}
D. {d}"""

LETTERS = "ABCD"


def build_episode_content(question, choices, response_text, is_correct, gold_letter):
    opts = "\n".join(f"{LETTERS[i]}. {c}" for i, c in enumerate(choices))
    return (
        f"USER QUESTION\n{question}\n{opts}\n\n"
        f"ASSISTANT ANSWER\n{response_text}\n\n"
        f"TASK FEEDBACK\nPrediction Correct: {'true' if is_correct else 'false'}\n"
        f"Correct Option: {gold_letter}"
    )


def parse_answer(text):
    """Return (letter, explanation) or None. Never guesses silently."""
    s = text.strip()
    s = re.sub(r"^```(?:json)?|```$", "", s, flags=re.MULTILINE).strip()
    candidates = [s]
    m = re.search(r"\{.*\}", s, flags=re.DOTALL)
    if m:
        candidates.append(m.group(0))
    for cand in candidates:
        try:
            obj = json.loads(cand)
        except Exception:
            continue
        if isinstance(obj, dict):
            ans = str(obj.get("answer", "")).strip().upper()[:1]
            if ans in LETTERS:
                return ans, str(obj.get("explanation", "")).strip()
    # truncated JSON (max_tokens cut): recover the answer field, keep the rest as text
    m = re.search(r'"answer"\s*:\s*"\s*([ABCD])\s*"', s)
    if m:
        return m.group(1), s
    # last resort: a bare letter on its own line (recorded as such)
    m = re.search(r"\b([ABCD])\b\s*$", s)
    if m:
        return m.group(1), s
    return None


def run_one(client, cfg, subject, q, rep, episode_index):
    letters = "ABCD"
    user = USER_A.format(
        subject=subject, question=q["question"],
        a=q["choices"][0], b=q["choices"][1], c=q["choices"][2], d=q["choices"][3],
    )
    episode_key = f"{subject}/Q{int(q['qid'].split('Q')[-1]):03d}/R{rep:02d}"
    messages = [{"role": "system", "content": SYSTEM_A},
                {"role": "user", "content": user}]
    parse_failures = 0
    last_text = ""
    for attempt in range(3):
        r = client.chat(
            messages, tag=f"inference/{subject}",
            temperature=cfg["prompts"]["inference_temperature"],
            max_tokens=cfg["prompts"]["inference_max_tokens"],
            cache_salt=episode_key,
        )
        last_text = r["text"]
        parsed = parse_answer(last_text)
        if parsed:
            model_answer, explanation = parsed
            gold = q["gold_answer"]
            is_correct = model_answer == gold
            episode_content = build_episode_content(
                q["question"], q["choices"], last_text,
                is_correct, gold,
            )
            eid = f"{subject}/Q{int(q['qid'].split('Q')[-1]):03d}/R{rep:02d}/client{episode_index % 4}"
            return {
                "episode_id": eid,
                "subject": subject,
                "client_id": episode_index % 4,
                "source_question_id": q["qid"],
                "repeat_index": rep,
                "question": q["question"],
                "choices": q["choices"],
                "gold_answer": gold,
                "model_answer": model_answer,
                "model_response": last_text,
                "explanation": explanation,
                "is_correct": is_correct,
                "episode_content": episode_content,
                "raw_payload_bytes": len(serialize_item(subject, episode_content)),
                "model_id": client.model,
                "api_response_id": None,
                "prompt_hash": r.get("prompt_hash"),
            }
        parse_failures += 1
        messages = messages + [
            {"role": "assistant", "content": last_text},
            {"role": "user", "content": 'Return ONLY a JSON object like {"answer":"B","explanation":"..."}.'},
        ]
    raise ValueError(f"unparseable answer after {parse_failures} attempts: {last_text[:120]!r}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    args = ap.parse_args()
    cfg = load_config(args.config)
    run_dir = os.path.abspath(os.path.join(cfg["runtime"]["runs_dir"], cfg["run_id"]))
    client = LLMClient(cfg, run_dir)

    jobs = []
    ep_index = 0
    for subject in cfg["data"]["subjects"]:
        qs = read_jsonl(os.path.join(run_dir, "dataset", f"{subject}.jsonl"))
        for q in qs:
            for rep in range(cfg["data"]["repeats"]):
                jobs.append((subject, q, rep, ep_index))
                ep_index += 1
    print(f"[interactions] {len(jobs)} episodes queued, concurrency={cfg['runtime']['max_concurrent']}")

    failures_path = os.path.join(run_dir, "tables", "failures.csv")
    os.makedirs(os.path.dirname(failures_path), exist_ok=True)
    written = {}
    n_ok = n_fail = 0
    with ThreadPoolExecutor(max_workers=cfg["runtime"]["max_concurrent"]) as ex:
        futs = {ex.submit(run_one, client, cfg, s, q, r, i): (s, q, r) for s, q, r, i in jobs}
        for k, fut in enumerate(as_completed(futs), 1):
            s, q, r = futs[fut]
            try:
                rec = fut.result()
                path = os.path.join(run_dir, "episodes", f"{s}.jsonl")
                append_jsonl(path, rec)
                written[s] = written.get(s, 0) + 1
                n_ok += 1
            except (ValueError, TransientAPIError, FatalAPIError) as e:
                n_fail += 1
                with open(failures_path, "a", encoding="utf-8") as f:
                    f.write(f"{now_iso()},inference,{s},{q['qid']},{r},{type(e).__name__},\"{str(e)[:200]}\"\n")
            if k % 200 == 0:
                print(f"  ... {k}/{len(jobs)} done (ok={n_ok}, failed={n_fail})", flush=True)

    summary = {
        "stage": "run_interactions",
        "finished_at": now_iso(),
        "episodes_queued": len(jobs),
        "episodes_ok": n_ok,
        "episodes_failed": n_fail,
        "per_subject_ok": written,
        "api": client.summary(),
    }
    write_json(os.path.join(run_dir, "manifest_interactions.json"), summary)
    print(f"[interactions] ok={n_ok} failed={n_fail} cost=${client.summary()['estimated_cost_usd']}")


if __name__ == "__main__":
    main()
