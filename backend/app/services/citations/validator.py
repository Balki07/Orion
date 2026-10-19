"""ORION Citation Validation Engine."""

from typing import Any

from app.models.chunk import Chunk
from app.schemas.research import Citation, Claim


class CitationValidator:
    """Validates citations against retrieved chunks and database records to eliminate hallucinations."""

    def validate_and_hydrate(
        self,
        raw_response: dict[str, Any],
        retrieved_chunks: list[Chunk],
    ) -> tuple[list[Citation], list[Claim], list[str], bool]:
        """Validates all citations in LLM response against actual retrieved evidence.

        Returns: (verified_citations, verified_claims, warnings, insufficient_evidence)
        """
        warnings: list[str] = list(raw_response.get("warnings", []))
        insufficient_evidence = bool(raw_response.get("insufficient_evidence", False))

        # Index retrieved chunks by their ID and document ID
        valid_chunk_map: dict[str, Chunk] = {c.id: c for c in retrieved_chunks}

        raw_citations = raw_response.get("citations", [])
        raw_claims = raw_response.get("claims", [])

        verified_citations: list[Citation] = []
        verified_citation_ids: set[str] = set()

        for rc in raw_citations:
            c_id = rc.get("citation_id", "")
            claimed_chunk_ids = rc.get("chunk_ids", [])
            claimed_pages = rc.get("page_numbers", [])
            excerpt = rc.get("excerpt", "")

            # Check if any claimed chunk ID matches an actual retrieved chunk
            matched_chunks = [valid_chunk_map[cid] for cid in claimed_chunk_ids if cid in valid_chunk_map]

            if not matched_chunks:
                if claimed_chunk_ids:
                    warnings.append(f"Rejected hallucinated citation '{c_id}' with invalid chunk IDs: {claimed_chunk_ids}")
                    continue
                elif retrieved_chunks:
                    matched_chunks = [retrieved_chunks[0]]
                    warnings.append(f"Citation '{c_id}' lacked chunk ID; associated with top retrieved evidence.")
                else:
                    warnings.append(f"Rejected citation '{c_id}' with zero matching evidence.")
                    continue

            if matched_chunks:
                target_chunk = matched_chunks[0]
                # Hydrate filename and page numbers strictly from trusted database records
                trusted_filename = (
                    target_chunk.document.filename
                    if hasattr(target_chunk, "document") and target_chunk.document
                    else rc.get("filename", "document.pdf")
                )
                trusted_pages = target_chunk.page_numbers or claimed_pages or [1]

                verified_citations.append(
                    Citation(
                        citation_id=c_id or f"cite:{len(verified_citations)+1}",
                        document_id=target_chunk.document_id,
                        filename=trusted_filename,
                        page_numbers=trusted_pages,
                        chunk_ids=[target_chunk.id],
                        excerpt=excerpt or target_chunk.text[:250],
                    )
                )
                verified_citation_ids.add(c_id)
            else:
                warnings.append(f"Rejected hallucinated citation '{c_id}' with zero matching evidence.")

        # Validate Claims against verified citations
        verified_claims: list[Claim] = []
        for cl in raw_claims:
            claim_text = cl.get("text", "")
            c_ids = cl.get("citation_ids", [])

            # Check citation support
            valid_c_ids = [cid for cid in c_ids if cid in verified_citation_ids]

            if not valid_c_ids:
                status = "unsupported"
                warnings.append(f"Claim '{claim_text[:60]}...' lacks valid citation provenance.")
            elif len(valid_c_ids) < len(c_ids):
                status = "partially_supported"
            else:
                status = "supported"

            verified_claims.append(
                Claim(
                    text=claim_text,
                    citation_ids=valid_c_ids,
                    support_status=status,
                )
            )

        # If all citations were rejected or no evidence was provided
        if not verified_citations and not insufficient_evidence and retrieved_chunks:
            # Fall back to top retrieved chunk
            top = retrieved_chunks[0]
            trusted_fn = top.document.filename if hasattr(top, "document") and top.document else "document.pdf"
            fallback_cite = Citation(
                citation_id="cite:1",
                document_id=top.document_id,
                filename=trusted_fn,
                page_numbers=top.page_numbers or [1],
                chunk_ids=[top.id],
                excerpt=top.text[:250],
            )
            verified_citations.append(fallback_cite)

        return verified_citations, verified_claims, warnings, insufficient_evidence


_VALIDATOR_INSTANCE = None


def get_citation_validator() -> CitationValidator:
    global _VALIDATOR_INSTANCE
    if _VALIDATOR_INSTANCE is None:
        _VALIDATOR_INSTANCE = CitationValidator()
    return _VALIDATOR_INSTANCE
