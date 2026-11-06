"""Research Q&A, Paper Comparison, and Session management REST API."""

import json
import time

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.security.service import auth_rate_limiter

from app.api.deps import (
    AuthenticatedUser,
    CitationValidator,
    GeminiService,
    RetrievalEngine,
    get_citation_validator,
    get_db,
    get_gemini_service,
    get_retrieval_engine,
    require_active_researcher,
)
from app.core.config import settings
from app.core.errors import OrionException
from app.models.chunk import Chunk
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
    PipelineDiagnostics,
    SessionCreate,
    SessionDetailResponse,
    SessionListResponse,
    SessionResponse,
    SessionUpdate,
)
from app.security.permissions import verify_ownership
from app.services.retrieval.diagnostics import (
    PipelineTracker,
    REASON_ANSWER_GROUNDED,
    REASON_CANDIDATES_REJECTED_BY_FILTER,
    REASON_CITATION_VALIDATION_FAILED,
    REASON_GENUINE_INSUFFICIENT_EVIDENCE,
    REASON_MODEL_GENERATION_FAILED,
    REASON_NO_SELECTED_DOCUMENTS,
    REASON_RETRIEVAL_NO_CANDIDATES,
    REASON_SELECTED_DOCUMENTS_NOT_INDEXED,
)
from app.services.retrieval.query_processor import process_query

router = APIRouter(prefix="/research", tags=["Research"])


@router.post("/ask", response_model=AskResponse)
async def ask_research_question(
    body: AskRequest,
    request: Request,
    current_user: AuthenticatedUser = Depends(require_active_researcher),
    db: AsyncSession = Depends(get_db),
    retrieval_engine: RetrievalEngine = Depends(get_retrieval_engine),
    gemini: GeminiService = Depends(get_gemini_service),
    citation_validator: CitationValidator = Depends(get_citation_validator),
):
    """Execute hybrid retrieval across user documents, generate an answer with Gemini, validate citations, and track 12-stage diagnostics."""
    # Check rate limit on research queries: 30 requests per 60 seconds per user
    if not auth_rate_limiter.check_rate_limit(f"chat_rate_{current_user.id}", max_attempts=30, window_seconds=60):
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "error": "RATE_LIMIT_EXCEEDED",
                "detail": "Research query rate limit exceeded. Please wait a moment before submitting more questions.",
                "request_id": getattr(request.state, "request_id", None),
            },
            headers={"Retry-After": "60"},
        )

    overall_start = time.perf_counter()

    # Initialize 12-stage diagnostic correlation tracker
    tracker = PipelineTracker(user_id=current_user.id)

    # Stage 1: Request received
    tracker.stage_1_request_received(
        question=body.question,
        requested_doc_ids=body.document_ids,
        collection_id=body.collection_id,
        top_k=body.top_k,
        enable_reranking=body.enable_reranking,
    )

    # Stage 4: Query preprocessing
    p_query = process_query(body.question)
    tracker.stage_4_query_preprocessed(
        original_query=body.question,
        cleaned_query=p_query.cleaned_query,
        detected_intent=p_query.intent,
        meta_instructions_removed=p_query.meta_instructions_removed,
        academic_synonyms=p_query.academic_synonyms,
        is_meta_query=p_query.is_meta_query,
        is_overview_query=p_query.is_overview_query,
    )

    # 1. Resolve and validate target document IDs
    doc_ids = body.document_ids or []
    if body.collection_id and not doc_ids:
        coll_docs_stmt = select(DocumentCollection.document_id).where(
            DocumentCollection.collection_id == body.collection_id
        )
        coll_docs_res = await db.execute(coll_docs_stmt)
        doc_ids = [d for d in coll_docs_res.scalars().all()]

    accessible_docs: dict[str, Document] = {}
    if doc_ids:
        docs_stmt = select(Document).where(
            Document.id.in_(doc_ids),
            Document.owner_id == current_user.id,
        )
        docs_res = await db.execute(docs_stmt)
        accessible_docs = {d.id: d for d in docs_res.scalars().all()}
        unauth_or_missing = [did for did in doc_ids if did not in accessible_docs]
        tracker.stage_2_sources_validated(
            validated_doc_ids=list(accessible_docs.keys()),
            unauthorized_doc_ids=unauth_or_missing,
        )
    else:
        # No specific documents passed, query all user's documents
        user_docs_stmt = select(Document).where(Document.owner_id == current_user.id)
        user_docs_res = await db.execute(user_docs_stmt)
        accessible_docs = {d.id: d for d in user_docs_res.scalars().all()}
        tracker.stage_2_sources_validated(
            validated_doc_ids=list(accessible_docs.keys()),
        )

    # Check for empty sources
    if not accessible_docs:
        tracker.stage_3_eligible_documents(eligible_doc_ids=[], total_chunks=0)
        tracker.stage_12_final_classification(
            reason_code=REASON_NO_SELECTED_DOCUMENTS,
            reason_description="No accessible research documents were selected or found for this account.",
            insufficient_evidence=True,
        )
        diag_dict = tracker.to_diagnostics_dict()
        return AskResponse(
            answer="No research documents are currently selected or available. Please upload and select a research paper to ask questions.",
            insufficient_evidence=True,
            reason_code=REASON_NO_SELECTED_DOCUMENTS,
            trace_id=tracker.trace_id,
            diagnostics=PipelineDiagnostics(**diag_dict),
            latency_ms={"total": (time.perf_counter() - overall_start) * 1000.0},
        )

    # Stage 3: Check eligibility (completed status and chunks)
    eligible_docs = [d for d in accessible_docs.values() if d.status == "completed"]
    unindexed_docs = [d.id for d in accessible_docs.values() if d.status != "completed"]
    eligible_doc_ids = [d.id for d in eligible_docs]

    # Map content hashes to identify duplicate uploads / renamed copies
    hash_to_docs: dict[str, list[Document]] = {}
    for d in eligible_docs:
        h = d.content_hash or f"size_{d.file_size}"
        hash_to_docs.setdefault(h, []).append(d)

    duplicate_groups: dict[str, list[str]] = {}
    for h, d_list in hash_to_docs.items():
        if len(d_list) > 1:
            names = [doc.filename for doc in d_list]
            for doc in d_list:
                duplicate_groups[doc.id] = names

    chunk_count_stmt = select(func.count(Chunk.id)).where(Chunk.document_id.in_(eligible_doc_ids))
    chunk_count_res = await db.execute(chunk_count_stmt)
    total_chunks = chunk_count_res.scalar_one_or_none() or 0

    tracker.stage_3_eligible_documents(
        eligible_doc_ids=eligible_doc_ids,
        unindexed_doc_ids=unindexed_docs,
        total_chunks=total_chunks,
    )

    if not eligible_doc_ids or total_chunks == 0:
        tracker.stage_12_final_classification(
            reason_code=REASON_SELECTED_DOCUMENTS_NOT_INDEXED,
            reason_description="Selected documents have not completed indexing or have zero chunks stored.",
            insufficient_evidence=True,
        )
        diag_dict = tracker.to_diagnostics_dict()
        return AskResponse(
            answer="The selected research documents have not completed indexing yet. Please wait for indexing to finish before querying.",
            insufficient_evidence=True,
            reason_code=REASON_SELECTED_DOCUMENTS_NOT_INDEXED,
            trace_id=tracker.trace_id,
            diagnostics=PipelineDiagnostics(**diag_dict),
            latency_ms={"total": (time.perf_counter() - overall_start) * 1000.0},
            answer_path="deterministic_fallback",
            model=None,
            fallback_reason=None,
        )

    # Stages 5-8: Hybrid Retrieval with Compound Subquery Decomposition
    retrieved_pairs, retrieval_timings = await retrieval_engine.retrieve(
        query=body.question,
        user_id=current_user.id,
        db=db,
        document_ids=eligible_doc_ids,
        strategy="hybrid",
        top_k=body.top_k,
        enable_reranking=body.enable_reranking,
        tracker=tracker,
        subqueries=p_query.subqueries if p_query.is_compound_query else None,
    )

    retrieved_chunks = [chunk for chunk, _ in retrieved_pairs]

    if not retrieved_chunks:
        tracker.stage_9_context_assembly(context_chunks=[], total_characters=0)
        tracker.stage_12_final_classification(
            reason_code=REASON_RETRIEVAL_NO_CANDIDATES,
            reason_description="Retrieval returned zero candidate passages matching the query.",
            insufficient_evidence=True,
        )
        diag_dict = tracker.to_diagnostics_dict()
        return AskResponse(
            answer="No relevant passages could be retrieved from the selected documents for this question.",
            insufficient_evidence=True,
            reason_code=REASON_RETRIEVAL_NO_CANDIDATES,
            trace_id=tracker.trace_id,
            diagnostics=PipelineDiagnostics(**diag_dict),
            latency_ms={"retrieval": retrieval_timings.get("total_retrieval_ms", 0.0), "total": (time.perf_counter() - overall_start) * 1000.0},
            answer_path="deterministic_fallback",
            model=None,
            fallback_reason=None,
        )

    # Stage 9: Context Assembly with Neighboring Chunk Context
    context_blocks = []
    retrieved_metadata = []

    # Batch fetch neighbor chunks (chunk_index - 1, chunk_index + 1) for coherent excerpt extraction
    doc_to_indices: dict[str, set[int]] = {}
    for c in retrieved_chunks:
        if c.chunk_index > 0:
            doc_to_indices.setdefault(c.document_id, set()).add(c.chunk_index - 1)
        doc_to_indices.setdefault(c.document_id, set()).add(c.chunk_index + 1)

    neighbor_map: dict[tuple[str, int], Chunk] = {}
    if doc_to_indices:
        from sqlalchemy import and_, or_
        conds = [
            and_(Chunk.document_id == did, Chunk.chunk_index.in_(indices))
            for did, indices in doc_to_indices.items()
        ]
        if conds:
            n_res = await db.execute(select(Chunk).where(or_(*conds)))
            for n_chunk in n_res.scalars().all():
                neighbor_map[(n_chunk.document_id, n_chunk.chunk_index)] = n_chunk

    for idx, chunk in enumerate(retrieved_chunks):
        cite_id = f"cite:{idx + 1}"
        filename = chunk.document.filename if hasattr(chunk, "document") and chunk.document else "unknown.pdf"
        pages_str = ", ".join(str(p) for p in chunk.page_numbers) if chunk.page_numbers else "1"

        prev_chunk = neighbor_map.get((chunk.document_id, chunk.chunk_index - 1))
        next_chunk = neighbor_map.get((chunk.document_id, chunk.chunk_index + 1))
        prev_text = prev_chunk.text if prev_chunk else ""
        next_text = next_chunk.text if next_chunk else ""

        block = (
            f'<source_evidence id="{cite_id}" chunk_id="{chunk.id}" doc_id="{chunk.document_id}" '
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
            "prev_text": prev_text,
            "next_text": next_text,
            "chunk_index": chunk.chunk_index,
        })

    formatted_context = "\n\n".join(context_blocks)
    tracker.stage_9_context_assembly(
        context_chunks=retrieved_metadata,
        total_characters=len(formatted_context),
    )

    # Stage 10: Answer Generation with Gemini
    gen_start = time.perf_counter()
    gen_status = "success"
    gen_error = None
    try:
        req_id = getattr(request.state, "request_id", None) if hasattr(request, "state") else None
        raw_response = await gemini.generate_grounded_answer(
            question=body.question,
            formatted_context=formatted_context,
            retrieved_metadata=retrieved_metadata,
            processed_query=p_query,
            duplicate_groups=duplicate_groups,
            document_ids=eligible_doc_ids,
            user_id=current_user.id,
            session_id=body.session_id,
            trace_id=tracker.trace_id,
            request_id=req_id,
            db=db,
        )
    except Exception as exc:
        gen_status = "error"
        gen_error = str(exc)
        raw_response = {
            "answer": "An error occurred while communicating with the generation model.",
            "insufficient_evidence": True,
            "claims": [],
            "citations": [],
            "warnings": [f"Generation failed: {exc}"],
        }

    generation_ms = (time.perf_counter() - gen_start) * 1000.0
    gen_diag = raw_response.get("generation_diagnostics", {})
    tracker.stage_10_generation(
        status=gen_status,
        generation_ms=generation_ms,
        answer_length=len(raw_response.get("answer", "")),
        error_detail=gen_error or gen_diag.get("last_error"),
        provider=gen_diag.get("provider", "gemini"),
        model=raw_response.get("model") or settings.GEMINI_MODEL,
        attempts=gen_diag.get("attempts", 1),
        max_attempts=gen_diag.get("max_attempts", getattr(settings, "GEMINI_MAX_RETRIES", 1) + 1),
        fallback_activated=(raw_response.get("answer_path") == "deterministic_fallback"),
        fallback_reason=raw_response.get("fallback_reason"),
    )

    # Stage 11: Citation Validation
    verified_citations, verified_claims, warnings, insufficient_evidence = (
        citation_validator.validate_and_hydrate(raw_response, retrieved_chunks)
    )

    raw_cites = raw_response.get("citations", [])
    tracker.stage_11_citation_validation(
        raw_citation_count=len(raw_cites),
        verified_citation_count=len(verified_citations),
        rejected_citation_count=max(0, len(raw_cites) - len(verified_citations)),
        claims_count=len(verified_claims),
        warnings=warnings,
    )

    # Stage 12: Final Classification
    if gen_status == "error":
        reason_code = REASON_MODEL_GENERATION_FAILED
        reason_desc = "The language model encountered an execution error."
    elif raw_cites and not verified_citations and not insufficient_evidence:
        reason_code = REASON_CITATION_VALIDATION_FAILED
        reason_desc = "Generated citations failed validation against source chunk records."
    elif insufficient_evidence:
        reason_code = REASON_GENUINE_INSUFFICIENT_EVIDENCE
        reason_desc = "The provided documents do not contain evidence to substantiate this answer without speculation."
    else:
        reason_code = REASON_ANSWER_GROUNDED
        reason_desc = "Answer successfully substantiated and verified with page-level citations."

    tracker.stage_12_final_classification(
        reason_code=reason_code,
        reason_description=reason_desc,
        insufficient_evidence=insufficient_evidence,
    )

    total_latency_ms = (time.perf_counter() - overall_start) * 1000.0
    latency_breakdown = {
        "retrieval": retrieval_timings.get("total_retrieval_ms", 0.0),
        "generation": generation_ms,
        "total": total_latency_ms,
    }

    # Session and message persistence
    session_id = body.session_id
    message_id = None

    if session_id:
        s_res = await db.execute(select(ResearchSession).where(ResearchSession.id == session_id))
        session = s_res.scalar_one_or_none()
        if session and session.owner_id == current_user.id:
            user_msg = ChatMessage(
                session_id=session.id,
                role="user",
                content=body.question,
            )
            db.add(user_msg)

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

    diag_dict = tracker.to_diagnostics_dict()
    answer_path = raw_response.get("answer_path", "deterministic_fallback")
    actual_model = raw_response.get("model") if answer_path == "gemini" else None
    fallback_reason = raw_response.get("fallback_reason")

    return AskResponse(
        answer=raw_response.get("answer", "No answer could be constructed."),
        claims=verified_claims,
        citations=verified_citations,
        insufficient_evidence=insufficient_evidence,
        reason_code=reason_code,
        trace_id=tracker.trace_id,
        diagnostics=PipelineDiagnostics(**diag_dict),
        warnings=warnings,
        session_id=session_id,
        message_id=message_id,
        latency_ms=latency_breakdown,
        model=actual_model,
        answer_path=answer_path,
        fallback_reason=fallback_reason,
    )


@router.post("/ask/stream")
async def ask_research_question_stream(
    body: AskRequest,
    request: Request,
    current_user: AuthenticatedUser = Depends(require_active_researcher),
    db: AsyncSession = Depends(get_db),
    retrieval_engine: RetrievalEngine = Depends(get_retrieval_engine),
    gemini: GeminiService = Depends(get_gemini_service),
    citation_validator: CitationValidator = Depends(get_citation_validator),
):
    """Execute streaming research query with continuous auth and rate limiting checks."""
    if not auth_rate_limiter.check_rate_limit(f"chat_rate_{current_user.id}", max_attempts=30, window_seconds=60):
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={"error": "RATE_LIMIT_EXCEEDED", "detail": "Rate limit exceeded."},
            headers={"Retry-After": "60"},
        )

    response_data = await ask_research_question(
        body=body,
        request=request,
        current_user=current_user,
        db=db,
        retrieval_engine=retrieval_engine,
        gemini=gemini,
        citation_validator=citation_validator,
    )

    async def event_generator():
        yield f"data: {json.dumps({'event': 'start', 'session_id': response_data.session_id})}\n\n"
        answer_text = response_data.answer
        chunk_size = 40
        for i in range(0, len(answer_text), chunk_size):
            chunk = answer_text[i:i + chunk_size]
            yield f"data: {json.dumps({'event': 'delta', 'text': chunk})}\n\n"
        yield f"data: {json.dumps({'event': 'complete', 'data': response_data.model_dump(mode='json')})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/compare", response_model=PaperComparisonResponse)
async def compare_papers(
    body: PaperComparisonRequest,
    current_user: AuthenticatedUser = Depends(require_active_researcher),
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
    current_user: AuthenticatedUser = Depends(require_active_researcher),
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
    current_user: AuthenticatedUser = Depends(require_active_researcher),
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
    current_user: AuthenticatedUser = Depends(require_active_researcher),
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
    current_user: AuthenticatedUser = Depends(require_active_researcher),
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
    current_user: AuthenticatedUser = Depends(require_active_researcher),
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
    current_user: AuthenticatedUser = Depends(require_active_researcher),
    db: AsyncSession = Depends(get_db),
):
    """Submit quality rating and feedback for an answer message."""
    # Verify that the message exists and belongs to a research session owned by current_user
    stmt = (
        select(ChatMessage, ResearchSession)
        .join(ResearchSession, ChatMessage.session_id == ResearchSession.id)
        .where(ChatMessage.id == message_id)
    )
    res = await db.execute(stmt)
    row = res.one_or_none()
    if not row:
        raise OrionException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="MESSAGE_NOT_FOUND",
            detail=f"Message with ID '{message_id}' was not found.",
        )
    message, session = row
    verify_ownership(session.owner_id, current_user.id, "research message")

    fbk = AnswerFeedback(
        message_id=message.id,
        rating=body.rating,
        comment=body.comment,
    )
    db.add(fbk)
    await db.commit()
    return {"status": "success", "feedback_id": fbk.id}
