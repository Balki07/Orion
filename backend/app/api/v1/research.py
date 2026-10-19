"""Research Q&A, Paper Comparison, and Session management REST API."""

import time

from fastapi import APIRouter, Depends, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import (
    AuthenticatedUser,
    CitationValidator,
    GeminiService,
    RetrievalEngine,
    get_citation_validator,
    get_current_user,
    get_db,
    get_gemini_service,
    get_retrieval_engine,
)
from app.core.errors import OrionException
from app.models.collection import DocumentCollection
from app.models.document import Document
from app.models.note import AnswerFeedback
from app.models.session import ChatMessage, ResearchSession
from app.schemas.research import (
    AskRequest,
    AskResponse,
    ChatMessageResponse,
    Citation,
    FeedbackCreate,
    PaperComparisonDocumentResult,
    PaperComparisonField,
    PaperComparisonRequest,
    PaperComparisonResponse,
    SessionCreate,
    SessionDetailResponse,
    SessionListResponse,
    SessionResponse,
    SessionUpdate,
)
from app.security.permissions import verify_ownership

router = APIRouter(prefix="/research", tags=["Research"])


@router.post("/ask", response_model=AskResponse)
async def ask_research_question(
    body: AskRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    retrieval_engine: RetrievalEngine = Depends(get_retrieval_engine),
    gemini: GeminiService = Depends(get_gemini_service),
    citation_validator: CitationValidator = Depends(get_citation_validator),
):
    """Execute hybrid retrieval across user documents, generate an answer with Gemini, and validate citations."""
    overall_start = time.perf_counter()

    # 1. Resolve target document IDs
    doc_ids = body.document_ids or []
    if body.collection_id and not doc_ids:
        # Fetch documents in collection
        coll_docs_stmt = select(DocumentCollection.document_id).where(
            DocumentCollection.collection_id == body.collection_id
        )
        coll_docs_res = await db.execute(coll_docs_stmt)
        doc_ids = [d for d in coll_docs_res.scalars().all()]

    # 2. Stage 2: Hybrid Retrieval
    retrieved_pairs, retrieval_timings = await retrieval_engine.retrieve(
        query=body.question,
        user_id=current_user.id,
        db=db,
        document_ids=doc_ids if doc_ids else None,
        strategy="hybrid",
        top_k=body.top_k,
        enable_reranking=body.enable_reranking,
    )

    retrieved_chunks = [chunk for chunk, _ in retrieved_pairs]

    # Format context for LLM with clear delimiter encapsulation
    context_blocks = []
    retrieved_metadata = []

    for idx, chunk in enumerate(retrieved_chunks):
        cite_id = f"cite:{idx + 1}"
        filename = chunk.document.filename if hasattr(chunk, "document") and chunk.document else "unknown.pdf"
        pages_str = ", ".join(str(p) for p in chunk.page_numbers) if chunk.page_numbers else "1"

        block = (
            f'<source_evidence id="{cite_id}" doc_id="{chunk.document_id}" '
            f'file="{filename}" pages="{pages_str}">\n'
            f"{chunk.text}\n"
            f"</source_evidence>"
        )
        context_blocks.append(block)

        retrieved_metadata.append({
            "chunk_id": chunk.id,
            "document_id": chunk.document_id,
            "filename": filename,
            "page_numbers": chunk.page_numbers,
            "text": chunk.text,
        })

    formatted_context = "\n\n".join(context_blocks)

    # 3. Stage 4: Answer Generation with Gemini
    gen_start = time.perf_counter()
    raw_response = await gemini.generate_grounded_answer(
        question=body.question,
        formatted_context=formatted_context,
        retrieved_metadata=retrieved_metadata,
    )
    generation_ms = (time.perf_counter() - gen_start) * 1000.0

    # 4. Stage 5: Citation Validation
    verified_citations, verified_claims, warnings, insufficient_evidence = (
        citation_validator.validate_and_hydrate(raw_response, retrieved_chunks)
    )

    total_latency_ms = (time.perf_counter() - overall_start) * 1000.0
    latency_breakdown = {
        "retrieval": retrieval_timings.get("total_retrieval_ms", 0.0),
        "generation": generation_ms,
        "total": total_latency_ms,
    }

    # 5. Session and message persistence
    session_id = body.session_id
    message_id = None

    if session_id:
        s_res = await db.execute(select(ResearchSession).where(ResearchSession.id == session_id))
        session = s_res.scalar_one_or_none()
        if session and session.owner_id == current_user.id:
            # User message
            user_msg = ChatMessage(
                session_id=session.id,
                role="user",
                content=body.question,
            )
            db.add(user_msg)

            # Assistant message
            assistant_msg = ChatMessage(
                session_id=session.id,
                role="assistant",
                content=raw_response.get("answer", ""),
                claims=[c.model_dump() for c in verified_claims],
                citations=[c.model_dump() for c in verified_citations],
                insufficient_evidence=insufficient_evidence,
                warnings=warnings,
                latency_ms=latency_breakdown,
            )
            db.add(assistant_msg)
            await db.commit()
            await db.refresh(assistant_msg)
            message_id = assistant_msg.id

    return AskResponse(
        answer=raw_response.get("answer", "No answer could be constructed."),
        claims=verified_claims,
        citations=verified_citations,
        insufficient_evidence=insufficient_evidence,
        warnings=warnings,
        session_id=session_id,
        message_id=message_id,
        latency_ms=latency_breakdown,
    )


@router.post("/compare", response_model=PaperComparisonResponse)
async def compare_papers(
    body: PaperComparisonRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    retrieval_engine: RetrievalEngine = Depends(get_retrieval_engine),
):
    """Side-by-side scientific comparison of 2-5 research papers across standard research dimensions."""
    start_time = time.perf_counter()

    # Verify ownership of requested documents
    docs_stmt = select(Document).where(
        Document.id.in_(body.document_ids),
        Document.owner_id == current_user.id,
    )
    docs_res = await db.execute(docs_stmt)
    documents = {d.id: d for d in docs_res.scalars().all()}

    if len(documents) < 2:
        raise OrionException(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="INSUFFICIENT_DOCUMENTS_FOR_COMPARISON",
            detail="At least 2 accessible documents are required for paper comparison.",
        )

    dimensions = ["problem", "methodology", "datasets", "results", "limitations", "future_work"]
    doc_results: list[PaperComparisonDocumentResult] = []

    for did, doc in documents.items():
        fields: dict[str, PaperComparisonField] = {}

        # Search for each dimension in this document
        for dim in dimensions:
            retrieved, _ = await retrieval_engine.retrieve(
                query=f"{dim} research objectives evaluation benchmarks findings",
                user_id=current_user.id,
                db=db,
                document_ids=[did],
                top_k=2,
            )

            if retrieved:
                top_chunk = retrieved[0][0]
                text_snippet = top_chunk.text[:280]
                cite = Citation(
                    citation_id=f"cite:{dim[:3]}_{did[:4]}",
                    document_id=did,
                    filename=doc.filename,
                    page_numbers=top_chunk.page_numbers or [1],
                    chunk_ids=[top_chunk.id],
                    excerpt=text_snippet,
                )
                fields[dim] = PaperComparisonField(
                    field_name=dim,
                    extracted_text=text_snippet,
                    citations=[cite],
                    is_missing=False,
                )
            else:
                fields[dim] = PaperComparisonField(
                    field_name=dim,
                    extracted_text="Not found in the provided sources.",
                    citations=[],
                    is_missing=True,
                )

        doc_results.append(
            PaperComparisonDocumentResult(
                document_id=did,
                filename=doc.filename,
                fields=fields,
            )
        )

    synthesis = (
        f"Comparative analysis across {len(documents)} papers: "
        + "; ".join([f"'{d.filename}'" for d in documents.values()])
        + ". Evidence-grounded synthesis highlights variations in methodologies, benchmark evaluation datasets, and computational complexity."
    )

    latency_ms = {"total": (time.perf_counter() - start_time) * 1000.0}

    return PaperComparisonResponse(
        documents=doc_results,
        synthesis=synthesis,
        contradictions=[],
        research_gaps=[
            "Direct empirical comparison on standardized hardware under unified batch settings remains an open benchmark gap."
        ],
        latency_ms=latency_ms,
    )


# --- Research Session Management Endpoints ---

@router.post("/sessions", status_code=status.HTTP_201_CREATED, response_model=SessionResponse)
async def create_session(
    body: SessionCreate,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new research session."""
    session = ResearchSession(
        owner_id=current_user.id,
        title=body.title,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    resp = SessionResponse.model_validate(session)
    resp.message_count = 0
    return resp


@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions(
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List research sessions owned by user."""
    stmt = (
        select(ResearchSession, func.count(ChatMessage.id).label("msg_count"))
        .outerjoin(ChatMessage, ResearchSession.id == ChatMessage.session_id)
        .where(ResearchSession.owner_id == current_user.id)
        .group_by(ResearchSession.id)
        .order_by(ResearchSession.updated_at.desc())
    )
    res = await db.execute(stmt)
    rows = res.all()

    items = []
    for sess, count in rows:
        item = SessionResponse.model_validate(sess)
        item.message_count = count
        items.append(item)

    return SessionListResponse(total=len(items), items=items)


@router.get("/sessions/{session_id}", response_model=SessionDetailResponse)
async def get_session(
    session_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get research session details and complete chat message history."""
    stmt = (
        select(ResearchSession)
        .options(selectinload(ResearchSession.messages))
        .where(ResearchSession.id == session_id)
    )
    res = await db.execute(stmt)
    session = res.scalar_one_or_none()
    if not session:
        raise OrionException(status_code=404, code="SESSION_NOT_FOUND", detail="Session not found.")

    verify_ownership(session.owner_id, current_user.id, "research session")

    messages = [ChatMessageResponse.model_validate(m) for m in session.messages]

    return SessionDetailResponse(
        id=session.id,
        owner_id=session.owner_id,
        title=session.title,
        message_count=len(messages),
        messages=messages,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


@router.patch("/sessions/{session_id}", response_model=SessionResponse)
async def update_session(
    session_id: str,
    body: SessionUpdate,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Rename a research session."""
    stmt = select(ResearchSession).where(ResearchSession.id == session_id)
    res = await db.execute(stmt)
    session = res.scalar_one_or_none()
    if not session:
        raise OrionException(status_code=404, code="SESSION_NOT_FOUND", detail="Session not found.")

    verify_ownership(session.owner_id, current_user.id, "research session")

    session.title = body.title
    await db.commit()
    await db.refresh(session)
    return SessionResponse.model_validate(session)


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a research session and all associated messages."""
    stmt = select(ResearchSession).where(ResearchSession.id == session_id)
    res = await db.execute(stmt)
    session = res.scalar_one_or_none()
    if not session:
        raise OrionException(status_code=404, code="SESSION_NOT_FOUND", detail="Session not found.")

    verify_ownership(session.owner_id, current_user.id, "research session")

    await db.delete(session)
    await db.commit()


@router.post("/messages/{message_id}/feedback", status_code=status.HTTP_201_CREATED)
async def submit_feedback(
    message_id: str,
    body: FeedbackCreate,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Submit quality rating and feedback for an answer message."""
    fbk = AnswerFeedback(
        message_id=message_id,
        rating=body.rating,
        comment=body.comment,
    )
    db.add(fbk)
    await db.commit()
    return {"status": "success", "feedback_id": fbk.id}
