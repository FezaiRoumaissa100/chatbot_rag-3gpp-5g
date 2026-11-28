"""Unified retrieval experiments (supersedes eval_01 / eval_02 and covers every bonus).

    python evaluation/eval_05_retrieval_suite.py --suite core
    python evaluation/eval_05_retrieval_suite.py --suite k
    python evaluation/eval_05_retrieval_suite.py --suite embeddings     # needs: build_index --all
    python evaluation/eval_05_retrieval_suite.py --suite rerankers
    python evaluation/eval_05_retrieval_suite.py --suite scope          # impact of TS 23.502 + TS 33.501
    python evaluation/eval_05_retrieval_suite.py --suite release        # needs Rel-17 documents indexed
    python evaluation/eval_05_retrieval_suite.py --suite multilingual   # French questions
    python evaluation/eval_05_retrieval_suite.py --suite all
Every run is on ONE retriever instance; models are loaded once and cached.
"""
import argparse
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evaluation.common import (ALL_SPECS, BASE_SPECS, RESULTS_DIR, load_dataset, md_table,  # noqa: E402
                               question_of, retrieval_metrics)
from src.config import cfg  # noqa: E402

EVAL_DIR = Path(__file__).resolve().parent
CORE, EXT, FR = (EVAL_DIR / n for n in ("eval_dataset.json", "eval_dataset_ext.json", "eval_dataset_fr.json"))
TRANSLATIONS = RESULTS_DIR / "translation_cache.json"


def suite_core():
    b = {"specs": BASE_SPECS}
    return [("Full pipeline (soft routing + coverage)", {**b}), ("Hard routing (legacy)", {**b, "routing": "hard"}),
            ("No routing", {**b, "routing": "off"}), ("No reranker", {**b, "use_reranker": False}),
            ("Vector only", {**b, "mode": "vector"}), ("BM25 only", {**b, "mode": "bm25"}),
            ("No coverage guarantee", {**b, "coverage": False}), ("Candidate pool = 15 (legacy)", {**b, "candidate_pool": 15})]


def suite_k():
    return [(f"K = {k}", {"specs": BASE_SPECS, "top_k": k}) for k in (3, 5, 10, 15, 20)]


def suite_embeddings():
    cs = []
    for alias in cfg("embedding")["models"]:
        cs += [(f"{alias} | hybrid", {"specs": BASE_SPECS, "embedding": alias}),
               (f"{alias} | vector only", {"specs": BASE_SPECS, "embedding": alias, "mode": "vector"})]
    return cs


def suite_rerankers():
    return [(f"reranker = {a}", {"specs": BASE_SPECS, "reranker": a}) for a in cfg("reranker")["models"]]


def suite_scope():
    return [("Core questions | 2 specs", {"specs": BASE_SPECS}),
            ("Core questions | 4 specs", {"specs": ALL_SPECS}),
            ("Extended questions | 2 specs", {"specs": BASE_SPECS, "dataset": EXT, "cats": {"single_23502", "single_33501", "cross_4spec"}}),
            ("Extended questions | 4 specs", {"specs": ALL_SPECS, "dataset": EXT, "cats": {"single_23502", "single_33501", "cross_4spec"}})]


def suite_release():
    rel = {"dataset": EXT, "cats": {"release_17", "release_compare"}, "specs": ALL_SPECS}
    return [("Core questions | default release filter (Rel-18)", {"specs": ALL_SPECS}),
            ("Core questions | NO release filter", {"specs": ALL_SPECS, "releases": ["17", "18"], "compare": False}),
            ("Release questions | release-aware routing", {**rel}),
            ("Release questions | release-blind (always Rel-18)", {**rel, "releases": ["18"], "compare": False})]


def suite_multilingual():
    cs = []
    for alias in ("bge-base", "bge-m3"):
        for tr in (False, True):
            cs.append((f"French | {alias} | {'translated to EN' if tr else 'raw French'}",
                       {"specs": BASE_SPECS, "embedding": alias, "dataset": FR, "translate": tr}))
    return cs


SUITES = {"core": suite_core, "k": suite_k, "embeddings": suite_embeddings, "rerankers": suite_rerankers,
          "scope": suite_scope, "release": suite_release, "multilingual": suite_multilingual}


class Translator:
    def __init__(self, llm_spec):
        self.spec, self.cache = llm_spec, {}
        if TRANSLATIONS.exists():
            self.cache = json.loads(TRANSLATIONS.read_text(encoding="utf-8"))
        self.proc = None

    def __call__(self, q: str):
        from src.retrieval.query_processor import QueryProcessor, expand_acronyms
        if q not in self.cache:
            from src.generation.llm import get_llm
            self.proc = self.proc or QueryProcessor(get_llm(self.spec))
            pq = self.proc.process(q)
            if pq.error:
                raise RuntimeError(f"Translation failed: {pq.error}")
            self.cache[q] = pq.english
            TRANSLATIONS.parent.mkdir(parents=True, exist_ok=True)
            TRANSLATIONS.write_text(json.dumps(self.cache, ensure_ascii=False, indent=1), encoding="utf-8")
        en = self.cache[q]
        return en, expand_acronyms(en)


def run_config(retriever, name, conf, default_ds, args, translator):
    conf = dict(conf)
    ds_path = conf.pop("dataset", default_ds)
    cats = conf.pop("cats", None)
    translate = conf.pop("translate", False)
    top_k = conf.pop("top_k", args.k)
    pool = conf.pop("candidate_pool", args.pool)
    items = [q for q in load_dataset(ds_path) if q.get("expected_sections") and (not cats or q["category"] in cats)]
    rec, mrr, full, lat, by_cat = [], [], [], [], defaultdict(list)
    for it in items:
        q = question_of(it)
        route_q, dense, lex = q, q, q
        if translate:
            route_q, lex = translator(q)
            dense = route_q
        t = time.perf_counter()
        out = retriever.retrieve(route_q, top_k=top_k, candidate_pool=pool, dense_query=dense, lexical_query=lex, **conf)
        lat.append(time.perf_counter() - t)
        r, m = retrieval_metrics(out["results"], it["expected_sections"])
        rec.append(r), mrr.append(m), full.append(r == 1.0), by_cat[it["category"]].append(r)
    n = max(len(items), 1)
    return {"Configuration": name, "N": len(items), f"Recall@{top_k}": f"{sum(rec)/n:.3f}",
            "Full hit": f"{sum(full)/n:.3f}", "MRR": f"{sum(mrr)/n:.3f}", "Latency (s)": f"{sum(lat)/n:.2f}",
            "By category": ", ".join(f"{c}={sum(v)/len(v):.2f}" for c, v in sorted(by_cat.items()))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--suite", default="core", choices=[*SUITES, "all"])
    ap.add_argument("--dataset", default=str(CORE))
    ap.add_argument("--k", type=int, default=cfg("retrieval")["top_k"])
    ap.add_argument("--pool", type=int, default=cfg("retrieval")["candidate_pool"])
    ap.add_argument("--llm", default=cfg("generation")["default_llm"], help="LLM used to translate French questions")
    args = ap.parse_args()

    from src.retrieval.hybrid import HybridRetriever
    retriever = HybridRetriever()
    translator = Translator(args.llm)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    for suite in (SUITES if args.suite == "all" else [args.suite]):
        print(f"\n=== suite: {suite} ===")
        rows = []
        for name, conf in SUITES[suite]():
            try:
                row = run_config(retriever, name, conf, args.dataset, args, translator)
            except RuntimeError as e:
                print(f"  skipped '{name}': {e}")
                continue
            rows.append(row)
            print(f"  {name}: recall={row[[k for k in row if k.startswith('Recall')][0]]} mrr={row['MRR']}")
        if rows:
            rcol = [k for k in rows[0] if k.startswith("Recall")][0]
            cols = ["Configuration", "N", rcol, "Full hit", "MRR", "Latency (s)", "By category"]
            table = md_table(rows, cols)
            print("\n" + table)
            (RESULTS_DIR / f"eval_05_{suite}.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
            (RESULTS_DIR / f"eval_05_{suite}.md").write_text(table, encoding="utf-8")


if __name__ == "__main__":
    main()
