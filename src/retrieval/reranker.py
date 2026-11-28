from sentence_transformers import CrossEncoder

from src.config import cfg


class CrossEncoderReranker:
    """Re-scores (query, chunk) pairs jointly. `name` is an alias from config.yaml or a HF model id."""

    def __init__(self, name: str | None = None, max_length: int = 512):
        models = cfg("reranker")["models"]
        name = name or cfg("reranker")["active"]
        self.model_name = models.get(name, name)
        self.model = CrossEncoder(self.model_name, max_length=max_length)

    def rerank(self, query: str, candidates: list[dict], top_k: int = 5) -> list[dict]:
        if not candidates:
            return []
        scores = self.model.predict([(query, c["text"]) for c in candidates])
        out = []
        for cand, s in zip(candidates, scores):
            item = dict(cand)
            item["rerank_score"] = round(float(s), 4)
            out.append(item)
        out.sort(key=lambda x: x["rerank_score"], reverse=True)
        return out[:top_k]
