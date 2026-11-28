"""Compares several LLMs (API vs local) on the SAME retrieved context.

    python evaluation/eval_04_llm_comparison.py \
        --llms gemini:gemini-3.5-flash-lite ollama:qwen2.5:7b-instruct ollama:llama3.1:8b

Metrics (no RAGAS quota needed): true/false refusal rate, citation accuracy and citation rate,
key-fact recall (embedding proxy), latency. Use eval_03 (RAGAS) on the winning model.
Generations are cached in evaluation/results/eval_04_cache.json, so runs can be resumed.
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evaluation.common import (ALL_SPECS, BASE_SPECS, RESULTS_DIR, citation_scores, is_refusal,  # noqa: E402
                               load_dataset, md_table, question_of)
from src.config import cfg  # noqa: E402

CACHE = RESULTS_DIR / "eval_04_cache.json"


def key_fact_recall(answer, facts, emb, thr):
    if not facts:
        return None
    sents = [s.strip(" -*•\t") for s in re.split(r"(?<=[.!?])\s+|\n+", answer) if len(s.strip()) > 8]
    if not sents:
        return 0.0
    sims = np.array(emb.encode_documents(facts)) @ np.array(emb.encode_documents(sents)).T
    return float((sims.max(axis=1) >= thr).mean())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--llms", nargs="+", required=True)
    ap.add_argument("--dataset", default=str(Path(__file__).parent / "eval_dataset.json"))
    ap.add_argument("--k", type=int, default=cfg("retrieval")["top_k"])
    ap.add_argument("--specs", choices=["base", "all"], default="base")
    ap.add_argument("--fact-threshold", type=float, default=0.72)
    ap.add_argument("--delay", type=float, default=4.5, help="pause between Gemini calls (free-tier RPM)")
    ap.add_argument("--limit", type=int)
    args = ap.parse_args()

    from src.generation.generator import RAGGenerator
    from src.generation.llm import LLMError, get_llm
    from src.indexing.embedder import TextEmbedder
    from src.retrieval.hybrid import HybridRetriever

    items = load_dataset(args.dataset)[: args.limit]
    retriever = HybridRetriever(specs=BASE_SPECS if args.specs == "base" else ALL_SPECS)
    print("Retrieving once per question...")
    contexts = {it["id"]: retriever.retrieve(question_of(it), top_k=args.k)["results"] for it in items}
    emb = TextEmbedder("bge-base")
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}

    rows = []
    for spec in args.llms:
        llm = get_llm(spec)
        gen = RAGGenerator(llm)
        print(f"\n--- {llm.label} ---")
        res = {"cit_acc": [], "cit_rate": [], "facts": [], "lat": [], "true_ref": [], "false_ref": []}
        for it in items:
            key = f"{llm.label}|{args.k}|{it['id']}"
            if key not in cache:
                for attempt in range(6):
                    try:
                        t = time.perf_counter()
                        ans = gen.generate(question_of(it), contexts[it["id"]])
                        cache[key] = {"answer": ans, "latency": time.perf_counter() - t}
                        break
                    except LLMError as e:
                        if e.status == 429 and attempt < 5:
                            print("  rate limit, waiting 35 s"); time.sleep(35)
                        else:
                            raise
                CACHE.parent.mkdir(parents=True, exist_ok=True)
                CACHE.write_text(json.dumps(cache, indent=1, ensure_ascii=False), encoding="utf-8")
                if llm.provider == "gemini":
                    time.sleep(args.delay)
            ans, lat = cache[key]["answer"], cache[key]["latency"]
            res["lat"].append(lat)
            if it["expected_sections"]:
                res["false_ref"].append(is_refusal(ans))
                cs = citation_scores(ans, contexts[it["id"]])
                if not is_refusal(ans):
                    res["cit_acc"].append(cs["citation_accuracy"]); res["cit_rate"].append(cs["has_citation"])
                f = key_fact_recall(ans, it.get("key_facts"), emb, args.fact_threshold)
                if f is not None:
                    res["facts"].append(f)
            else:
                res["true_ref"].append(is_refusal(ans))
        mean = lambda v: f"{np.mean(v):.3f}" if v else "n/a"
        rows.append({"LLM": llm.label, "Key-fact recall": mean(res["facts"]), "Citation accuracy": mean(res["cit_acc"]),
                     "Citation rate": mean(res["cit_rate"]), "False refusals": mean(res["false_ref"]),
                     "True refusals": mean(res["true_ref"]), "Latency (s)": f"{np.mean(res['lat']):.1f}"})
        print(rows[-1])

    table = md_table(rows, list(rows[0]))
    print("\n" + table)
    (RESULTS_DIR / "eval_04_llm_comparison.md").write_text(table, encoding="utf-8")
    (RESULTS_DIR / "eval_04_llm_comparison.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
