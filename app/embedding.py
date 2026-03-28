import logging
import os

from sentence_transformers import SentenceTransformer


logger = logging.getLogger("documind.embedding")


class EmbeddingService:
    """Wraps the sentence-transformers embedding model."""

    def __init__(self, model_name: str | None = None):
        self.model_name = model_name or os.getenv(
            "EMBEDDING_MODEL",
            "sentence-transformers/all-MiniLM-L6-v2",
        )
        logger.info("Loading embedding model: %s", self.model_name)
        self.model = SentenceTransformer(self.model_name)

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        embeddings = self.model.encode(
            texts,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        return embeddings.tolist()

    def embed_query(self, text: str) -> list[float]:
        embedding = self.model.encode(
            text,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        return embedding.tolist()
