"""PDF text extractor preserving strict page-by-page provenance using PyMuPDF."""

from dataclasses import dataclass, field

import pymupdf

from app.core.config import settings
from app.core.errors import IngestionError


@dataclass
class ExtractedPage:
    page_number: int  # 1-indexed
    text: str
    character_count: int
    has_text: bool
    headings: list[str] = field(default_factory=list)


@dataclass
class ExtractionResult:
    pages: list[ExtractedPage]
    total_pages: int
    total_characters: int
    is_scanned_or_empty: bool
    warnings: list[str] = field(default_factory=list)


class PdfExtractor:
    def __init__(self, max_pages: int = settings.MAX_PDF_PAGES):
        self.max_pages = max_pages

    def extract_from_bytes(self, pdf_bytes: bytes, filename: str = "document.pdf") -> ExtractionResult:
        """Extracts text page by page with strict page number provenance."""
        if not pdf_bytes:
            raise IngestionError("PDF byte stream is empty.", stage="extracting")

        # Validate PDF signature magic bytes: %PDF-
        if not pdf_bytes.startswith(b"%PDF-"):
            raise IngestionError(
                "Uploaded file is missing the %PDF- header signature. Corrupt or invalid file.",
                stage="validating",
            )

        try:
            doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
        except Exception as e:
            raise IngestionError(f"Failed to parse PDF document structure: {e!s}", stage="extracting")

        total_pages = len(doc)
        if total_pages == 0:
            doc.close()
            raise IngestionError("PDF contains 0 pages.", stage="extracting")

        if total_pages > self.max_pages:
            doc.close()
            raise IngestionError(
                f"PDF has {total_pages} pages, which exceeds the limit of {self.max_pages}.",
                stage="validating",
            )

        pages: list[ExtractedPage] = []
        total_chars = 0
        pages_without_text = 0
        warnings: list[str] = []

        for page_idx in range(total_pages):
            page_num = page_idx + 1  # 1-indexed for human readability and citations
            page = doc[page_idx]

            # Extract raw plain text
            raw_text = page.get_text("text").strip()
            char_count = len(raw_text)
            total_chars += char_count

            # Simple heuristic for potential section headings
            headings: list[str] = []
            blocks = page.get_text("blocks")
            for b in blocks:
                block_text = b[4].strip()
                # If block is short, single line, and capitalized
                if 3 < len(block_text) < 80 and "\n" not in block_text:
                    if block_text[0].isupper() or block_text.split()[0].replace(".", "").isdigit():
                        headings.append(block_text)

            has_text = char_count >= 15
            if not has_text:
                pages_without_text += 1

            pages.append(
                ExtractedPage(
                    page_number=page_num,
                    text=raw_text,
                    character_count=char_count,
                    has_text=has_text,
                    headings=headings[:5],
                )
            )

        doc.close()

        # Check for scanned or image-only PDF
        is_scanned = total_chars < (total_pages * 30) or pages_without_text == total_pages
        if is_scanned:
            warnings.append(
                "Document appears to be image-only or scanned with insufficient text layer. "
                "Optical Character Recognition (OCR) is required to index content."
            )
        elif pages_without_text > 0:
            warnings.append(
                f"{pages_without_text} out of {total_pages} pages contained little or no extractable text."
            )

        return ExtractionResult(
            pages=pages,
            total_pages=total_pages,
            total_characters=total_chars,
            is_scanned_or_empty=is_scanned,
            warnings=warnings,
        )
