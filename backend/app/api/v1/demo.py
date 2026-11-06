"""Public Demo API Endpoints.

Dedicated router providing read-only demo research paper access,
page extraction, and rate-limited, grounded Q&A over the 4-paper EPR allowlist.
Completely isolated from private researcher documents, accounts, and storage.
"""

from io import BytesIO
from fastapi import APIRouter, Depends, HTTPException, Path, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.config import settings
from app.schemas.demo import (
    DemoAskRequest,
    DemoAskResponse,
    DemoExampleQuestion,
    DemoPageResponse,
    DemoPaperItem,
    DemoStatusResponse,
)
from app.services.demo.corpus import (
    CURATED_PAPERS,
    demo_corpus_service,
)
from app.services.demo.examples import CURATED_EXAMPLES
from app.services.demo.service import demo_service


from app.security.ip_resolver import get_trusted_client_ip


def require_demo_enabled() -> None:
    """Dependency verifying that the public demo feature flag is active."""
    if not settings.ORION_ENABLE_PUBLIC_DEMO:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Public demo mode is currently disabled.",
        )


def get_client_ip(request: Request) -> str:
    """Extract securely verified client IP respecting trusted proxy configuration."""
    return get_trusted_client_ip(request)


router = APIRouter(
    prefix="/demo",
    tags=["Public Demo"],
    dependencies=[Depends(require_demo_enabled)],
)


@router.get(
    "/status",
    response_model=DemoStatusResponse,
    summary="Get demo service availability and capacity status",
)
async def get_status(db: AsyncSession = Depends(get_db)):
    """Return availability, budget metrics, and rate limit configuration."""
    return await demo_service.get_status(db)


@router.get(
    "/papers",
    response_model=list[DemoPaperItem],
    summary="List the 4 curated demo research papers",
)
def list_papers():
    """Retrieve metadata catalog for the approved open-access demo papers."""
    return demo_corpus_service.list_papers()


@router.get(
    "/papers/{document_id}",
    response_model=DemoPaperItem,
    summary="Get single demo paper metadata",
)
def get_paper(
    document_id: str = Path(..., description="Demo document identifier"),
):
    """Retrieve metadata for a specific allowlisted demo paper."""
    paper = demo_corpus_service.get_paper(document_id)
    if not paper:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Demo document '{document_id}' not found in the approved corpus allowlist.",
        )
    return paper


@router.get(
    "/papers/{document_id}/pdf",
    summary="Stream authentic demo paper PDF binary",
    response_class=StreamingResponse,
)
def get_paper_pdf(
    document_id: str = Path(..., description="Demo document identifier"),
):
    """Stream PDF binary for inspection in embedded viewer."""
    canonical_id = demo_corpus_service.resolve_paper_id(document_id)
    if not canonical_id or canonical_id not in CURATED_PAPERS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Demo document '{document_id}' not found in the approved corpus allowlist.",
        )

    pdf_bytes = demo_corpus_service.get_pdf_bytes(document_id)
    if not pdf_bytes:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"PDF for demo document '{document_id}' could not be loaded.",
        )

    paper = CURATED_PAPERS[canonical_id]
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{paper.filename}"',
            "Content-Type": "application/pdf",
            "X-Frame-Options": "SAMEORIGIN",
            "Content-Security-Policy": "default-src 'self'; frame-ancestors 'self'",
            "Cache-Control": "public, max-age=86400",
        },
    )


@router.get(
    "/papers/{document_id}/pages/{page_number}",
    response_model=DemoPageResponse,
    summary="Get extracted text for a specific demo paper page",
)
def get_paper_page(
    document_id: str = Path(..., description="Demo document identifier"),
    page_number: int = Path(..., ge=1, description="Page number (1-based index)"),
):
    """Retrieve extracted page text for ground-truth inspection and citation verification."""
    canonical_id = demo_corpus_service.resolve_paper_id(document_id)
    if not canonical_id or canonical_id not in CURATED_PAPERS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Demo document '{document_id}' not found in the approved corpus allowlist.",
        )

    page = demo_corpus_service.get_paper_page(document_id, page_number)
    if not page:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Page {page_number} does not exist for demo document '{document_id}'.",
        )
    return page


@router.get(
    "/examples",
    response_model=list[DemoExampleQuestion],
    summary="List curated example questions",
)
def list_examples():
    """Retrieve curated research questions with pre-verified ground-truth answers."""
    return CURATED_EXAMPLES


@router.post(
    "/ask",
    response_model=DemoAskResponse,
    summary="Ask a research question grounded in the demo corpus",
)
async def ask_demo_question(
    request: DemoAskRequest,
    req: Request,
    db: AsyncSession = Depends(get_db),
):
    """Execute evidence-grounded Q&A against the 4 curated demo papers."""
    client_ip = get_client_ip(req)
    return await demo_service.execute_query(request, client_ip, db)

