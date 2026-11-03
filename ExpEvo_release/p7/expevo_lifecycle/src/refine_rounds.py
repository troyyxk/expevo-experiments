"""ALGORITHM VARIANT: iterative (multi-round) refinement.

The paper defines a single condensation pass per threshold. This module applies
the same BM25 + anchor-grouping + LLM-condensation pass repeatedly to the output
of the previous round, which compounds the compression. It is reported
separately and must never replace the official single-pass 100/80/60/40 results.
"""
import argparse
import json
import os
from concurrent.futures import ThreadPoolExecutor

from .api_client import LLMClient
from .common import load_config, now_iso, read_jsonl, serialize_item, write_json, write_jsonl
from .refine import build_matrix, condense, group_ids


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--threshold", type=float, default=100.0)
    ap.add_argument("--rounds", type=int, default=2)
    args = ap.parse_args()
    cfg = load_config(args.config)
    run_dir = os.path.abspath(os.path.join(cfg["runtime"]["runs_dir"], cfg["run_id"]))
    client = LLMClient(cfg, run_dir)
    slug = f"bm25_{args.threshold:g}"
    summary = {"threshold": args.threshold, "rounds": [], "note": "ALGORITHM VARIANT"}

    for subject in cfg["data"]["subjects"]:
        src = read_jsonl(os.path.join(run_dir, "refined", subject, f"{slug}.jsonl"))
        items = [{"id": r["refined_id"], "text": r["text"]} for r in src]
        base_bytes = sum(len(serialize_item(subject, r["text"])) for r in src)
        round_stats = [{"round": 0, "count": len(items), "bytes": base_bytes,
                        "merged_groups": 0}]
        for rnd in range(1, args.rounds + 1):
            ids = [x["id"] for x in items]
            texts = [x["text"] for x in items]
            S, _ = build_matrix(texts, cfg["refine"]["bm25"]["k1"], cfg["refine"]["bm25"]["b"])
            groups = group_ids(ids, S, args.threshold)
            multi = [g for g in groups if len(g) > 1]
            pos = {eid: i for i, eid in enumerate(ids)}
            condensed = {}

            def work(g):
                txt, ph = condense(client, cfg, subject, [texts[pos[x]] for x in g],
                                   tag=f"condense_round/{subject}/{rnd}")
                return tuple(g), txt

            with ThreadPoolExecutor(max_workers=cfg["runtime"]["max_concurrent"]) as ex:
                for g, txt in ex.map(work, multi):
                    if not txt:
                        raise ValueError("empty condensation")
                    condensed[g] = txt
            new_items = []
            for g in groups:
                if len(g) == 1:
                    new_items.append({"id": g[0], "text": texts[pos[g[0]]]})
                else:
                    new_items.append({"id": f"{g[0]}#r{rnd}", "text": condensed[tuple(g)]})
            items = new_items
            nbytes = sum(len(serialize_item(subject, x["text"])) for x in items)
            round_stats.append({"round": rnd, "count": len(items), "bytes": nbytes,
                                "merged_groups": len(multi)})
            write_jsonl(os.path.join(run_dir, "refined_iterative", subject,
                                     f"round{rnd}.jsonl"),
                        [{"refined_id": x["id"], "subject": subject, "text": x["text"],
                          "refined_payload_bytes": len(serialize_item(subject, x["text"])),
                          "round": rnd, "variant": "iterative_condensation"} for x in items])
            print(f"[iterative] {subject:<22} round {rnd}: {len(items):>4} items, "
                  f"{nbytes:>8} B (merged {len(multi)} groups)", flush=True)
        summary["rounds"].append({"subject": subject, "stats": round_stats})

    write_json(os.path.join(run_dir, "tables", "refinement_iterative.json"), summary)
    print(f"[iterative] cost=${client.summary()['estimated_cost_usd']}")


if __name__ == "__main__":
    main()
