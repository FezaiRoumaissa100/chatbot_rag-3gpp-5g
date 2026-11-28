import sys
import threading
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import cfg
from src.generation.citations import validate_citations
from src.generation.generator import RAGGenerator
from src.generation.llm import LLMError, get_llm
from src.generation.prompt import REFUSAL_MESSAGE
from src.retrieval.hybrid import HybridRetriever
from src.retrieval.query_processor import QueryProcessor, is_smalltalk

SMALLTALK_REPLY = ("Hi, I’m ChatGPP. Ask me anything about the 3GPP 5G specifications "
                   "(TS 23.501, TS 24.501, TS 23.502, TS 33.501) and I’ll answer with citations.")


def parse_release(release: str | None) -> tuple[list[str] | None, bool | None]:
    """UI selector -> (releases, compare). 'auto' lets the router decide."""
    if not release or release == "auto":
        return None, None
    if release == "compare":
        return None, True
    return [release.replace("Rel-", "")], False


def slim(chunk: dict) -> dict:
    m = chunk["metadata"]
    return {"chunk_id": chunk["chunk_id"], "text": chunk["text"], "metadata": m,
            "rank": chunk.get("final_rank"), "rerank_score": chunk.get("rerank_score"),
            "rrf_score": chunk.get("rrf_score"), "retrieval_sources": chunk.get("retrieval_sources", [])}


class RAGPipeline:
    """Query -> (rewrite/translate) -> route -> hybrid retrieval -> rerank -> LLM -> cited answer."""

    def __init__(self, llm: str | None = None, routing=None, use_router=None, use_reranker=None,
                 top_k: int | None = None, candidate_pool: int | None = None, embedding=None,
                 reranker=None, model_name: str | None = None, specs=None):
        r = cfg("retrieval")
        self.top_k = top_k or r["top_k"]
        self.pool = candidate_pool or r["candidate_pool"]
        self.default_llm = llm or (f"gemini:{model_name}" if model_name else cfg("generation")["default_llm"])
        self.retriever = HybridRetriever(routing=routing, use_router=use_router, use_reranker=use_reranker,
                                         embedding=embedding, reranker=reranker, specs=specs)
        self.processor = QueryProcessor()
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    def _prepare(self, query, history, llm_spec, release, top_k):
        llm = get_llm(llm_spec or self.default_llm)
        t0 = time.perf_counter()
        pq = self.processor.process(query, history, llm)
        t1 = time.perf_counter()
        releases, compare = parse_release(release)
        with self._lock:
            out = self.retriever.retrieve(
                pq.english, top_k=top_k or self.top_k, candidate_pool=self.pool,
                dense_query=pq.english, lexical_query=pq.lexical, releases=releases, compare=compare)
        t2 = time.perf_counter()
        chunks = out["results"]
        min_score = cfg("retrieval").get("min_rerank_score")
        if min_score is not None and chunks and max(c.get("rerank_score", 0) for c in chunks) < min_score:
            chunks = []
        return llm, pq, out, chunks, {"processing": round((t1 - t0) * 1000, 1),
                                      "retrieval": round((t2 - t1) * 1000, 1)}

    def run(self, query: str, top_k: int | None = None, history=None, llm: str | None = None,
            release: str | None = None) -> dict:
        if is_smalltalk(query):
            return {"query": query, "english_query": query, "language": "en", "answer": SMALLTALK_REPLY,
                    "routing": None, "sources": [], "citations": validate_citations("", []),
                    "latency_ms": {"processing": 0, "retrieval": 0, "generation": 0, "total": 0},
                    "llm": None, "refused": False}
        llm_obj, pq, out, chunks, lat = self._prepare(query, history, llm, release, top_k)
        t = time.perf_counter()
        answer = RAGGenerator(llm_obj).generate(pq.english, chunks, compare=out["routing"]["compare"])
        lat["generation"] = round((time.perf_counter() - t) * 1000, 1)
        lat["total"] = round(sum(lat.values()), 1)
        return {"query": query, "english_query": pq.english, "language": pq.language, "answer": answer,
                "routing": out["routing"], "sources": chunks, "citations": validate_citations(answer, chunks),
                "latency_ms": lat, "llm": llm_obj.label, "refused": REFUSAL_MESSAGE.lower() in answer.lower()}

    def stream(self, query: str, top_k: int | None = None, history=None, llm: str | None = None,
               release: str | None = None):
        """Yields {'event': meta|sources|token|done, 'data': ...} dicts (SSE-ready)."""
        if is_smalltalk(query):
            yield {"event": "meta", "data": {"routing": None, "language": "en", "english_query": query,
                                             "rewritten": False, "llm": None}}
            yield {"event": "sources", "data": []}
            yield {"event": "token", "data": SMALLTALK_REPLY}
            yield {"event": "done", "data": {"citations": validate_citations("", []), "refused": False,
                                              "latency_ms": {"total": 0}, "llm": None}}
            return
        llm_obj, pq, out, chunks, lat = self._prepare(query, history, llm, release, top_k)
        yield {"event": "meta", "data": {"routing": out["routing"], "language": pq.language,
                                         "english_query": pq.english, "rewritten": pq.rewritten,
                                         "llm": llm_obj.label}}
        yield {"event": "sources", "data": [slim(c) for c in chunks]}
        t = time.perf_counter()
        parts = []
        for piece in RAGGenerator(llm_obj).stream(pq.english, chunks, compare=out["routing"]["compare"]):
            parts.append(piece)
            yield {"event": "token", "data": piece}
        answer = "".join(parts)
        lat["generation"] = round((time.perf_counter() - t) * 1000, 1)
        lat["total"] = round(sum(lat.values()), 1)
        yield {"event": "done", "data": {"citations": validate_citations(answer, chunks), "latency_ms": lat,
                                         "llm": llm_obj.label, "refused": REFUSAL_MESSAGE.lower() in answer.lower()}}
