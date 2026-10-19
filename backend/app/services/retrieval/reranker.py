"""Optional Cross-Encoder Reranker."""


from app.core.config import settings
from app.core.logging import logger
from app.models.chunk import Chunk


class Reranker:
    def __init__(self, model_name: str = settings.RERANKER_MODEL, enabled: bool = settings.RERANKER_ENABLED):
        self.model_name = model_name
        self.enabled = enabled
        self._model = None
        if self.enabled:
            self._load_model()

    def _load_model(self) -> None:
        try:
            from sentence_transformers import CrossEncoder

            logger.info(f"Loading reranker model '{self.model_name}'...")
            self._model = CrossEncoder(self.model_name)
        except Exception as e:
            logger.warning(f"Could not initialize CrossEncoder reranker: {e}")
            self.enabled = False

    def rerank(
        self,
        query: str,
        candidates: list[tuple[Chunk, float]],
        top_k: int = settings.RETRIEVAL_TOP_K,
    ) -> list[tuple[Chunk, float]]:
        """Reranks retrieved candidate chunks using cross-encoder scoring."""
        if not self.enabled or not self._model or not candidates:
            return candidates[:top_k]

        pairs = [[query, chunk.text] for chunk, _ in candidates]
        try:
            scores = self._model.predict(pairs)
            scored = list(zip([c[0] for c in candidates], [float(s) for s in scores]))
            scored.sort(key=lambda x: x[1], reverse=True)
            return scored[:top_k]
        except Exception as e:
            logger.warning(f"Reranking prediction failed: {e}. Falling back to original ranking.")
            return candidates[:top_k]
