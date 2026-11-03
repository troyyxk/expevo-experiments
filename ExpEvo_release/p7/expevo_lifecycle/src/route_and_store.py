"""Topic repository construction: freeze the full experience repository."""
import argparse
import os

from .common import load_config, now_iso, read_jsonl, serialize_item, sha256_file, write_json, write_jsonl


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    args = ap.parse_args()
    cfg = load_config(args.config)
    run_dir = os.path.abspath(os.path.join(cfg["runtime"]["runs_dir"], cfg["run_id"]))

    manifest = {"stage": "route_and_store", "finished_at": now_iso(), "subjects": {}}
    for subject in cfg["data"]["subjects"]:
        eps = {e["episode_id"]: e for e in read_jsonl(os.path.join(run_dir, "episodes", f"{subject}.jsonl"))}
        exps = read_jsonl(os.path.join(run_dir, "experiences", f"{subject}.jsonl"))
        # pairing check: every experience must trace to a real episode
        missing = [x["source_episode_id"] for x in exps if x["source_episode_id"] not in eps]
        if missing:
            raise ValueError(f"{subject}: {len(missing)} experiences without an episode")
        exps.sort(key=lambda x: x["experience_id"])
        repo = []
        for x in exps:
            repo.append({
                "experience_id": x["experience_id"],
                "subject": subject,
                "text": x["text"],
                "distilled_payload_bytes": len(serialize_item(subject, x["text"])),
                "source_episode_id": x["source_episode_id"],
            })
        path = os.path.join(run_dir, "full_repositories", f"{subject}.jsonl")
        write_jsonl(path, repo)
        manifest["subjects"][subject] = {
            "n_episodes": len(eps),
            "n_experiences": len(exps),
            "full_count": len(repo),
            "full_bytes": sum(r["distilled_payload_bytes"] for r in repo),
            "snapshot_sha256": sha256_file(path),
        }
        print(f"[store] {subject:<22} episodes={len(eps):>4} experiences={len(exps):>4} "
              f"full={len(repo):>4} bytes={manifest['subjects'][subject]['full_bytes']:>8}")

    write_json(os.path.join(run_dir, "full_repositories", "snapshots.json"), manifest)


if __name__ == "__main__":
    main()
