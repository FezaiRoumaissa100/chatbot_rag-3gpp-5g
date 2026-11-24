import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.retrieval.router import QueryRouter
from src.retrieval.vector_search import VectorSearcher
from src.retrieval.bm25_search import BM25Searcher
from src.retrieval.reranker import CrossEncoderReranker


class HybridRetriever:
    """
    Full 3GPP Retrieval Pipeline:
    1. Specification Routing (TS 23.501 vs TS 24.501 vs cross-spec)
    2. Parallel Dense (Vector) + Sparse (BM25) Search
    3. Reciprocal Rank Fusion (RRF)
    4. Cross-Encoder Reranking -> Top-K chunks
    """

    def __init__(
        self,
        use_router: bool = True,
        use_reranker: bool = True,
        rrf_k: int = 60,
        vector_weight: float = 0.6,
        bm25_weight: float = 0.4,
    ):
        self.use_router = use_router
        self.use_reranker = use_reranker
        self.rrf_k = rrf_k
        self.vector_weight = vector_weight
        self.bm25_weight = bm25_weight

        self.router = QueryRouter() if use_router else None
        self.vector_searcher = VectorSearcher()
        self.bm25_searcher = BM25Searcher()
        self.reranker = CrossEncoderReranker() if use_reranker else None

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        candidate_pool: int = 15,
    ) -> dict:
        route_info = None
        target_specs = None
        if self.router:
            decision = self.router.route(query)
            route_info = {
                "target_specs": decision.target_specs,
                "confidence": decision.confidence,
                "reason": decision.reason,
            }
            if decision.confidence in ("explicit", "high"):
                target_specs = decision.target_specs

        vec_hits = self.vector_searcher.search(query, top_k=candidate_pool, target_specs=target_specs)
        bm25_hits = self.bm25_searcher.search(query, top_k=candidate_pool, target_specs=target_specs)

        if target_specs and (len(vec_hits) < 3 or len(bm25_hits) < 2):
            vec_hits = self.vector_searcher.search(query, top_k=candidate_pool, target_specs=None)
            bm25_hits = self.bm25_searcher.search(query, top_k=candidate_pool, target_specs=None)

        fused: dict[str, dict] = {}

        for item in vec_hits:
            cid = item["chunk_id"]
            rrf_contrib = self.vector_weight / (self.rrf_k + item["vector_rank"])
            fused[cid] = {
                **item,
                "rrf_score": rrf_contrib,
                "retrieval_sources": ["vector"],
            }

        for item in bm25_hits:
            cid = item["chunk_id"]
            rrf_contrib = self.bm25_weight / (self.rrf_k + item["bm25_rank"])
            if cid in fused:
                fused[cid]["rrf_score"] += rrf_contrib
                fused[cid]["bm25_score"] = item["bm25_score"]
                fused[cid]["bm25_rank"] = item["bm25_rank"]
                fused[cid]["retrieval_sources"].append("bm25")
            else:
                fused[cid] = {
                    **item,
                    "rrf_score": rrf_contrib,
                    "retrieval_sources": ["bm25"],
                }

        ranked_candidates = sorted(
            fused.values(),
            key=lambda x: x["rrf_score"],
            reverse=True,
        )[:candidate_pool]

        for idx, cand in enumerate(ranked_candidates, start=1):
            cand["rrf_score"] = round(cand["rrf_score"], 5)
            cand["rrf_rank"] = idx

        if self.reranker:
            final_results = self.reranker.rerank(query, ranked_candidates, top_k=top_k)
        else:
            final_results = ranked_candidates[:top_k]

        return {
            "query": query,
            "routing": route_info,
            "results": final_results,
        }