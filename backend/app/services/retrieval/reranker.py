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

    def _apply_source_diversity(
        self,
        candidates: list[tuple[Chunk, float]],
        required_doc_ids: set[str] | list[str] | None,
        top_k: int,
        doc_hash_map: dict[str, str] | None = None,
    ) -> list[tuple[Chunk, float]]:
        """Ensures balanced candidate representation across required source documents, collapsing duplicates."""
        if not required_doc_ids or len(required_doc_ids) <= 1:
            return candidates[:top_k]

        doc_hash_map = doc_hash_map or {}
        # Group required doc_ids by canonical source hash
        hash_to_doc_ids: dict[str, list[str]] = {}
        for did in required_doc_ids:
            h = doc_hash_map.get(did, did)
            hash_to_doc_ids.setdefault(h, []).append(did)

        # If duplicate collapsing leaves <= 1 canonical source, do not activate diversity
        if len(hash_to_doc_ids) <= 1:
            return candidates[:top_k]

        min_per_source = max(2, min(3, top_k // len(hash_to_doc_ids)))
        selected: list[tuple[Chunk, float]] = []
        selected_ids: set[str] = set()

        # Pass 1: Ensure minimum quota per distinct source group
        for h, group_doc_ids in hash_to_doc_ids.items():
            doc_cands = [c for c in candidates if getattr(c[0], "document_id", None) in group_doc_ids]
            for c in doc_cands[:min_per_source]:
                if c[0].id not in selected_ids and len(selected) < top_k:
                    selected.append(c)
                    selected_ids.add(c[0].id)

        # Pass 2: Fill remaining slots with globally top-scoring candidates
        for c in candidates:
            if len(selected) >= top_k:
                break
            if c[0].id not in selected_ids:
                selected.append(c)
                selected_ids.add(c[0].id)

        # Preserve score order among the chosen diverse set
        selected.sort(key=lambda x: x[1], reverse=True)
        return selected

    def rerank(
        self,
        query: str,
        candidates: list[tuple[Chunk, float]],
        top_k: int = settings.RETRIEVAL_TOP_K,
        required_doc_ids: set[str] | list[str] | None = None,
        doc_hash_map: dict[str, str] | None = None,
    ) -> list[tuple[Chunk, float]]:
        """Reranks retrieved candidate chunks using cross-encoder scoring with source diversity."""
        if not self.enabled or not self._model or not candidates:
            return self._apply_source_diversity(candidates, required_doc_ids, top_k, doc_hash_map)

        pairs = [[query, chunk.text] for chunk, _ in candidates]
        try:
            scores = self._model.predict(pairs)
            scored = list(zip([c[0] for c in candidates], [float(s) for s in scores]))
            scored.sort(key=lambda x: x[1], reverse=True)
            return self._apply_source_diversity(scored, required_doc_ids, top_k, doc_hash_map)
        except Exception as e:
            logger.warning(f"Reranking prediction failed: {e}. Falling back to original ranking.")
            return self._apply_source_diversity(candidates, required_doc_ids, top_k, doc_hash_map)

