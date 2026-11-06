"""Reciprocal Rank Fusion (RRF) for hybrid retrieval ranking."""


from app.core.config import settings
from app.models.chunk import Chunk


def reciprocal_rank_fusion(
    dense_results: list[tuple[Chunk, float]],
    lexical_results: list[tuple[Chunk, float]],
    k: int = 60,
    alpha: float = settings.HYBRID_FUSION_ALPHA,
    top_k: int = settings.RETRIEVAL_TOP_K,
) -> list[tuple[Chunk, float]]:
    """Fuses ranked lists from dense vector search and lexical search using RRF.

    RRF(d) = alpha * (1 / (k + rank_dense)) + (1 - alpha) * (1 / (k + rank_lexical))
    """
    scores: dict[str, float] = {}
    chunk_map: dict[str, Chunk] = {}

    # Accumulate dense ranks
    for rank, (chunk, _) in enumerate(dense_results):
        chunk_map[chunk.id] = chunk
        scores[chunk.id] = scores.get(chunk.id, 0.0) + (alpha / (k + rank + 1))

    # Accumulate lexical ranks
    for rank, (chunk, _) in enumerate(lexical_results):
        chunk_map[chunk.id] = chunk
        scores[chunk.id] = scores.get(chunk.id, 0.0) + ((1.0 - alpha) / (k + rank + 1))

    # Sort candidates by combined RRF score
    sorted_items = sorted(scores.items(), key=lambda item: item[1], reverse=True)

    fused_results: list[tuple[Chunk, float]] = [
        (chunk_map[cid], score) for cid, score in sorted_items[:top_k]
    ]

    return fused_results


def multi_list_reciprocal_rank_fusion(
    ranked_lists: list[list[tuple[Chunk, float]]],
    weights: list[float] | None = None,
    k: int = 60,
    top_k: int = settings.RETRIEVAL_TOP_K,
) -> list[tuple[Chunk, float]]:
    """Fuses multiple ranked candidate lists using reciprocal rank fusion.

    RRF(d) = sum_i( weight_i / (k + rank_i + 1) )
    """
    scores: dict[str, float] = {}
    chunk_map: dict[str, Chunk] = {}

    if weights is None:
        weights = [1.0] * len(ranked_lists)

    for r_list, weight in zip(ranked_lists, weights):
        for rank, (chunk, _) in enumerate(r_list):
            chunk_map[chunk.id] = chunk
            scores[chunk.id] = scores.get(chunk.id, 0.0) + (weight / (k + rank + 1))

    sorted_items = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    return [(chunk_map[cid], score) for cid, score in sorted_items[:top_k]]

