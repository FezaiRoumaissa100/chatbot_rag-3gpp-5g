import math
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import cfg
from src.retrieval.bm25_search import BM25Searcher
from src.retrieval.reranker import CrossEncoderReranker
from src.retrieval.router import QueryRouter
from src.retrieval.selection import balance_specs
from src.retrieval.vector_search import VectorSearcher


def _scope(scope: list[str] | None, hard: list[str] | None) -> list[str] | None:
    if hard and scope:
        return [s for s in hard if s in scope] or scope
    return hard or scope


class HybridRetriever:
    """
    Query -> release/spec routing -> dense + BM25 -> weighted RRF -> (soft boost) -> cross-encoder
    -> spec-coverage selection -> top-k.

    Every behaviour can be overridden per call, so evaluation scripts can run many configurations
    on ONE instance (models are loaded lazily and cached).
    """

    def __init__(self, routing=None, use_router=None, use_reranker=None, mode=None, embedding=None,
                 reranker=None, rrf_k=None, vector_weight=None, bm25_weight=None, soft_boost=None,
                 coverage=None, specs=None, default_release=None):
        r = cfg("retrieval")
        if routing is None:
            routing = r["routing"] if use_router is None else ("hard" if use_router else "off")
        self.routing = routing
        self.use_reranker = r["use_reranker"] if use_reranker is None else use_reranker
        self.mode = mode or r["mode"]
        self.embedding = embedding or cfg("embedding")["active"]
        self.reranker_name = reranker or cfg("reranker")["active"]
        self.rrf_k = rrf_k or r["rrf_k"]
        self.vector_weight = r["vector_weight"] if vector_weight is None else vector_weight
        self.bm25_weight = r["bm25_weight"] if bm25_weight is None else bm25_weight
        self.soft_boost = r["soft_boost"] if soft_boost is None else soft_boost
        self.coverage = r["coverage"] if coverage is None else coverage
        self.specs = specs if specs is not None else (cfg("corpus")["specs"] or None)
        self.default_release = default_release or cfg("corpus")["default_release"]
        self.router = QueryRouter()
        self._vec: dict[str, VectorSearcher] = {}
        self._rerankers: dict[str, CrossEncoderReranker] = {}
        self._bm25: BM25Searcher | None = None

    # ---- lazy components -------------------------------------------------
    def bm25(self) -> BM25Searcher:
        if self._bm25 is None:
            self._bm25 = BM25Searcher()
        return self._bm25

    def vector(self, alias: str) -> VectorSearcher:
        if alias not in self._vec:
            self._vec[alias] = VectorSearcher(alias)
        return self._vec[alias]

    def reranker(self, name: str) -> CrossEncoderReranker:
        if name not in self._rerankers:
            self._rerankers[name] = CrossEncoderReranker(name)
        return self._rerankers[name]

    def corpus_info(self) -> list[dict]:
        return self.bm25().corpus_info()

    def available_releases(self) -> list[str]:
        return sorted({c["release"] for c in self.corpus_info()})

    # ---- one retrieval over one release group ---------------------------
    def _search(self, dense_q, lex_q, specs, rels, mode, pool, embedding):
        vec = self.vector(embedding).search(dense_q, pool, specs, rels) if mode in ("hybrid", "vector") else []
        lex = self.bm25().search(lex_q, pool, specs, rels) if mode in ("hybrid", "bm25") else []
        return vec, lex

    def _retrieve_group(self, dense_q, lex_q, rerank_q, scope, hard, preferred, rels, *, mode, pool, k,
                        use_rr, embedding, reranker, coverage, routing):
        specs = _scope(scope, hard)
        vec, lex = self._search(dense_q, lex_q, specs, rels, mode, pool, embedding)
        if hard and ((mode != "bm25" and len(vec) < 3) or (mode != "vector" and len(lex) < 2)):
            vec, lex = self._search(dense_q, lex_q, scope, rels, mode, pool, embedding)  # filter too thin

        wv, wb = {"hybrid": (self.vector_weight, self.bm25_weight),
                  "vector": (1.0, 0.0), "bm25": (0.0, 1.0)}[mode]
        fused: dict[str, dict] = {}
        for it in vec:
            fused[it["chunk_id"]] = {**it, "rrf_score": wv / (self.rrf_k + it["vector_rank"]),
                                     "retrieval_sources": ["vector"]}
        for it in lex:
            contrib = wb / (self.rrf_k + it["bm25_rank"])
            if it["chunk_id"] in fused:
                f = fused[it["chunk_id"]]
                f["rrf_score"] += contrib
                f["bm25_score"], f["bm25_rank"] = it["bm25_score"], it["bm25_rank"]
                f["retrieval_sources"].append("bm25")
            else:
                fused[it["chunk_id"]] = {**it, "rrf_score": contrib, "retrieval_sources": ["bm25"]}

        if routing == "soft" and preferred and not hard:
            for c in fused.values():
                if c["metadata"]["specification"] in preferred:
                    c["rrf_score"] *= self.soft_boost

        ranked = sorted(fused.values(), key=lambda x: x["rrf_score"], reverse=True)[:pool]
        for i, c in enumerate(ranked, 1):
            c["rrf_score"], c["rrf_rank"] = round(c["rrf_score"], 5), i

        scored = self.reranker(reranker).rerank(rerank_q, ranked, top_k=len(ranked)) if use_rr else ranked
        if coverage and routing == "soft" and not hard and len(preferred) >= 2:
            return balance_specs(scored, preferred, k, cfg("retrieval")["coverage_min_per_spec"])
        return scored[:k]

    # ---- public API --------------------------------------------------------
    def retrieve(self, query: str, top_k: int | None = None, candidate_pool: int | None = None, *,
                 routing=None, mode=None, use_reranker=None, embedding=None, reranker=None,
                 coverage=None, specs=None, releases=None, compare=None,
                 dense_query=None, lexical_query=None) -> dict:
        r = cfg("retrieval")
        top_k, pool = top_k or r["top_k"], candidate_pool or r["candidate_pool"]
        routing, mode = routing or self.routing, mode or self.mode
        use_rr = self.use_reranker if use_reranker is None else use_reranker
        embedding, reranker = embedding or self.embedding, reranker or self.reranker_name
        coverage = self.coverage if coverage is None else coverage
        scope = specs if specs is not None else self.specs

        decision = self.router.route(query)
        hard, preferred = None, []
        if routing == "hard" and decision.confidence in ("explicit", "high"):
            hard = decision.target_specs
        elif routing == "soft":
            hard = decision.target_specs if decision.confidence == "explicit" else None
            preferred = [s for s in decision.preferred_specs if not scope or s in scope]

        rels = releases if releases is not None else decision.releases
        do_compare = decision.compare if compare is None else compare
        if do_compare:
            if not rels or len(rels) < 2:
                rels = self.available_releases()
            groups = [[x] for x in rels]
        else:
            groups = [rels or [self.default_release]]

        k_each = top_k if len(groups) == 1 else max(3, math.ceil(top_k / len(groups)))
        per_group = [self._retrieve_group(
            dense_query or query, lexical_query or query, query, scope, hard, preferred, g,
            mode=mode, pool=pool, k=k_each, use_rr=use_rr, embedding=embedding, reranker=reranker,
            coverage=coverage, routing=routing) for g in groups]

        if len(per_group) == 1:
            results = per_group[0]
        else:  # interleave so every release is represented in the context
            results = [c for tup in zip(*per_group) for c in tup]
            results += [c for lst in per_group for c in lst[min(map(len, per_group)):]]
        for i, c in enumerate(results, 1):
            c["final_rank"] = i

        return {
            "query": query,
            "routing": {"mode": mode, "routing": routing, "target_specs": hard,
                        "preferred_specs": preferred, "confidence": decision.confidence,
                        "reason": decision.reason, "releases": [x for g in groups for x in g],
                        "compare": do_compare},
            "results": results,
        }
