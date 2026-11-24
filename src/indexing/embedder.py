from sentence_transformers import SentenceTransformer


class TextEmbedder:
    """
    Wrapper around a local SentenceTransformer embedding model.
    Handles document encoding (for indexing) and query encoding (for retrieval).
    """

    def __init__(self, model_name: str = "BAAI/bge-base-en-v1.5"):
        self.model_name = model_name
        print(f"Loading local embedding model: {self.model_name}...")
        self.model = SentenceTransformer(self.model_name)

    def encode_documents(self, texts: list[str], batch_size: int = 128) -> list[list[float]]:
        """Encodes corpus chunks into normalized dense vectors."""
        embeddings = self.model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=False,
            normalize_embeddings=True,
        )
        return embeddings.tolist()

    def encode_query(self, query: str) -> list[float]:
        """
        Encodes a single user query into a normalized dense vector.
        Applies the BGE retrieval instruction prefix when using English BGE models.
        """
        if "bge" in self.model_name.lower() and "-en-" in self.model_name.lower():
            formatted_query = f"Represent this sentence for searching relevant passages: {query}"
        else:
            formatted_query = query

        embedding = self.model.encode(
            [formatted_query],
            normalize_embeddings=True,
        )
        return embedding[0].tolist()