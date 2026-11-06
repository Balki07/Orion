"""PDF text extractor preserving strict page-by-page provenance using PyMuPDF."""

from dataclasses import dataclass, field

import pymupdf

from app.core.config import settings
from app.core.errors import IngestionError


@dataclass
class ExtractedPage:
    page_number: int  # 1-indexed physical PDF page
    text: str
    character_count: int
    has_text: bool
    headings: list[str] = field(default_factory=list)
    page_label: str = ""  # Printed publisher page label if defined


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
            raise IngestionError(
                "Uploaded PDF byte stream is empty (0 bytes).",
                stage="extracting",
                error_code="ERR_PDF_EMPTY",
            )

        # Validate PDF signature magic bytes: %PDF-
        if not pdf_bytes.startswith(b"%PDF-"):
            raise IngestionError(
                "Uploaded file is missing the %PDF- header signature. Corrupt or invalid file.",
                stage="validating",
                error_code="ERR_PDF_CORRUPT",
            )

        try:
            doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
        except Exception as e:
            raise IngestionError(
                "The uploaded PDF is corrupted or has an invalid structure. Please verify that it opens correctly in a desktop reader.",
                stage="extracting",
                error_code="ERR_PDF_CORRUPT",
            )

        # Check for password-protected or encrypted PDFs before attempting extraction
        if doc.is_encrypted or doc.needs_pass:
            doc.close()
            raise IngestionError(
                "This PDF is password-protected or encrypted. Please remove password protection before uploading.",
                stage="validating",
                error_code="ERR_PDF_ENCRYPTED",
            )

        total_pages = len(doc)
        if total_pages == 0:
            doc.close()
            raise IngestionError(
                "The uploaded PDF file contains zero pages or no content.",
                stage="extracting",
                error_code="ERR_PDF_EMPTY",
            )

        if total_pages > self.max_pages:
            doc.close()
            raise IngestionError(
                f"PDF has {total_pages} pages, which exceeds the limit of {self.max_pages}.",
                stage="validating",
                error_code="ERR_PDF_PAGE_LIMIT",
            )

        pages: list[ExtractedPage] = []
        total_chars = 0
        pages_without_text = 0
        warnings: list[str] = []

        for page_idx in range(total_pages):
            page_num = page_idx + 1  # 1-indexed for human readability and citations
            try:
                page = doc[page_idx]
                raw_text = page.get_text("text").strip()
            except Exception as e:
                doc.close()
                raise IngestionError(
                    "The uploaded PDF is corrupted and content could not be read from all pages.",
                    stage="extracting",
                    error_code="ERR_PDF_CORRUPT",
                )

            char_count = len(raw_text)
            total_chars += char_count

            # Simple heuristic for potential section headings
            headings: list[str] = []
            try:
                blocks = page.get_text("blocks")
                for b in blocks:
                    block_text = b[4].strip()
                    # If block is short, single line, and capitalized
                    if 3 < len(block_text) < 80 and "\n" not in block_text:
                        if block_text[0].isupper() or block_text.split()[0].replace(".", "").isdigit():
                            headings.append(block_text)
            except Exception:
                pass

            has_text = char_count >= 15
            if not has_text:
                pages_without_text += 1

            page_label = page.get_label() or str(page_num)

            pages.append(
                ExtractedPage(
                    page_number=page_num,
                    text=raw_text,
                    character_count=char_count,
                    has_text=has_text,
                    headings=headings[:5],
                    page_label=page_label,
                )
            )

        doc.close()

        # Check for scanned or image-only PDF
        is_scanned = total_chars < (total_pages * 30) or pages_without_text == total_pages or total_chars == 0
        if is_scanned:
            raise IngestionError(
                "This PDF appears to contain scanned images or no extractable text. OCR is not currently supported. Please upload a text-based PDF.",
                stage="extracting",
                error_code="ERR_PDF_SCANNED_NO_TEXT",
            )

        if pages_without_text > 0:
            warnings.append(
                f"{pages_without_text} out of {total_pages} pages contained little or no extractable text."
            )

        return ExtractionResult(
            pages=pages,
            total_pages=total_pages,
            total_characters=total_chars,
            is_scanned_or_empty=False,
            warnings=warnings,
        )
