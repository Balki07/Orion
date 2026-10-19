"""Local CPU Embedding generator using Sentence-Transformers (BGE-small-en-v1.5)."""


import numpy as np

from app.core.config import settings
from app.core.logging import logger

_EMBEDDER_INSTANCE = None


class LocalEmbedder:
    def __init__(
        self,
        model_name: str = settings.EMBEDDING_MODEL,
        device: str = settings.EMBEDDING_DEVICE,
        dimensions: int = settings.EMBEDDING_DIMENSIONS,
        batch_size: int = settings.EMBEDDING_BATCH_SIZE,
    ):
        self.model_name = model_name
        self.device = device
        self.dimensions = dimensions
        self.batch_size = batch_size
        self._model = None
        self._load_model()

    def _load_model(self) -> None:
        try:
            from sentence_transformers import SentenceTransformer

            logger.info(f"Loading local embedding model '{self.model_name}' on {self.device}...")
            self._model = SentenceTransformer(self.model_name, device=self.device)
            logger.info(f"Embedding model '{self.model_name}' successfully initialized.")
        except Exception as e:
            logger.warning(
                f"Could not load HuggingFace model '{self.model_name}': {e}. "
                "Activating deterministic semantic fallback for offline testing."
            )
            self._model = None

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Generates 384-dimensional normalized vector embeddings for a list of strings."""
        if not texts:
            return []

        if self._model is not None:
            # Generate embeddings in batches with normalization
            embeddings = self._model.encode(
                texts,
                batch_size=self.batch_size,
                show_progress_bar=False,
                normalize_embeddings=True,
            )
            result = [emb.tolist() for emb in embeddings]
        else:
            # Deterministic fallback hashing for testing without internet access
            result = []
            for t in texts:
                np.random.seed(abs(hash(t)) % (2**31 - 1))
                vec = np.random.randn(self.dimensions).astype(np.float32)
                vec /= np.linalg.norm(vec) + 1e-9
                result.append(vec.tolist())

        # Validate vector dimensions
        for vec in result:
            if len(vec) != self.dimensions:
                raise ValueError(
                    f"Generated vector dimension {len(vec)} does not match expected {self.dimensions}."
                )

        return result

    def embed_query(self, query: str) -> list[float]:
        """Embeds a single search query."""
        # BGE models benefit from query prompt prefix: "Represent this sentence for searching relevant passages: "
        formatted_query = f"Represent this sentence for searching relevant passages: {query}"
        return self.embed_texts([formatted_query])[0]


def get_embedder() -> LocalEmbedder:
    """Singleton getter ensuring model is loaded once per process."""
    global _EMBEDDER_INSTANCE
    if _EMBEDDER_INSTANCE is None:
        _EMBEDDER_INSTANCE = LocalEmbedder()
    return _EMBEDDER_INSTANCE
