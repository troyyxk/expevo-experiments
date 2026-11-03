"""Frontend distillation Psi(H): one experience per completed episode."""
import argparse
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

from .api_client import FatalAPIError, LLMClient, TransientAPIError
from .common import append_jsonl, load_config, now_iso, read_jsonl, serialize_item, write_json

SYSTEM_B = """You distill completed task interactions into reusable experience.
Extract concise domain knowledge that can help solve related future questions.
Pay attention to the actual question, the model response, and task feedback.
If the prediction was wrong, do not preserve the incorrect conclusion as a fact.
Do not invent facts that are unsupported by the interaction and feedback.
Avoid restating the full original question, answer options, or raw transcript.
Produce one self-contained experience item in plain English, usually 1 to 3 sentences.
Prefer concise and useful content over arbitrary length.
Return only the experience text, with no JSON wrapper or explanation about your process."""

USER_B = """Topic: {subject}
Completed episode:
{episode_content}"""


def run_one(client, cfg, ep):
    messages = [
        {"role": "system", "content": SYSTEM_B},
        {"role": "user", "content": USER_B.format(subject=ep["subject"],
                                                  episode_content=ep["episode_content"])},
    ]
    last = ""
    r = None
    for _ in range(3):
        r = client.chat(
            messages, tag=f"distill/{ep['subject']}",
            temperature=cfg["prompts"]["distill_temperature"],
            max_tokens=cfg["prompts"]["distill_max_tokens"],
        )
        last = (r["text"] or "").strip()
        if last:
            break
    if not last:
        raise ValueError("empty distillation output after 3 attempts")
    return {
        "experience_id": f"exp:{ep['episode_id']}",
        "source_episode_id": ep["episode_id"],
        "subject": ep["subject"],
        "text": last,
        "distilled_payload_bytes": len(serialize_item(ep["subject"], last)),
        "model_id": client.model,
        "prompt_hash": r.get("prompt_hash"),
        "distill_temperature": cfg["prompts"]["distill_temperature"],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    args = ap.parse_args()
    cfg = load_config(args.config)
    run_dir = os.path.abspath(os.path.join(cfg["runtime"]["runs_dir"], cfg["run_id"]))
    client = LLMClient(cfg, run_dir)

    jobs = []
    for subject in cfg["data"]["subjects"]:
        jobs.extend(read_jsonl(os.path.join(run_dir, "episodes", f"{subject}.jsonl")))
    print(f"[distill] {len(jobs)} episodes, concurrency={cfg['runtime']['max_concurrent']}")

    failures_path = os.path.join(run_dir, "tables", "failures.csv")
    n_ok = n_fail = 0
    per_subject = {}
    with ThreadPoolExecutor(max_workers=cfg["runtime"]["max_concurrent"]) as ex:
        futs = {ex.submit(run_one, client, cfg, ep): ep for ep in jobs}
        for k, fut in enumerate(as_completed(futs), 1):
            ep = futs[fut]
            try:
                rec = fut.result()
                append_jsonl(os.path.join(run_dir, "experiences", f"{ep['subject']}.jsonl"), rec)
                per_subject[ep["subject"]] = per_subject.get(ep["subject"], 0) + 1
                n_ok += 1
            except (ValueError, TransientAPIError, FatalAPIError) as e:
                n_fail += 1
                with open(failures_path, "a", encoding="utf-8") as f:
                    f.write(f"{now_iso()},distill,{ep['subject']},{ep['episode_id']},-,"
                            f"{type(e).__name__},\"{str(e)[:200]}\"\n")
            if k % 200 == 0:
                print(f"  ... {k}/{len(jobs)} (ok={n_ok}, failed={n_fail})", flush=True)

    write_json(os.path.join(run_dir, "manifest_distill.json"), {
        "stage": "distill", "finished_at": now_iso(),
        "experiences_ok": n_ok, "experiences_failed": n_fail,
        "per_subject_ok": per_subject, "api": client.summary(),
    })
    print(f"[distill] ok={n_ok} failed={n_fail} cost=${client.summary()['estimated_cost_usd']}")


if __name__ == "__main__":
    main()
