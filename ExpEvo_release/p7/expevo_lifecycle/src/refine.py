"""Backend refinement: directed BM25 similarity -> anchor grouping -> LLM condensation.

Every threshold starts from the SAME frozen full-repository snapshot.
"""
import argparse
import csv
import os
import re
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
from rank_bm25 import BM25Okapi

from .api_client import FatalAPIError, LLMClient, TransientAPIError
from .common import (append_jsonl, load_config, now_iso, read_jsonl, serialize_item,
                     write_json, write_jsonl)

SYSTEM_C = """You consolidate a group of related experience items into one reusable experience.
Merge overlapping knowledge, remove repetition, and retain useful distinctions.
Preserve supported factual statements. Do not add unrelated facts.
If items contain unresolved contradictions, do not silently choose an unsupported claim.
Return one coherent, concise, self-contained experience in plain English.
Do not reproduce the full list of inputs.
Return only the consolidated experience text."""

USER_C = """Topic: {subject}
Experience group to consolidate:
{numbered}"""

TOK = re.compile(r"[a-z0-9]+")


def tokenize(text):
    return TOK.findall(text.lower())


def build_matrix(texts, k1=1.5, b=0.75):
    corpus = [tokenize(t) for t in texts]
    bm25 = BM25Okapi(corpus, k1=k1, b=b)
    n = len(texts)
    S = np.zeros((n, n), dtype=np.float64)
    for i in range(n):
        S[i, :] = bm25.get_scores(corpus[i])
    return S, bm25


def group_ids(ids, S, threshold):
    """Literal implementation of the spec's anchor-grouping pseudocode."""
    order = list(ids)  # stable order (already sorted)
    pos = {eid: i for i, eid in enumerate(order)}
    U = set(order)
    groups = []
    for anchor in order:
        if anchor not in U:
            continue
        group = [anchor]
        for cand in order:
            if cand == anchor or cand not in U:
                continue
            if S[pos[anchor], pos[cand]] >= threshold:
                group.append(cand)
        for g in group:
            U.remove(g)
        groups.append(group)
    assert not U, "anchor grouping left items uncovered"
    flat = sorted(x for g in groups for x in g)
    assert flat == sorted(ids), "grouping does not cover exactly once"
    return groups


def condense(client, cfg, subject, texts, tag):
    numbered = "\n".join(f"{i + 1}. {t}" for i, t in enumerate(texts))
    messages = [
        {"role": "system", "content": SYSTEM_C},
        {"role": "user", "content": USER_C.format(subject=subject, numbered=numbered)},
    ]
    r = client.chat(
        messages, tag=tag,
        temperature=cfg["prompts"]["condense_temperature"],
        max_tokens=cfg["prompts"]["condense_max_tokens"],
    )
    return (r["text"] or "").strip(), r.get("prompt_hash")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--subject", default=None)
    args = ap.parse_args()
    cfg = load_config(args.config)
    run_dir = os.path.abspath(os.path.join(cfg["runtime"]["runs_dir"], cfg["run_id"]))
    client = LLMClient(cfg, run_dir)
    subjects = [args.subject] if args.subject else cfg["data"]["subjects"]
    thresholds = list(cfg["refine"]["thresholds"]) + list(cfg["refine"].get("exploratory_thresholds") or [])
    max_words = int(cfg["refine"]["max_group_words"])

    os.makedirs(os.path.join(run_dir, "bm25"), exist_ok=True)
    diag_rows = []
    for subject in subjects:
        repo = read_jsonl(os.path.join(run_dir, "full_repositories", f"{subject}.jsonl"))
        texts = [r["text"] for r in repo]
        ids = [r["experience_id"] for r in repo]
        S, bm25 = build_matrix(texts, cfg["refine"]["bm25"]["k1"], cfg["refine"]["bm25"]["b"])
        np.save(os.path.join(run_dir, "bm25", f"score_matrix_{subject}.npy"),
                S.astype(np.float32))
        iu = np.triu_indices(len(texts), k=1)
        off = S[iu]
        diag = {
            "subject": subject, "n": len(texts),
            "k1": cfg["refine"]["bm25"]["k1"], "b": cfg["refine"]["bm25"]["b"],
            "self_min": float(np.diag(S).min()), "self_median": float(np.median(np.diag(S))),
            "off_min": float(off.min()) if len(off) else 0.0,
            "off_max": float(off.max()) if len(off) else 0.0,
            "off_mean": float(off.mean()) if len(off) else 0.0,
            "off_p50": float(np.percentile(off, 50)) if len(off) else 0.0,
            "off_p75": float(np.percentile(off, 75)) if len(off) else 0.0,
            "off_p90": float(np.percentile(off, 90)) if len(off) else 0.0,
            "off_p95": float(np.percentile(off, 95)) if len(off) else 0.0,
            "off_p99": float(np.percentile(off, 99)) if len(off) else 0.0,
        }
        for th in (40, 60, 80, 100):
            diag[f"frac_pairs_ge_{th}"] = float((off >= th).mean()) if len(off) else 0.0
        diag_rows.append(diag)
        print(f"[refine] {subject:<22} n={len(texts):>4} self_med={diag['self_median']:.1f} "
              f"off_p99={diag['off_p99']:.1f} max={diag['off_max']:.1f}")

        for th in thresholds:
            groups = group_ids(ids, S, float(th))
            multi = [g for g in groups if len(g) > 1]
            slug = f"bm25_{th:g}" if float(th) == int(th) else f"bm25_{th:g}"
            out_path = os.path.join(run_dir, "refined", subject, f"{slug}.jsonl")
            groups_path = os.path.join(run_dir, "bm25", f"groups_{subject}_{slug}.json")
            write_json(groups_path, [{"anchor": g[0], "members": g, "size": len(g)} for g in groups])

            overflow = [g for g in multi
                        if sum(len(texts[ids.index(x)].split()) for x in g) > max_words]
            to_merge = [g for g in multi if g not in overflow]

            condensed = {}
            if to_merge:
                def work(g):
                    src = [texts[ids.index(x)] for x in g]
                    txt, ph = condense(client, cfg, subject, src, tag=f"condense/{subject}/{slug}")
                    return g, txt, ph

                with ThreadPoolExecutor(max_workers=cfg["runtime"]["max_concurrent"]) as ex:
                    futs = {ex.submit(work, g): g for g in to_merge}
                    for fut in as_completed(futs):
                        g, txt, ph = fut.result()
                        if not txt:
                            raise ValueError(f"empty condensation for group anchored {g[0]}")
                        condensed[tuple(g)] = (txt, ph)
                print(f"  [refine] th={th:g}: condensed {len(condensed)}/{len(multi)} groups "
                      f"(overflow={len(overflow)})")

            records = []
            for g in groups:
                src = [texts[ids.index(x)] for x in g]
                if len(g) == 1:
                    txt = src[0]
                    ph = None
                elif tuple(g) in condensed:
                    txt, ph = condensed[tuple(g)]
                else:  # context overflow: keep items unmerged, recorded as such
                    for x in g:
                        records.append({
                            "refined_id": f"ref:{x}", "subject": subject,
                            "text": texts[ids.index(x)],
                            "source_experience_ids": [x], "source_group_size": 1,
                            "threshold": th,
                            "refined_payload_bytes": len(serialize_item(subject, texts[ids.index(x)])),
                            "refinement_model_id": None,
                            "status": "context_overflow_unmerged",
                        })
                    continue
                records.append({
                    "refined_id": f"ref:{g[0]}" if len(g) > 1 else f"ref:{g[0]}",
                    "subject": subject,
                    "text": txt,
                    "source_experience_ids": list(g),
                    "source_group_size": len(g),
                    "threshold": th,
                    "refined_payload_bytes": len(serialize_item(subject, txt)),
                    "refinement_model_id": client.model if len(g) > 1 else None,
                    "status": "condensed" if len(g) > 1 else "singleton_kept",
                })
            write_jsonl(out_path, records)
            n_bytes = sum(r["refined_payload_bytes"] for r in records)
            print(f"  [refine] th={th:g}: count {len(texts)} -> {len(records)}  "
                  f"bytes {sum(len(serialize_item(subject, t)) for t in texts)} -> {n_bytes}")

    os.makedirs(os.path.join(run_dir, "tables"), exist_ok=True)
    with open(os.path.join(run_dir, "tables", "bm25_score_diagnostics.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(diag_rows[0].keys()))
        w.writeheader()
        w.writerows(diag_rows)
    write_json(os.path.join(run_dir, "manifest_refine.json"),
               {"stage": "refine", "finished_at": now_iso(),
                "thresholds": thresholds, "api": client.summary()})
    print(f"[refine] cost=${client.summary()['estimated_cost_usd']}")


if __name__ == "__main__":
    main()
