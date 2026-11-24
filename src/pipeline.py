import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.retrieval.hybrid import HybridRetriever
from src.generation.generator import GeminiGenerator


class RAGPipeline:
    """
    End-to-end 3GPP 5G RAG Pipeline:
    Query -> Router -> Hybrid Search (Vector + BM25) -> Reranker -> Gemini Flash -> Cited Answer
    """

    def __init__(
        self,
        use_router: bool = False,
        use_reranker: bool = True,
        model_name: str = "gemini-3.5-flash-lite",
        top_k: int = 15,
    ):
        self.top_k = top_k
        self.retriever = HybridRetriever(
            use_router=use_router,
            use_reranker=use_reranker,
        )
        self.generator = GeminiGenerator(model_name=model_name)

    def run(self, query: str, top_k: int | None = None) -> dict:
        k = top_k or self.top_k

        # 1. Retrieval stage
        t0 = time.perf_counter()
        retrieval_output = self.retriever.retrieve(query, top_k=k)
        retrieval_ms = round((time.perf_counter() - t0) * 1000, 1)

        chunks = retrieval_output["results"]

        # 2. Generation stage
        t1 = time.perf_counter()
        answer = self.generator.generate(query, chunks)
        generation_ms = round((time.perf_counter() - t1) * 1000, 1)

        return {
            "query": query,
            "answer": answer,
            "routing": retrieval_output["routing"],
            "sources": chunks,
            "latency_ms": {
                "retrieval": retrieval_ms,
                "generation": generation_ms,
                "total": round(retrieval_ms + generation_ms, 1),
            },
        }