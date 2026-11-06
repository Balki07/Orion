"""ORION Public Demo Service.

Provides:
1. Public Q&A grounded exclusively in the 4 curated EPR benchmark papers.
2. Distributed sliding window rate limiting (5 req/min per IP) backed by LLMUsageRecord.
3. Visitor daily query tracking (20 queries/day per session).
4. Atomic global daily Gemini budget reservation (200 provider calls/day).
5. Pre-cached answer matching for instant responses with 0 tokens.
6. Deterministic fallback synthesis when Gemini is unavailable or budget exhausted.
7. Strict tenant isolation: Zero private user data, zero private chunks, zero private documents.
"""

import asyncio
from collections import defaultdict
from datetime import UTC, datetime, timedelta
import hashlib
import json
import math
import re
import time
import uuid

from fastapi import HTTPException
from sqlalchemy import and_, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import logger
from app.models.llm_usage import LLMUsageRecord
from app.schemas.demo import (
    DemoAskRequest,
    DemoAskResponse,
    DemoCitation,
    DemoStatusResponse,
)
from app.services.demo.corpus import (
    CURATED_PAPERS,
    DemoChunk,
    demo_corpus_service,
)
from app.services.demo.examples import (
    CURATED_EXAMPLES,
    find_cached_demo_response,
)
from app.services.generation.llm import get_gemini_service
from app.services.retrieval.query_processor import STOP_WORDS


# In-memory sliding window rate limiter: IP -> list of request timestamps (epoch seconds)
_IP_RATE_LIMIT_STORE: dict[str, list[float]] = defaultdict(list)
_WINDOW_SECONDS = 60.0

# Concurrency lock for serializing reservation near budget threshold
_BUDGET_RESERVATION_LOCK = asyncio.Lock()


def check_and_record_ip_rate_limit(client_ip: str) -> None:
    """Check in-memory sliding window rate limit for visitor IP (first-line filter)."""
    now = time.time()
    cutoff = now - _WINDOW_SECONDS
    timestamps = _IP_RATE_LIMIT_STORE[client_ip]

    # Purge expired timestamps
    _IP_RATE_LIMIT_STORE[client_ip] = [ts for ts in timestamps if ts > cutoff]

    if len(_IP_RATE_LIMIT_STORE[client_ip]) >= settings.DEMO_IP_RATE_LIMIT_PER_MINUTE:
        raise HTTPException(
            status_code=429,
            detail=(
                f"Public demo rate limit exceeded. Maximum {settings.DEMO_IP_RATE_LIMIT_PER_MINUTE} "
                "requests per minute. Please pause for a moment before trying again."
            ),
        )

    _IP_RATE_LIMIT_STORE[client_ip].append(now)


async def check_and_reserve_rate_limit(
    db: AsyncSession,
    client_ip: str,
    visitor_session: str,
    trace_id: str,
) -> LLMUsageRecord:
    """Distributed burst rate limiter coordinating across Uvicorn workers & Render instances.
    
    1. Checks local in-memory sliding window for micro-burst suppression.
    2. Queries shared LLMUsageRecord for requests from this visitor in the last 60 seconds.
    3. Atomically commits an in-flight tracking record to coordinate across parallel workers.
    """
    # 1. First-line local memory check
    check_and_record_ip_rate_limit(client_ip)

    # 2. Distributed shared database check
    cutoff = datetime.now(UTC) - timedelta(seconds=_WINDOW_SECONDS)
    stmt = (
        select(func.count(LLMUsageRecord.id))
        .where(
            LLMUsageRecord.call_type == "public_demo",
            LLMUsageRecord.session_id == visitor_session,
            LLMUsageRecord.created_at >= cutoff,
        )
    )
    res = await db.execute(stmt)
    count = res.scalar() or 0

    if count >= settings.DEMO_IP_RATE_LIMIT_PER_MINUTE:
        raise HTTPException(
            status_code=429,
            detail=(
                f"Public demo rate limit exceeded. Maximum {settings.DEMO_IP_RATE_LIMIT_PER_MINUTE} "
                "requests per minute. Please pause for a moment before trying again."
            ),
        )

    # 3. Create committed tracking record visible to all workers
    rec = LLMUsageRecord(
        trace_id=trace_id,
        session_id=visitor_session,
        user_id=None,
        call_type="public_demo",
        model="orion-demo",
        attempt_number=1,
        max_attempts=1,
        is_provider_call=False,
        status="in_flight",
        http_status_code=200,
        prompt_tokens=0,
        completion_tokens=0,
        total_tokens=0,
        has_usage_metadata=False,
        latency_ms=0.0,
    )
    db.add(rec)
    await db.commit()
    return rec


def get_visitor_session_id(client_ip: str) -> str:
    """Generate a stable, anonymized daily visitor session identifier from IP."""
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    raw = f"{client_ip}_{today}_orion_demo"
    hashed = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"demo_vis_{hashed}"


async def get_daily_demo_provider_call_count(db: AsyncSession) -> int:
    """Return count of Gemini provider calls made by public demo today (UTC), including active reservations."""
    today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    stale_cutoff = datetime.now(UTC) - timedelta(minutes=2)
    stmt = (
        select(func.count(LLMUsageRecord.id))
        .where(
            LLMUsageRecord.call_type == "public_demo",
            or_(
                LLMUsageRecord.is_provider_call.is_(True),
                and_(
                    LLMUsageRecord.status == "reserved",
                    LLMUsageRecord.created_at >= stale_cutoff,
                ),
            ),
            LLMUsageRecord.created_at >= today_start,
        )
    )
    res = await db.execute(stmt)
    return res.scalar() or 0


async def get_visitor_daily_query_count(db: AsyncSession, visitor_session_id: str) -> int:
    """Return count of completed queries made by this visitor session today (UTC)."""
    today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    stmt = (
        select(func.count(LLMUsageRecord.id))
        .where(
            LLMUsageRecord.call_type == "public_demo",
            LLMUsageRecord.session_id == visitor_session_id,
            LLMUsageRecord.status.notin_(["in_flight", "rate_limited", "visitor_quota_exceeded"]),
            LLMUsageRecord.created_at >= today_start,
        )
    )
    res = await db.execute(stmt)
    return res.scalar() or 0


async def try_reserve_gemini_budget(db: AsyncSession, usage_rec: LLMUsageRecord) -> bool:
    """Atomically reserve 1 Gemini provider call slot for today.
    
    Guarantees:
    - Serialization across async tasks (via asyncio.Lock).
    - Serialization across multi-process workers on PostgreSQL (via pg_advisory_xact_lock).
    - Checks both completed provider calls and actively reserved in-flight calls today.
    - Safe fallback: if budget exhausted, returns False without consuming quota.
    """
    async with _BUDGET_RESERVATION_LOCK:
        try:
            if db.bind and db.bind.dialect.name == "postgresql":
                await db.execute(text("SELECT pg_advisory_xact_lock(889901)"))
        except Exception as e:
            logger.debug(f"Advisory lock check skipped/failed: {e}")

        today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        stale_cutoff = datetime.now(UTC) - timedelta(minutes=2)

        # Count completed provider calls today + currently reserved calls (unexpired)
        stmt = (
            select(func.count(LLMUsageRecord.id))
            .where(
                LLMUsageRecord.call_type == "public_demo",
                or_(
                    LLMUsageRecord.is_provider_call.is_(True),
                    and_(
                        LLMUsageRecord.status == "reserved",
                        LLMUsageRecord.created_at >= stale_cutoff,
                        LLMUsageRecord.id != usage_rec.id,
                    ),
                ),
                LLMUsageRecord.created_at >= today_start,
            )
        )
        res = await db.execute(stmt)
        active_count = res.scalar() or 0

        if active_count >= settings.DEMO_DAILY_GEMINI_BUDGET:
            return False

        # Budget is available: atomically reserve slot
        usage_rec.status = "reserved"
        usage_rec.is_provider_call = False  # Not yet completed
        usage_rec.model = settings.GEMINI_MODEL
        await db.commit()
        return True


def tokenize_query(text: str) -> list[str]:
    """Tokenize query removing stop words and punctuation."""
    words = re.findall(r"\b[A-Za-z0-9_-]+\b", text.lower())
    return [w for w in words if len(w) > 2 and w not in STOP_WORDS]


def score_chunk_relevance(query_tokens: list[str], chunk: DemoChunk) -> float:
    """Simple BM25-like lexical scoring for demo chunks."""
    if not query_tokens:
        return 0.0
    content_lower = chunk.content.lower()
    score = 0.0
    for token in query_tokens:
        matches = content_lower.count(token)
        if matches > 0:
            score += 1.0 + math.log(matches)
        # Bonus for section title match
        if token in chunk.section_title.lower():
            score += 1.5
    return score


class DemoService:
    """Service executing evidence-grounded demo queries with rate limiting and budget tracking."""

    async def get_status(self, db: AsyncSession) -> DemoStatusResponse:
        """Return public status and daily usage metrics for demo."""
        used_today = await get_daily_demo_provider_call_count(db)
        total_budget = settings.DEMO_DAILY_GEMINI_BUDGET
        remaining = max(0, total_budget - used_today)

        return DemoStatusResponse(
            enabled=settings.ORION_ENABLE_PUBLIC_DEMO,
            total_papers=len(CURATED_PAPERS),
            daily_budget_total=total_budget,
            daily_budget_remaining=remaining,
            visitor_daily_limit=settings.DEMO_VISITOR_DAILY_QUERY_LIMIT,
            ip_rate_limit_per_minute=settings.DEMO_IP_RATE_LIMIT_PER_MINUTE,
        )

    async def execute_query(
        self,
        request: DemoAskRequest,
        client_ip: str,
        db: AsyncSession,
    ) -> DemoAskResponse:
        """Execute a demo research query over the curated allowlist corpus."""
        start_time = time.perf_counter()
        trace_id = f"demo_{uuid.uuid4().hex[:12]}"
        visitor_session = get_visitor_session_id(client_ip)

        # 1. Distributed rate limiting check and in-flight reservation
        usage_rec = await check_and_reserve_rate_limit(db, client_ip, visitor_session, trace_id)

        # 2. Validate requested document_ids
        resolved_doc_ids: list[str] = []
        if request.document_ids:
            for doc_id in request.document_ids:
                canonical = demo_corpus_service.resolve_paper_id(doc_id)
                if not canonical or canonical not in CURATED_PAPERS:
                    usage_rec.status = "invalid_document_filter"
                    usage_rec.http_status_code = 400
                    await db.commit()
                    raise HTTPException(
                        status_code=400,
                        detail=f"Document '{doc_id}' is not in the curated demo corpus allowlist.",
                    )
                resolved_doc_ids.append(canonical)

        # 3. Check for pre-cached answer first
        cached = find_cached_demo_response(request.question)
        if cached:
            selected_docs = cached["selected_papers"]
            if resolved_doc_ids:
                # If visitor filtered to specific docs, verify at least one matches
                if not any(d in resolved_doc_ids for d in selected_docs):
                    cached = None  # Force search within requested filter

        if cached:
            latency_ms = (time.perf_counter() - start_time) * 1000.0
            usage_rec.model = "orion-demo-cache"
            usage_rec.status = "cached"
            usage_rec.http_status_code = 200
            usage_rec.prompt_tokens = 0
            usage_rec.completion_tokens = 0
            usage_rec.total_tokens = 0
            usage_rec.has_usage_metadata = False
            usage_rec.latency_ms = latency_ms
            await db.commit()

            return DemoAskResponse(
                answer=cached["answer"],
                citations=cached["citations"],
                grounding_score=1.0,
                is_cached=True,
                insufficient_evidence=False,
                trace_id=trace_id,
                latency_ms=round(latency_ms, 2),
                selected_papers=cached["selected_papers"],
            )

        # 4. Enforce visitor daily limit
        visitor_count = await get_visitor_daily_query_count(db, visitor_session)
        if visitor_count >= settings.DEMO_VISITOR_DAILY_QUERY_LIMIT:
            usage_rec.status = "visitor_quota_exceeded"
            usage_rec.http_status_code = 429
            await db.commit()
            raise HTTPException(
                status_code=429,
                detail=(
                    f"Daily query limit reached for your session ({settings.DEMO_VISITOR_DAILY_QUERY_LIMIT} queries/day). "
                    "Thank you for exploring ORION Demo! Please register for a researcher account to continue extensive research."
                ),
            )

        # 5. Hybrid retrieval over curated demo chunks
        all_chunks = demo_corpus_service.get_all_chunks(resolved_doc_ids if resolved_doc_ids else None)
        tokens = tokenize_query(request.question)

        scored_chunks: list[tuple[DemoChunk, float]] = []
        for ch in all_chunks:
            s = score_chunk_relevance(tokens, ch)
            if s > 0.0:
                scored_chunks.append((ch, s))

        scored_chunks.sort(key=lambda x: x[1], reverse=True)
        top_chunks = scored_chunks[:4]

        # Check for insufficient evidence
        if not top_chunks or top_chunks[0][1] < 1.0:
            latency_ms = (time.perf_counter() - start_time) * 1000.0
            usage_rec.model = "orion-demo-abstain"
            usage_rec.status = "abstained_no_context"
            usage_rec.http_status_code = 200
            usage_rec.prompt_tokens = 0
            usage_rec.completion_tokens = 0
            usage_rec.total_tokens = 0
            usage_rec.has_usage_metadata = False
            usage_rec.latency_ms = latency_ms
            await db.commit()

            return DemoAskResponse(
                answer=(
                    "I could not find sufficient evidence in the 4 curated Extended Producer Responsibility (EPR) "
                    "demo papers to address this question. Please ask a question related to EPR policy instruments, "
                    "community waste banks (Sulami et al.), digital EPR platforms (Somantri et al.), or European packaging directives."
                ),
                citations=[],
                grounding_score=0.0,
                is_cached=False,
                insufficient_evidence=True,
                trace_id=trace_id,
                latency_ms=round(latency_ms, 2),
                selected_papers=[],
            )

        # Construct citations from top chunks
        citations: list[DemoCitation] = []
        selected_paper_ids: set[str] = set()

        for chunk, score in top_chunks:
            paper_meta = CURATED_PAPERS[chunk.document_id]
            selected_paper_ids.add(chunk.document_id)
            snippet = chunk.content[:350].strip()
            citations.append(
                DemoCitation(
                    document_id=chunk.document_id,
                    filename=paper_meta.filename,
                    paper_title=paper_meta.title,
                    page_number=chunk.page_number,
                    exact_passage=snippet,
                    relevance_score=min(1.0, round(score / 5.0, 2)),
                )
            )

        # 6. Concurrency-safe atomic Gemini daily budget reservation
        gemini_service = get_gemini_service()
        gemini_ready = bool(gemini_service and getattr(gemini_service, "_client", None) and settings.GEMINI_API_KEY)
        
        reservation_acquired = False
        if gemini_ready:
            reservation_acquired = await try_reserve_gemini_budget(db, usage_rec)

        answer_text: str = ""

        if reservation_acquired:
            # Prepare concise grounded prompt
            context_blocks = []
            for idx, (ch, _) in enumerate(top_chunks, 1):
                p_meta = CURATED_PAPERS[ch.document_id]
                context_blocks.append(
                    f"[{idx}] Source: {p_meta.title} (Page {ch.page_number})\n{ch.content}"
                )
            context_str = "\n\n".join(context_blocks)

            system_instruction = (
                "You are ORION, an academic research assistant demonstrating Extended Producer Responsibility (EPR) literature. "
                "Answer the user question concisely (max 3 paragraphs) strictly using the provided academic excerpts. "
                "Cite sources using [1], [2] format corresponding to the excerpts. "
                "Do not extrapolate or speculate beyond the provided text."
            )

            user_prompt = f"Context:\n{context_str}\n\nQuestion: {request.question}"

            try:
                from google.genai import types

                timeout_ms = int(settings.DEMO_QUERY_TIMEOUT_SECONDS * 1000)
                gen_config = types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=0.1,
                    max_output_tokens=600,
                    http_options=types.HttpOptions(timeout=timeout_ms),
                )
                response = gemini_service._client.models.generate_content(
                    model=settings.GEMINI_MODEL,
                    contents=user_prompt,
                    config=gen_config,
                )
                answer_text = response.text.strip() if response.text else ""

                p_tok = None
                c_tok = None
                if hasattr(response, "usage_metadata") and response.usage_metadata:
                    p_tok = getattr(response.usage_metadata, "prompt_token_count", None)
                    c_tok = getattr(response.usage_metadata, "candidates_token_count", None)

                latency_ms = (time.perf_counter() - start_time) * 1000.0

                usage_rec.model = settings.GEMINI_MODEL
                usage_rec.is_provider_call = True
                usage_rec.status = "success"
                usage_rec.http_status_code = 200
                usage_rec.prompt_tokens = p_tok
                usage_rec.completion_tokens = c_tok
                usage_rec.total_tokens = (p_tok or 0) + (c_tok or 0) if (p_tok or c_tok) else None
                usage_rec.has_usage_metadata = p_tok is not None
                usage_rec.latency_ms = latency_ms
                await db.commit()

            except Exception as e:
                logger.warning(f"Public demo Gemini call failed, safely releasing budget reservation: {e}")
                # Release reservation so budget is not consumed on failure
                usage_rec.is_provider_call = False
                usage_rec.status = "failed"
                usage_rec.error_detail = str(e)[:500]
                usage_rec.latency_ms = (time.perf_counter() - start_time) * 1000.0
                await db.commit()
                answer_text = ""

        # Deterministic synthesis fallback if Gemini was not called, budget exhausted, or Gemini failed
        if not answer_text:
            synthesis_parts = []
            for idx, (ch, _) in enumerate(top_chunks[:2], 1):
                p_meta = CURATED_PAPERS[ch.document_id]
                first_para = ch.content.split("\n\n")[0].strip()
                synthesis_parts.append(
                    f"According to {p_meta.authors} ({p_meta.year}) in *{p_meta.title}* [Page {ch.page_number}]:\n\n\"{first_para}\""
                )
            if not reservation_acquired:
                synthesis_parts.append(
                    "\n\n*(Note: ORION Public Demo daily AI generation budget is reached; answer synthesized directly from verified benchmark literature).* "
                )
            answer_text = "\n\n".join(synthesis_parts)

            latency_ms = (time.perf_counter() - start_time) * 1000.0
            if usage_rec.status != "failed":
                usage_rec.model = "orion-demo-fallback"
                usage_rec.status = "fallback" if reservation_acquired else "budget_exhausted_fallback"
            usage_rec.is_provider_call = False
            usage_rec.latency_ms = latency_ms
            await db.commit()

        total_latency_ms = (time.perf_counter() - start_time) * 1000.0

        return DemoAskResponse(
            answer=answer_text,
            citations=citations,
            grounding_score=0.95,
            is_cached=False,
            insufficient_evidence=False,
            trace_id=trace_id,
            latency_ms=round(total_latency_ms, 2),
            selected_papers=list(selected_paper_ids),
        )


demo_service = DemoService()
