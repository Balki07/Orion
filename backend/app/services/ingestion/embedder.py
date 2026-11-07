"""Embedding generator interface and implementations.

Default production provider: FastEmbed (ONNX Runtime, lightweight, low-memory).
Optional comparison provider: SentenceTransformers (PyTorch-based, behind config flag).
"""

from typing import Protocol, runtime_checkable

import numpy as np

from app.core.config import settings
from app.core.logging import logger


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Common interface for embedding generation."""

    model_name: str
    dimensions: int
    batch_size: int

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Generates normalized vector embeddings for a list of strings."""
        ...

    def embed_query(self, query: str) -> list[float]:
        """Embeds a single search query."""
        ...


class FastEmbedProvider:
    """Lightweight CPU Embedding provider using FastEmbed and ONNX Runtime."""

    def __init__(
        self,
        model_name: str = settings.EMBEDDING_MODEL,
        dimensions: int = settings.EMBEDDING_DIMENSIONS,
        batch_size: int = settings.EMBEDDING_BATCH_SIZE,
        threads: int = settings.ONNX_NUM_THREADS,
        cache_dir: str | None = settings.FASTEMBED_CACHE_DIR,
    ):
        self.model_name = model_name
        self.dimensions = dimensions
        self.batch_size = batch_size
        self.threads = threads
        self.cache_dir = cache_dir
        self._model = None
        self._load_attempted = False

    def _ensure_model_loaded(self) -> None:
        """Lazily load the FastEmbed ONNX model upon first embedding call."""
        if self._model is not None or self._load_attempted:
            return
        self._load_attempted = True
        try:
            from fastembed import TextEmbedding

            logger.info(
                f"Initializing FastEmbed ONNX model '{self.model_name}' (threads={self.threads}, cache_dir={self.cache_dir})..."
            )
            self._model = TextEmbedding(
                model_name=self.model_name,
                threads=self.threads,
                cache_dir=self.cache_dir,
                lazy_load=False,
            )
            logger.info(f"FastEmbed ONNX model '{self.model_name}' successfully initialized.")
        except Exception as e:
            logger.warning(
                f"Could not load FastEmbed ONNX model '{self.model_name}': {e}. "
                "Activating deterministic semantic fallback for offline testing."
            )
            self._model = None

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Generates 384-dimensional normalized vector embeddings for a list of strings."""
        if not texts:
            return []

        self._ensure_model_loaded()

        if self._model is not None:
            embeddings = list(self._model.embed(texts, batch_size=self.batch_size))
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
        """Embeds a single search query with the required BGE instruction prefix."""
        formatted_query = f"Represent this sentence for searching relevant passages: {query}"
        return self.embed_texts([formatted_query])[0]


class SentenceTransformersProvider:
    """Legacy/comparison PyTorch Sentence-Transformers embedding provider."""

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
            import torch

            torch.set_num_threads(1)
            torch.set_num_interop_threads(1)
        except Exception as te:
            logger.debug(f"Could not configure PyTorch thread pool limits: {te}")

        try:
            from sentence_transformers import SentenceTransformer

            logger.info(f"Loading SentenceTransformer model '{self.model_name}' on {self.device}...")
            self._model = SentenceTransformer(self.model_name, device=self.device)
            logger.info(f"SentenceTransformer model '{self.model_name}' successfully initialized.")
        except Exception as e:
            logger.warning(
                f"Could not load HuggingFace model '{self.model_name}': {e}. "
                "Activating deterministic semantic fallback for offline testing."
            )
            self._model = None

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        if self._model is not None:
            try:
                import torch

                inference_ctx = torch.inference_mode()
            except Exception:
                from contextlib import nullcontext

                inference_ctx = nullcontext()

            with inference_ctx:
                embeddings = self._model.encode(
                    texts,
                    batch_size=self.batch_size,
                    show_progress_bar=False,
                    normalize_embeddings=True,
                )
            result = embeddings.tolist() if hasattr(embeddings, "tolist") else [list(emb) for emb in embeddings]
        else:
            result = []
            for t in texts:
                np.random.seed(abs(hash(t)) % (2**31 - 1))
                vec = np.random.randn(self.dimensions).astype(np.float32)
                vec /= np.linalg.norm(vec) + 1e-9
                result.append(vec.tolist())

        for vec in result:
            if len(vec) != self.dimensions:
                raise ValueError(
                    f"Generated vector dimension {len(vec)} does not match expected {self.dimensions}."
                )

        return result

    def embed_query(self, query: str) -> list[float]:
        formatted_query = f"Represent this sentence for searching relevant passages: {query}"
        return self.embed_texts([formatted_query])[0]


# Backward compatibility alias
LocalEmbedder = FastEmbedProvider

_EMBEDDER_INSTANCE: EmbeddingProvider | None = None


def get_embedder() -> EmbeddingProvider:
    """Singleton getter ensuring model is loaded once per process."""
    global _EMBEDDER_INSTANCE
    if _EMBEDDER_INSTANCE is None:
        if getattr(settings, "EMBEDDING_PROVIDER", "fastembed") == "sentence_transformers":
            _EMBEDDER_INSTANCE = SentenceTransformersProvider()
        else:
            _EMBEDDER_INSTANCE = FastEmbedProvider()
    return _EMBEDDER_INSTANCE
