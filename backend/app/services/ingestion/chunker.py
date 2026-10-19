"""Page-aware semantic text chunker preserving cross-page boundaries and provenance."""

import re
from dataclasses import dataclass

from app.core.config import settings
from app.services.ingestion.extractor import ExtractedPage


@dataclass
class TextChunk:
    chunk_index: int
    text: str
    page_numbers: list[int]
    character_start: int
    character_end: int
    token_count: int


class PageAwareChunker:
    def __init__(
        self,
        chunk_size: int = settings.CHUNK_SIZE,
        chunk_overlap: int = settings.CHUNK_OVERLAP,
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk_pages(self, pages: list[ExtractedPage]) -> list[TextChunk]:
        """Splits page text into overlapping semantic chunks while strictly recording all contributing page numbers."""
        chunks: list[TextChunk] = []
        if not pages:
            return chunks

        # Build an indexed stream of sentences annotated with page provenance
        annotated_units: list[tuple[str, int, int, int]] = []  # (unit_text, page_num, char_start, char_end)
        doc_char_offset = 0

        sentence_pattern = re.compile(r"(?<=[.?!])\s+(?=[A-Z0-9])|\n\n+")

        for page in pages:
            page_text = page.text
            if not page_text:
                continue

            # Split into paragraphs or sentences
            raw_splits = sentence_pattern.split(page_text)
            page_offset = 0

            for split in raw_splits:
                cleaned = split.strip()
                if not cleaned:
                    continue
                start = doc_char_offset + page_offset
                end = start + len(cleaned)
                annotated_units.append((cleaned, page.page_number, start, end))
                page_offset += len(split) + 1

            doc_char_offset += len(page_text) + 1

        if not annotated_units:
            return chunks

        # Slide window across annotated units
        chunk_idx = 0
        current_units: list[tuple[str, int, int, int]] = []
        current_len = 0

        for unit in annotated_units:
            unit_text, page_num, start, end = unit
            unit_len = len(unit_text)

            if current_units and (current_len + unit_len > self.chunk_size):
                # Finalize current chunk
                combined_text = " ".join(u[0] for u in current_units)
                # Deduplicate page numbers in order
                pages_in_chunk = sorted(list(set(u[1] for u in current_units)))
                c_start = current_units[0][2]
                c_end = current_units[-1][3]
                token_count = max(1, len(combined_text.split()))

                chunks.append(
                    TextChunk(
                        chunk_index=chunk_idx,
                        text=combined_text,
                        page_numbers=pages_in_chunk,
                        character_start=c_start,
                        character_end=c_end,
                        token_count=token_count,
                    )
                )
                chunk_idx += 1

                # Retain overlap from end of current_units
                overlap_units: list[tuple[str, int, int, int]] = []
                overlap_len = 0
                for rev_u in reversed(current_units):
                    if overlap_len + len(rev_u[0]) <= self.chunk_overlap:
                        overlap_units.insert(0, rev_u)
                        overlap_len += len(rev_u[0])
                    else:
                        break

                current_units = overlap_units
                current_len = overlap_len

            current_units.append(unit)
            current_len += unit_len

        # Flush final chunk
        if current_units:
            combined_text = " ".join(u[0] for u in current_units)
            pages_in_chunk = sorted(list(set(u[1] for u in current_units)))
            c_start = current_units[0][2]
            c_end = current_units[-1][3]
            token_count = max(1, len(combined_text.split()))

            chunks.append(
                TextChunk(
                    chunk_index=chunk_idx,
                    text=combined_text,
                    page_numbers=pages_in_chunk,
                    character_start=c_start,
                    character_end=c_end,
                    token_count=token_count,
                )
            )

        return chunks
