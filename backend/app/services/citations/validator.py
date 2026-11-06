"""ORION Citation Validation Engine."""

import re
from typing import Any

from app.core.config import settings
from app.models.chunk import Chunk
from app.schemas.research import Citation, Claim
from app.services.retrieval.query_processor import resolve_citation_page



def clean_excerpt_boundary(text: str, max_chars: int = 280) -> str:
    """Ensures fallback excerpts do not end abruptly mid-word or without boundary."""
    cleaned = re.sub(r"\s+", " ", text).strip()
    if len(cleaned) <= max_chars:
        return cleaned
    truncated = cleaned[:max_chars]
    last_punct = max(truncated.rfind("."), truncated.rfind("!"), truncated.rfind("?"))
    if last_punct > 50:
        return truncated[:last_punct + 1]
    last_space = truncated.rfind(" ")
    if last_space > 40:
        return truncated[:last_space] + "..."
    return truncated


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

        # Index retrieved chunks by their ID, citation tag (e.g. cite:1), and index
        valid_chunk_map: dict[str, Chunk] = {c.id: c for c in retrieved_chunks}
        for idx, c in enumerate(retrieved_chunks):
            valid_chunk_map[f"cite:{idx+1}"] = c
            valid_chunk_map[f"cite:{idx+1}".lower()] = c
            valid_chunk_map[str(idx + 1)] = c

        raw_citations = raw_response.get("citations", [])
        raw_claims = raw_response.get("claims", [])

        verified_citations: list[Citation] = []
        verified_citation_ids: set[str] = set()

        for rc in raw_citations:
            c_id = rc.get("citation_id", "")
            claimed_chunk_ids = rc.get("chunk_ids", [])
            claimed_pages = rc.get("page_numbers", [])
            claimed_doc_id = rc.get("document_id")
            excerpt = rc.get("excerpt", "")

            # Check if claimed chunk ID matches an actual retrieved chunk or cite handle
            matched_chunks = [valid_chunk_map[cid] for cid in claimed_chunk_ids if cid in valid_chunk_map]

            if not matched_chunks:
                if claimed_chunk_ids:
                    warnings.append(f"Rejected hallucinated citation '{c_id}' with invalid chunk IDs: {claimed_chunk_ids}")
                    continue
                elif c_id and c_id in valid_chunk_map:
                    matched_chunks = [valid_chunk_map[c_id]]
                else:
                    warnings.append(f"Rejected invalid citation '{c_id}' with zero matching evidence.")
                    continue

            if matched_chunks:
                target_chunk = matched_chunks[0]

                # Check for mismatched document ID
                if claimed_doc_id and claimed_doc_id != target_chunk.document_id:
                    warnings.append(
                        f"Rejected mismatched citation '{c_id}': claimed document '{claimed_doc_id}' "
                        f"does not match actual chunk document '{target_chunk.document_id}'."
                    )
                    continue

                # Hydrate filename and page numbers strictly from trusted database records
                trusted_filename = (
                    target_chunk.document.filename
                    if hasattr(target_chunk, "document") and target_chunk.document
                    else rc.get("filename", "document.pdf")
                )
                trusted_pages = target_chunk.page_numbers or claimed_pages or [1]
                if getattr(settings, "FLAG_CITATION_PAGE_ACCURACY", False):
                    resolved_page = resolve_citation_page(
                        excerpt or target_chunk.text, target_chunk.text, trusted_pages
                    )
                    trusted_pages = [resolved_page]
                elif claimed_pages and len(claimed_pages) == 1 and claimed_pages[0] in trusted_pages:
                    trusted_pages = claimed_pages

                verified_citations.append(
                    Citation(
                        citation_id=c_id or f"cite:{len(verified_citations)+1}",
                        document_id=target_chunk.document_id,
                        filename=trusted_filename,
                        page_numbers=trusted_pages,
                        chunk_ids=[c.id for c in matched_chunks],
                        excerpt=excerpt or clean_excerpt_boundary(target_chunk.text),
                    )
                )
                verified_citation_ids.add(c_id)
            else:
                warnings.append(f"Rejected hallucinated citation '{c_id}' with zero matching evidence.")

        # Map each verified citation ID directly to its verified Chunk object(s)
        cite_id_to_chunks: dict[str, list[Chunk]] = {}
        for vc in verified_citations:
            chunks_for_vc = [valid_chunk_map[cid] for cid in vc.chunk_ids if cid in valid_chunk_map]
            if chunks_for_vc:
                cite_id_to_chunks[vc.citation_id] = chunks_for_vc
                cite_id_to_chunks[vc.citation_id.lower()] = chunks_for_vc

        # Validate Claims against verified citations
        verified_claims: list[Claim] = []
        for cl in raw_claims:
            claim_text = cl.get("text") or cl.get("statement") or cl.get("claim") or ""
            c_ids = cl.get("citation_ids", [])

            # Check citation support
            valid_c_ids = [cid for cid in c_ids if cid in verified_citation_ids]

            # Explicit disclosure statements acknowledge lack of evidence and must be exempt from unsupported-claim penalty
            is_disclosure = bool(
                re.search(r"(?i)the selected literature does not report", claim_text)
                or re.search(r"(?i)insufficient evidence in selected literature to substantiate", claim_text)
            )

            if not valid_c_ids:
                if is_disclosure:
                    status = "supported"
                else:
                    status = "unsupported"
                    if cl.get("support_status") != "unsupported":
                        warnings.append(f"Claim '{claim_text[:60]}...' lacks valid citation provenance.")
            elif len(valid_c_ids) < len(c_ids):
                status = "partially_supported"
            else:
                status = "supported"

            # Check numerical claims integrity against supporting evidence
            if status == "supported" and valid_c_ids:
                # Exclude filenames (e.g. s40726-025-00392-4.pdf) and citation tags from numerical extraction
                clean_num_text = re.sub(r"\b[\w.-]+\.pdf\b", "", claim_text, flags=re.IGNORECASE)
                clean_num_text = re.sub(r"\[cite:\d+\]", "", clean_num_text, flags=re.IGNORECASE)
                claim_nums = re.findall(r"\b\d+(?:[\.,]\d+)?%?\b", clean_num_text)
                substantive_nums = [
                    n.replace(",", "")
                    for n in claim_nums
                    if len(n) > 2 or "." in n or "%" in n
                ]
                if substantive_nums:
                    supporting_chunks: list[Chunk] = []
                    for cid in valid_c_ids:
                        if cid in cite_id_to_chunks:
                            supporting_chunks.extend(cite_id_to_chunks[cid])
                        elif cid in valid_chunk_map:
                            supporting_chunks.append(valid_chunk_map[cid])

                    # Deduplicate chunks while preserving order
                    seen_cids: set[str] = set()
                    unique_supporting_chunks: list[Chunk] = []
                    for sc in supporting_chunks:
                        if sc.id not in seen_cids:
                            seen_cids.add(sc.id)
                            unique_supporting_chunks.append(sc)

                    supporting_text = " ".join(c.text.replace(",", "") for c in unique_supporting_chunks)
                    unsupported_nums = [n for n in substantive_nums if n not in supporting_text]
                    if unsupported_nums:
                        status = "unsupported"
                        warnings.append(
                            f"Claim '{claim_text[:60]}...' contains unverified numerical figures not substantiated by cited evidence: {unsupported_nums}"
                        )

            verified_claims.append(
                Claim(
                    text=claim_text,
                    citation_ids=valid_c_ids,
                    support_status=status,
                )
            )

        # If NO citations were provided by the model at all and evidence was retrieved
        if not verified_citations and not raw_citations and not insufficient_evidence and retrieved_chunks:
            # Fall back to top retrieved chunk
            top = retrieved_chunks[0]
            trusted_fn = top.document.filename if hasattr(top, "document") and top.document else "document.pdf"
            fallback_cite = Citation(
                citation_id="cite:1",
                document_id=top.document_id,
                filename=trusted_fn,
                page_numbers=top.page_numbers or [1],
                chunk_ids=[top.id],
                excerpt=clean_excerpt_boundary(top.text),
            )
            verified_citations.append(fallback_cite)

        return verified_citations, verified_claims, warnings, insufficient_evidence


_VALIDATOR_INSTANCE = None


def get_citation_validator() -> CitationValidator:
    global _VALIDATOR_INSTANCE
    if _VALIDATOR_INSTANCE is None:
        _VALIDATOR_INSTANCE = CitationValidator()
    return _VALIDATOR_INSTANCE
