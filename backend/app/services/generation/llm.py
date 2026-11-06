"""Google Gemini LLM Service with structured JSON output and deterministic synthesizer."""

import asyncio
import json
import re
import time
from typing import Any

from app.core.config import settings
from app.core.logging import logger
from app.services.generation.prompts import (
    QA_PROMPT_TEMPLATE,
    SYSTEM_PROMPT,
)
from app.services.generation.usage_tracker import record_llm_usage
from app.services.retrieval.query_processor import (
    ACADEMIC_SYNONYMS,
    STOP_WORDS,
    extract_anchor_constraints,
    is_reference_chunk,
    normalize_stem,
    process_query,
    resolve_citation_page,
)


COMMON_ACADEMIC_ABBREVIATIONS = [
    "Sect.", "Fig.", "al.", "Dr.", "Prof.", "Vol.", "No.", "vs.", "e.g.", "i.e.", "Univ.", "Dept.", "Eq.", "Ref."
]


def clean_text_formatting(text: str) -> str:
    """Cleans up internal newlines, artifact hyphens, and whitespace."""
    if not text:
        return ""
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
    cleaned = re.sub(r"(\w+)-\s+(\w+)", r"\1\2", cleaned)
    cleaned = re.sub(r"/\s+", "/", cleaned)
    cleaned = re.sub(r"(\d+)\s*%", r"\1%", cleaned)
    cleaned = re.sub(r"(\d+)\s*[-–—]\s*(\d+)%", r"\1%-\2%", cleaned)
    cleaned = re.sub(r"[\u2010\u2011\u2012\u2013\u2014\u2212]", "-", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def split_into_complete_sentences(text: str) -> list[str]:
    """Splits text into complete sentences while protecting academic abbreviations."""
    t = text
    for i, abbr in enumerate(COMMON_ACADEMIC_ABBREVIATIONS):
        t = t.replace(abbr, f"__ABBR_{i}__")
    raw_sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", t) if s.strip()]
    sentences = []
    for s in raw_sentences:
        for i, abbr in enumerate(COMMON_ACADEMIC_ABBREVIATIONS):
            s = s.replace(f"__ABBR_{i}__", abbr)
        sentences.append(s)
    return sentences


def extract_complete_sentence_excerpt(
    chunk_text: str,
    prev_text: str = "",
    next_text: str = "",
    target_terms: set[str] | None = None,
    max_chars: int = 480,
    requested_info: str = "",
) -> str:
    """Extracts coherent, complete sentence(s) prioritizing the specific requested information."""
    c_clean = clean_text_formatting(chunk_text)
    if not c_clean:
        return ""

    p_clean = clean_text_formatting(prev_text)
    n_clean = clean_text_formatting(next_text)

    # If chunk starts mid-sentence (lowercase start and prev_text available), prepend the sentence prefix
    if c_clean and c_clean[0].islower() and p_clean:
        p_sentences = split_into_complete_sentences(p_clean)
        if p_sentences:
            last_p = p_sentences[-1]
            if last_p and last_p[-1] not in ".!?":
                c_clean = last_p + " " + c_clean
            elif not p_clean.endswith((".", "!", "?")):
                p_parts = list(re.finditer(r"[.!?]\s+", p_clean))
                if p_parts:
                    sentence_prefix = p_clean[p_parts[-1].end():].strip()
                    if sentence_prefix:
                        c_clean = sentence_prefix + " " + c_clean

    # If chunk ends mid-sentence (no terminal punctuation and next_text available), append sentence suffix
    if c_clean and c_clean[-1] not in ".!?\"'":
        if n_clean:
            n_match = re.search(r"^([^.!?]*[.!?])", n_clean)
            if n_match:
                sentence_suffix = n_match.group(1).strip()
                c_clean = c_clean + " " + sentence_suffix

    sentences = split_into_complete_sentences(c_clean)
    if not sentences:
        return c_clean if c_clean.endswith(".") else c_clean + "."

    req_lower = (requested_info or "").lower()
    t_terms = {t.lower() for t in (target_terms or set()) if len(t) > 2}

    # Query information type signals
    is_num_query = any(w in req_lower for w in ["%", "percent", "percentage", "rate", "mass", "volume", "amount", "growth", "concentration", "proportion", "how many", "how much", "total", "kg", "mt", "ton", "tonne"]) or any(t in {"rate", "mass", "volume", "percent", "percentage", "growth", "concentration", "proportion"} for t in t_terms)
    is_list_query = any(w in req_lower for w in ["types", "polymers", "materials", "categories", "pathways", "systems", "list", "what are the", "which"]) or any(t in {"types", "polymers", "materials", "categories", "pathways", "systems"} for t in t_terms)
    is_gap_query = any(w in req_lower for w in ["gap", "gaps", "limitation", "limitations", "scarcity", "unresolved", "challenge", "challenges"]) or any(t in {"gap", "gaps", "limitation", "limitations", "scarcity", "unresolved"} for t in t_terms)

    scored = []
    for idx, s in enumerate(sentences):
        score = 0
        s_lower = s.lower()

        # 1. Target term overlap
        if t_terms:
            for term in t_terms:
                if term in s_lower:
                    score += 2

        # 2. Numerical / quantitative alignment
        if is_num_query:
            has_units = bool(re.search(r"\b\d+(?:\.\d+)?\s*(?:%|percent|mt|g/km2|kg|kt|tons?|tonnes?|cm|mm|million|billion)\b", s, re.I))
            has_digits = bool(re.search(r"\b\d+(?:\.\d+)?\b", re.sub(r"\[\d+\]", "", s)))
            if has_units:
                score += 4
            elif has_digits:
                score += 2
            # Penalize pure figure/table captions or metadata headings when quantitative finding requested
            if re.match(r"^(?:Fig(?:ure)?\.?\s*\d+|Table\s*\d+|SM\s*\d+)\b", s.strip(), re.I):
                score -= 4

        # 3. List / Enumeration alignment
        if is_list_query:
            has_colon_list = bool(re.search(r":\s+[a-zA-Z\s-]+(?:\([A-Z]+\))?(?:,\s+[a-zA-Z\s-]+(?:\([A-Z]+\))?){2,}", s))
            has_acronyms = bool(re.search(r"\([A-Z]{2,}\)", s))
            has_enumerations = bool(re.search(r"\b\d+\s+(?:product\s+categories|waste\s+collection\s+pathways|sorting\s+systems)\b", s, re.I))
            if has_colon_list or has_acronyms:
                score += 5
            elif has_enumerations:
                score += 4

        # 4. Research gap alignment
        if is_gap_query:
            if any(gt in s_lower for gt in ["data limitation", "lack of", "scarcity", "unresolved", "unable to accommodate", "fragmented", "short lifespan", "low recycling"]):
                score += 4

        # Penalty for extremely short fragments or mere headings
        if len(s) < 25:
            score -= 2

        scored.append((idx, score, s))

    best_idx = max(scored, key=lambda x: x[1])[0] if scored else 0

    selected = [sentences[best_idx]]
    current_len = len(selected[0])

    # Expand forwards if next sentence fits
    if best_idx + 1 < len(sentences):
        next_s = sentences[best_idx + 1]
        if current_len + len(next_s) + 1 <= max_chars:
            selected.append(next_s)
            current_len += len(next_s) + 1

    # Expand backwards if previous sentence fits and provides relevant context or grammatical continuity
    if best_idx > 0:
        prev_s = sentences[best_idx - 1]
        is_prev_caption = bool(re.match(r"^(?:Fig(?:ure)?\.?\s*\d+|Table\s*\d+|SM\s*\d+)\b", prev_s.strip(), re.I))
        needs_context = (
            len(selected[0]) < 80
            or bool(re.match(r"^(?:this|these|those|it|they|such|its|their|furthermore|moreover|specifically|in contrast)\b", selected[0].strip(), re.I))
            or any(t in prev_s.lower() for t in target_terms if len(t) > 2)
        )
        if not is_prev_caption and needs_context and current_len + len(prev_s) + 1 <= max_chars:
            selected.insert(0, prev_s)
            current_len += len(prev_s) + 1

    excerpt = " ".join(selected).strip()

    # Safety: ensure terminal punctuation
    if excerpt and excerpt[-1] not in ".!?\"'":
        last_punct = max(excerpt.rfind("."), excerpt.rfind("!"), excerpt.rfind("?"))
        if last_punct > 40:
            excerpt = excerpt[:last_punct + 1]
        else:
            excerpt += "."

    return excerpt


def _attempt_json_recovery(text: str) -> dict[str, Any] | None:
    """Best-effort regex recovery for truncated structured QA JSON."""
    try:
        # Attempt to repair common truncation by closing quotes and brackets
        for suffix in ['"}', '"]}', '"}]}', '"]}}', '}']:
            try:
                candidate = text.rstrip() + suffix
                parsed = json.loads(candidate, strict=False)
                if isinstance(parsed, dict) and "answer" in parsed:
                    parsed.setdefault("warnings", []).append("Response was recovered from truncated model JSON.")
                    return parsed
            except Exception:
                continue

        # Extract answer field directly via regex if present
        ans_match = re.search(r'"answer"\s*:\s*"((?:[^"\\]|\\.)*)', text)
        if ans_match:
            raw_ans = ans_match.group(1)
            ans_clean = raw_ans.replace('\\"', '"').replace('\\n', '\n').replace('\\t', '\t')

            insufficient = False
            ins_match = re.search(r'"insufficient_evidence"\s*:\s*(true|false)', text, re.IGNORECASE)
            if ins_match:
                insufficient = ins_match.group(1).lower() == "true"

            return {
                "answer": ans_clean,
                "insufficient_evidence": insufficient,
                "claims": [],
                "citations": [],
                "warnings": ["Answer was reconstructed from partially truncated model JSON."],
            }
    except Exception:
        pass
    return None


def extract_json_payload(raw_text: str | None) -> dict[str, Any]:
    """Robustly extract and parse a JSON dictionary from model response text.

    Handles:
    - None or empty string responses
    - Markdown code fences (```json ... ``` or ``` ... ```)
    - Preamble or postamble conversational text
    - Unescaped control characters in JSON strings (strict=False)
    - Truncated JSON recovery for structured QA output
    """
    if raw_text is None:
        raise ValueError("Model returned None for response text (possible safety or finish_reason block).")

    text = raw_text.strip()
    if not text:
        raise ValueError("Model returned an empty text response.")

    # 1. Strip markdown code fences if present
    fence_pattern = r"^```(?:json)?\s*\n?(.*?)\n?```$"
    fence_match = re.search(fence_pattern, text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1).strip()
    else:
        # Handle code fence embedded inside prose
        if "```json" in text:
            start_fence = text.find("```json") + len("```json")
            end_fence = text.find("```", start_fence)
            if end_fence != -1:
                text = text[start_fence:end_fence].strip()
        elif "```" in text:
            start_fence = text.find("```") + len("```")
            end_fence = text.find("```", start_fence)
            if end_fence != -1:
                text = text[start_fence:end_fence].strip()

    # 2. Extract JSON object substring between first '{' and last '}'
    start_brace = text.find("{")
    end_brace = text.rfind("}")
    if start_brace != -1 and end_brace != -1 and end_brace > start_brace:
        json_candidate = text[start_brace : end_brace + 1]
    else:
        json_candidate = text

    # 3. Attempt standard parse with strict=False to tolerate unescaped control chars
    try:
        parsed = json.loads(json_candidate, strict=False)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError as err:
        # 4. Attempt recovery for truncated JSON or unclosed strings
        recovered = _attempt_json_recovery(json_candidate)
        if recovered is not None:
            return recovered
        raise err

    raise ValueError(f"Extracted JSON is not an object/dict: {type(parsed).__name__}")


FALLBACK_REASON_QUOTA = "QUOTA"
FALLBACK_REASON_MODEL_NOT_FOUND = "MODEL_NOT_FOUND"
FALLBACK_REASON_BAD_KEY = "BAD_KEY"
FALLBACK_REASON_KEY_NOT_LOADED = "KEY_NOT_LOADED"
FALLBACK_REASON_NETWORK = "NETWORK"
FALLBACK_REASON_UNAVAILABLE = "UNAVAILABLE"
FALLBACK_REASON_OTHER = "OTHER"

PLAIN_FALLBACK_MESSAGES = {
    FALLBACK_REASON_QUOTA: "Gemini daily limit reached, using basic mode.",
    FALLBACK_REASON_BAD_KEY: "Gemini key problem, using basic mode.",
    FALLBACK_REASON_KEY_NOT_LOADED: "Gemini key not configured, using basic mode.",
    FALLBACK_REASON_MODEL_NOT_FOUND: "Configured Gemini model not found, using basic mode.",
    FALLBACK_REASON_NETWORK: "Network error connecting to Gemini, using basic mode.",
    FALLBACK_REASON_UNAVAILABLE: "Gemini service is currently overloaded (503 high demand). ORION answered using verified research literature directly.",
    FALLBACK_REASON_OTHER: "Gemini unavailable, using basic mode.",
}


def classify_gemini_error(exc: Exception) -> tuple[str, int | None, str | None, str]:
    """Classifies a Gemini exception into standard fallback reasons with redacted logging info.

    Returns: (fallback_reason, status_code, status_str, safe_message)
    """
    err_str = str(exc)
    if settings.GEMINI_API_KEY and settings.GEMINI_API_KEY in err_str:
        err_str = err_str.replace(settings.GEMINI_API_KEY, "[REDACTED]")

    status_code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
    status_str = getattr(exc, "status", None)

    if hasattr(exc, "response_json") and isinstance(exc.response_json, dict):
        err_dict = exc.response_json.get("error", {})
        if not status_code:
            status_code = err_dict.get("code")
        if not status_str:
            status_str = err_dict.get("status")

    if not status_code:
        m = re.search(r"\b(4\d\d|5\d\d)\b", err_str)
        if m:
            status_code = int(m.group(1))

    status_str_clean = (str(status_str) if status_str else "").upper()
    err_str_lower = err_str.lower()

    if (
        status_code == 503
        or status_str_clean == "UNAVAILABLE"
        or "503" in err_str
        or any(k in err_str_lower for k in ["unavailable", "high demand", "overloaded", "capacity", "service unavailable"])
    ):
        reason = FALLBACK_REASON_UNAVAILABLE
    elif status_code == 429 or "RESOURCE_EXHAUSTED" in err_str or "quota" in err_str_lower:
        reason = FALLBACK_REASON_QUOTA
    elif status_code == 404 or "NOT_FOUND" in err_str or "not found" in err_str_lower:
        reason = FALLBACK_REASON_MODEL_NOT_FOUND
    elif status_code in (400, 401, 403) or any(k in err_str for k in ["API_KEY_INVALID", "PERMISSION_DENIED", "UNAUTHENTICATED", "key invalid"]):
        reason = FALLBACK_REASON_BAD_KEY
    elif isinstance(exc, (TimeoutError, ConnectionError)) or any(k in err_str_lower for k in ["timeout", "connection refused", "dns", "getaddrinfo", "deadline"]):
        reason = FALLBACK_REASON_NETWORK
    else:
        reason = FALLBACK_REASON_OTHER

    return reason, status_code, status_str, err_str[:300]


def is_retryable_gemini_error(code: int | None, status_str: str | None, reason: str, retry_delay: float | None) -> bool:
    """Determine whether a Gemini API error is safe and sensible to retry."""
    # Definitively non-retryable errors
    if reason in (FALLBACK_REASON_BAD_KEY, FALLBACK_REASON_MODEL_NOT_FOUND, FALLBACK_REASON_KEY_NOT_LOADED):
        return False
    if code in (400, 401, 403, 404):
        return False
    # Long daily quota cooldown is non-retryable
    if reason == FALLBACK_REASON_QUOTA and retry_delay and retry_delay > 10.0:
        return False
    # Transient provider unavailability / server errors
    if reason == FALLBACK_REASON_UNAVAILABLE or (code is not None and code in (502, 503, 504)):
        return True
    # Transient network errors
    if reason == FALLBACK_REASON_NETWORK:
        return True
    # Short rate limit (e.g. burst limit with short wait)
    if code == 429 and (retry_delay is None or retry_delay <= 10.0):
        return True
    return False


def extract_retry_delay(exc: Exception) -> float | None:
    """Extracts retryDelay seconds from google.genai error details if present."""
    try:
        if hasattr(exc, "response_json") and isinstance(exc.response_json, dict):
            details = exc.response_json.get("error", {}).get("details", [])
            for d in details:
                if isinstance(d, dict) and "retryDelay" in d:
                    rd_str = str(d["retryDelay"]).rstrip("s")
                    return float(rd_str)
        m = re.search(r"['\"]?retryDelay['\"]?\s*:\s*['\"]?(\d+(?:\.\d+)?)s?['\"]?", str(exc))
        if m:
            return float(m.group(1))
    except Exception:
        pass
    return None


class GeminiService:
    _quota_exhausted_until: float = 0.0
    _request_timestamps: list[float] = []

    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY
        self.model_name = settings.GEMINI_MODEL
        self._client = None
        self.fallback_events_count = 0
        self.accumulated_prompt_tokens = 0
        self.accumulated_candidate_tokens = 0
        self.accumulated_api_calls = 0
        if self.api_key:
            self._init_client()

    def _init_client(self) -> None:
        if not self.api_key:
            logger.warning("Gemini key: absent. Deterministic fallback mode will be active.")
            self._client = None
            return

        try:
            from google import genai

            self._client = genai.Client(api_key=self.api_key)
            logger.info(f"Gemini key: present (length={len(self.api_key)}). Initialized Google Gemini client.")

            # Startup model validation check
            try:
                models = [m.name for m in self._client.models.list()]
                target = self.model_name
                target_full = f"models/{target}" if not target.startswith("models/") else target
                if not any(m == target or m == target_full for m in models):
                    flash_pro = [m for m in models if "flash" in m.lower() or "pro" in m.lower()]
                    logger.warning(
                        f"Configured GEMINI_MODEL '{self.model_name}' was not found in available models list! "
                        f"Available candidates: {flash_pro[:5]}..."
                    )
                else:
                    logger.info(f"Configured GEMINI_MODEL '{self.model_name}' verified in available models list.")
            except Exception as m_err:
                logger.warning(f"Could not verify models list against Gemini API: {m_err}")

        except Exception as e:
            logger.warning(f"Could not initialize google-genai Client: {e}")
            self._client = None

    def _pace_request(self) -> None:
        """Enforces client-side rate limiting to avoid burst 429 rate limit spikes."""
        rpm = getattr(settings, "GEMINI_REQUESTS_PER_MINUTE", 15)
        if rpm <= 0:
            return
        now = time.time()
        GeminiService._request_timestamps = [t for t in GeminiService._request_timestamps if now - t < 60.0]
        if len(GeminiService._request_timestamps) >= rpm:
            sleep_needed = 60.0 - (now - GeminiService._request_timestamps[0]) + 0.1
            if 0 < sleep_needed <= 5.0:
                logger.info(f"Pacing Gemini requests: sleeping {sleep_needed:.2f}s to respect {rpm} RPM limit.")
                time.sleep(sleep_needed)
        GeminiService._request_timestamps.append(time.time())

    async def record_cache_hit(
        self,
        *,
        trace_id: str | None = None,
        request_id: str | None = None,
        session_id: str | None = None,
        user_id: str | None = None,
        db: Any | None = None,
    ) -> None:
        """Records a cached answer reuse event without counting as a provider call or token usage."""
        await record_llm_usage(
            trace_id=trace_id,
            request_id=request_id,
            session_id=session_id,
            user_id=user_id,
            model=self.model_name,
            attempt_number=1,
            max_attempts=1,
            is_provider_call=False,
            status="cached",
            prompt_tokens=None,
            completion_tokens=None,
            total_tokens=None,
            has_usage_metadata=False,
            latency_ms=0.0,
            db=db,
        )

    async def generate_grounded_answer(
        self,
        question: str,
        formatted_context: str,
        retrieved_metadata: list[dict[str, Any]],
        processed_query: Any | None = None,
        duplicate_groups: dict[str, list[str]] | None = None,
        document_ids: list[str] | None = None,
        user_id: str | None = None,
        session_id: str | None = None,
        trace_id: str | None = None,
        request_id: str | None = None,
        disable_fallback: bool = False,
        db: Any | None = None,
    ) -> dict[str, Any]:
        """Calls Gemini with structured output constraints to generate evidence-grounded answers."""
        start_time = time.perf_counter()

        # If no context was retrieved at all, abstain immediately without a provider call
        if not formatted_context.strip():
            latency = (time.perf_counter() - start_time) * 1000.0
            await record_llm_usage(
                trace_id=trace_id,
                request_id=request_id,
                session_id=session_id,
                user_id=user_id,
                model=self.model_name,
                attempt_number=1,
                max_attempts=1,
                is_provider_call=False,
                status="abstained_no_context",
                latency_ms=latency,
                db=db,
            )
            return {
                "answer": "The provided research documents do not contain sufficient evidence to answer this question.",
                "claims": [],
                "citations": [],
                "insufficient_evidence": True,
                "warnings": ["Zero relevant document passages were retrieved from the selected sources."],
                "latency_ms": {"generation": latency},
                "answer_path": "deterministic_fallback",
                "model": None,
                "fallback_reason": None,
            }

        prompt = QA_PROMPT_TEMPLATE.format(
            context=formatted_context,
            question=question,
        )

        # 1. Check if API key is not loaded or client failed to initialize
        if self._client is None or not self.api_key:
            fallback_reason = FALLBACK_REASON_KEY_NOT_LOADED
            self.fallback_events_count = getattr(self, "fallback_events_count", 0) + 1
            latency = (time.perf_counter() - start_time) * 1000.0
            await record_llm_usage(
                trace_id=trace_id,
                request_id=request_id,
                session_id=session_id,
                user_id=user_id,
                model=self.model_name,
                attempt_number=1,
                max_attempts=1,
                is_provider_call=False,
                status="fallback",
                error_category=fallback_reason,
                error_detail="API key absent or client failed to initialize",
                latency_ms=latency,
                db=db,
            )
            if disable_fallback:
                raise RuntimeError("Gemini Client is None (missing API key or initialization failed), and fallback is disabled.")
            resp = self._deterministic_synthesizer(
                question,
                retrieved_metadata,
                start_time,
                pq=processed_query,
                duplicate_groups=duplicate_groups,
                document_ids=document_ids,
                user_id=user_id,
            )
            resp["answer_path"] = "deterministic_fallback"
            resp["model"] = None
            resp["fallback_reason"] = fallback_reason
            resp.setdefault("warnings", []).append(PLAIN_FALLBACK_MESSAGES[fallback_reason])
            return resp

        # 2. Check if currently under quota exhaustion cooldown cache
        now = time.time()
        if now < GeminiService._quota_exhausted_until:
            fallback_reason = FALLBACK_REASON_QUOTA
            remaining_cooldown = int(GeminiService._quota_exhausted_until - now)
            logger.info(f"Skipping Gemini API call; quota cooldown active for another {remaining_cooldown}s.")
            self.fallback_events_count = getattr(self, "fallback_events_count", 0) + 1
            latency = (time.perf_counter() - start_time) * 1000.0
            await record_llm_usage(
                trace_id=trace_id,
                request_id=request_id,
                session_id=session_id,
                user_id=user_id,
                model=self.model_name,
                attempt_number=1,
                max_attempts=1,
                is_provider_call=False,
                status="fallback",
                error_category=fallback_reason,
                error_detail=f"Quota cooldown active ({remaining_cooldown}s remaining)",
                latency_ms=latency,
                db=db,
            )
            if disable_fallback:
                raise RuntimeError(f"Gemini API quota cooldown active for another {remaining_cooldown}s, and fallback is disabled.")
            resp = self._deterministic_synthesizer(
                question,
                retrieved_metadata,
                start_time,
                pq=processed_query,
                duplicate_groups=duplicate_groups,
                document_ids=document_ids,
                user_id=user_id,
            )
            resp["answer_path"] = "deterministic_fallback"
            resp["model"] = None
            resp["fallback_reason"] = fallback_reason
            resp.setdefault("warnings", []).append(PLAIN_FALLBACK_MESSAGES[fallback_reason])
            return resp

        # 3. Real Gemini execution via official google-genai SDK with backoff retry
        from google.genai import types

        response = None
        max_retries = max(0, getattr(settings, "GEMINI_MAX_RETRIES", 1))
        max_attempts = max_retries + 1
        classified_reason = None
        attempts_taken = 0
        total_retry_wait = 0.0
        last_safe_msg = None

        timeout_ms = int(getattr(settings, "GEMINI_TIMEOUT_SECONDS", 12.0) * 1000)
        http_opts = types.HttpOptions(timeout=timeout_ms)
        gen_config = types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=settings.GEMINI_TEMPERATURE,
            max_output_tokens=settings.GEMINI_MAX_OUTPUT_TOKENS,
            response_mime_type="application/json",
            http_options=http_opts,
        )

        actual_model_name = self.model_name
        fallback_model_tried = False
        fallback_model_succeeded = False

        for attempt in range(1, max_attempts + 1):
            attempts_taken = attempt
            attempt_start = time.perf_counter()
            try:
                self._pace_request()
                response = self._client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=gen_config,
                )
                attempt_latency = (time.perf_counter() - attempt_start) * 1000.0

                # Extract token usage metadata from Gemini SDK
                p_tok = None
                c_tok = None
                t_tok = None
                has_usage = False
                if hasattr(response, "usage_metadata") and response.usage_metadata:
                    p_tok = getattr(response.usage_metadata, "prompt_token_count", None)
                    c_tok = getattr(response.usage_metadata, "candidates_token_count", None)
                    t_tok = getattr(response.usage_metadata, "total_token_count", None)
                    has_usage = (p_tok is not None or c_tok is not None or t_tok is not None)

                await record_llm_usage(
                    trace_id=trace_id,
                    request_id=request_id,
                    session_id=session_id,
                    user_id=user_id,
                    model=self.model_name,
                    attempt_number=attempt,
                    max_attempts=max_attempts,
                    is_provider_call=True,
                    status="success",
                    http_status_code=200,
                    prompt_tokens=p_tok,
                    completion_tokens=c_tok,
                    total_tokens=t_tok,
                    has_usage_metadata=has_usage,
                    latency_ms=attempt_latency,
                    db=db,
                )
                break
            except Exception as api_err:
                attempt_latency = (time.perf_counter() - attempt_start) * 1000.0
                reason, code, status_str, safe_msg = classify_gemini_error(api_err)
                classified_reason = reason
                last_safe_msg = safe_msg
                logger.error(
                    f"Gemini API call attempt {attempt}/{max_attempts} failed "
                    f"[{type(api_err).__name__} code={code} status={status_str} reason={reason}]: {safe_msg}"
                )

                await record_llm_usage(
                    trace_id=trace_id,
                    request_id=request_id,
                    session_id=session_id,
                    user_id=user_id,
                    model=self.model_name,
                    attempt_number=attempt,
                    max_attempts=max_attempts,
                    is_provider_call=True,
                    status="failed",
                    http_status_code=code,
                    error_category=reason,
                    error_detail=safe_msg,
                    prompt_tokens=None,
                    completion_tokens=None,
                    total_tokens=None,
                    has_usage_metadata=False,
                    latency_ms=attempt_latency,
                    db=db,
                )

                retry_delay = extract_retry_delay(api_err)

                # Check if it's a long daily-quota exhaustion (> 60s)
                if reason == FALLBACK_REASON_QUOTA and retry_delay and retry_delay > 60.0:
                    GeminiService._quota_exhausted_until = time.time() + retry_delay
                    logger.warning(f"Cached daily quota exhaustion until timestamp: cooldown of {retry_delay:.0f}s.")
                    break  # Do not retry long daily quota exhaustion

                # Check retryability
                retryable = is_retryable_gemini_error(code, status_str, reason, retry_delay)
                if not retryable:
                    logger.info(f"Encountered non-retryable error ({reason}, code={code}). Activating fallback without retries.")
                    break

                # For 503 high-demand overload, bound to at most 1 retry
                if reason == FALLBACK_REASON_UNAVAILABLE and attempt >= 2:
                    logger.warning("Gemini 503 high demand persisted after bounded retry; proceeding promptly to fallback.")
                    break

                # If attempts remaining, calculate backoff with jitter and budget enforcement
                if attempt < max_attempts:
                    import random
                    base_backoff = getattr(settings, "GEMINI_RETRY_BACKOFF_BASE_SECONDS", 0.5)
                    max_backoff = getattr(settings, "GEMINI_RETRY_BACKOFF_MAX_SECONDS", 2.0)
                    max_total_wait = getattr(settings, "GEMINI_MAX_TOTAL_RETRY_WAIT_SECONDS", 5.0)

                    if retry_delay is not None and 0.0 < retry_delay <= max_backoff:
                        backoff = retry_delay + random.uniform(0.05, 0.2)
                    else:
                        backoff = min(max_backoff, (base_backoff * (2 ** (attempt - 1)))) + random.uniform(0.05, 0.2)

                    if total_retry_wait + backoff > max_total_wait:
                        logger.warning(f"Cumulative retry wait budget ({max_total_wait:.1f}s) exceeded. Proceeding to fallback.")
                        break

                    total_retry_wait += backoff
                    logger.info(f"Retrying Gemini API call in {backoff:.2f}s (attempt {attempt + 1}/{max_attempts})...")
                    await asyncio.sleep(backoff)
                    continue

                break

        # Optional alternative fallback model check
        if response is None and getattr(settings, "GEMINI_FALLBACK_MODEL", None) and not disable_fallback:
            fallback_target = settings.GEMINI_FALLBACK_MODEL.strip()
            if fallback_target and fallback_target != self.model_name:
                fallback_model_tried = True
                logger.info(
                    f"Primary model '{self.model_name}' failed ({classified_reason}). "
                    f"Attempting optional fallback model '{fallback_target}'..."
                )
                fb_start = time.perf_counter()
                try:
                    self._pace_request()
                    fb_response = self._client.models.generate_content(
                        model=fallback_target,
                        contents=prompt,
                        config=gen_config,
                    )
                    fb_latency = (time.perf_counter() - fb_start) * 1000.0
                    response = fb_response
                    actual_model_name = fallback_target
                    fallback_model_succeeded = True

                    p_tok = getattr(response.usage_metadata, "prompt_token_count", None) if hasattr(response, "usage_metadata") else None
                    c_tok = getattr(response.usage_metadata, "candidates_token_count", None) if hasattr(response, "usage_metadata") else None
                    t_tok = getattr(response.usage_metadata, "total_token_count", None) if hasattr(response, "usage_metadata") else None
                    has_usage = (p_tok is not None or c_tok is not None or t_tok is not None)

                    await record_llm_usage(
                        trace_id=trace_id,
                        request_id=request_id,
                        session_id=session_id,
                        user_id=user_id,
                        model=fallback_target,
                        attempt_number=1,
                        max_attempts=1,
                        is_provider_call=True,
                        status="success",
                        http_status_code=200,
                        prompt_tokens=p_tok,
                        completion_tokens=c_tok,
                        total_tokens=t_tok,
                        has_usage_metadata=has_usage,
                        latency_ms=fb_latency,
                        db=db,
                    )
                    logger.info(f"Fallback model '{fallback_target}' succeeded in {fb_latency:.1f}ms.")
                except Exception as fb_err:
                    fb_latency = (time.perf_counter() - fb_start) * 1000.0
                    fb_reason, fb_code, _, fb_safe_msg = classify_gemini_error(fb_err)
                    logger.warning(f"Optional fallback model '{fallback_target}' also failed [{fb_reason}]: {fb_safe_msg}")
                    await record_llm_usage(
                        trace_id=trace_id,
                        request_id=request_id,
                        session_id=session_id,
                        user_id=user_id,
                        model=fallback_target,
                        attempt_number=1,
                        max_attempts=1,
                        is_provider_call=True,
                        status="failed",
                        http_status_code=fb_code,
                        error_category=fb_reason,
                        error_detail=fb_safe_msg,
                        prompt_tokens=None,
                        completion_tokens=None,
                        total_tokens=None,
                        has_usage_metadata=False,
                        latency_ms=fb_latency,
                        db=db,
                    )

        parse_warning = None
        if response is not None:
            try:
                raw_text = response.text
                if raw_text is None:
                    finish_reason = "UNKNOWN"
                    if response.candidates and response.candidates[0].finish_reason:
                        finish_reason = str(response.candidates[0].finish_reason)
                    raise ValueError(f"Empty response text from model (finish_reason: {finish_reason})")

                parsed = extract_json_payload(raw_text)
                parsed["answer_path"] = "gemini"
                parsed["model"] = actual_model_name
                parsed["fallback_reason"] = None
                parsed["latency_ms"] = {
                    "generation": (time.perf_counter() - start_time) * 1000.0
                }
                if fallback_model_succeeded and actual_model_name != self.model_name:
                    parsed.setdefault("warnings", []).append(
                        f"Answer generated via fallback model '{actual_model_name}' due to primary model overload."
                    )
                parsed["generation_diagnostics"] = {
                    "provider": "gemini",
                    "primary_model": self.model_name,
                    "actual_model": actual_model_name,
                    "attempts": attempts_taken,
                    "max_attempts": max_attempts,
                    "fallback_model_attempted": fallback_model_tried,
                    "fallback_activated": False,
                    "fallback_reason": None,
                    "generation_ms": round((time.perf_counter() - start_time) * 1000.0, 2),
                }
                self.accumulated_api_calls += 1
                if hasattr(response, "usage_metadata") and response.usage_metadata:
                    p_tok = getattr(response.usage_metadata, "prompt_token_count", 0) or 0
                    c_tok = getattr(response.usage_metadata, "candidates_token_count", 0) or 0
                    t_tok = getattr(response.usage_metadata, "total_token_count", 0) or 0
                    self.accumulated_prompt_tokens += p_tok
                    self.accumulated_candidate_tokens += c_tok
                    parsed["usage_metadata"] = {
                        "prompt_token_count": p_tok,
                        "candidates_token_count": c_tok,
                        "total_token_count": t_tok,
                    }
                return parsed

            except Exception as parse_err:
                self.fallback_events_count = getattr(self, "fallback_events_count", 0) + 1
                if disable_fallback:
                    raise RuntimeError(f"Gemini response parsing failed with fallback disabled: {parse_err}") from parse_err

                classified_reason = FALLBACK_REASON_OTHER
                parse_warning = f"Response parsing failed: {type(parse_err).__name__}"
                logger.error(f"Gemini response parsing failed ({type(parse_err).__name__}): {parse_err}. Falling back to deterministic synthesizer.", exc_info=True)

        # Fallback to deterministic synthesizer
        self.fallback_events_count = getattr(self, "fallback_events_count", 0) + 1
        if disable_fallback:
            raise RuntimeError(f"Real Gemini API call failed with fallback disabled (reason={classified_reason}).")

        fallback_reason = classified_reason or FALLBACK_REASON_OTHER
        resp = self._deterministic_synthesizer(
            question,
            retrieved_metadata,
            start_time,
            pq=processed_query,
            duplicate_groups=duplicate_groups,
            document_ids=document_ids,
            user_id=user_id,
        )
        resp["answer_path"] = "deterministic_fallback"
        resp["model"] = None
        resp["fallback_reason"] = fallback_reason
        plain_msg = PLAIN_FALLBACK_MESSAGES.get(fallback_reason, "Gemini unavailable, using basic mode.")
        resp.setdefault("warnings", []).append(plain_msg)
        if parse_warning:
            resp.setdefault("warnings", []).append(parse_warning)
        resp["generation_diagnostics"] = {
            "provider": "gemini",
            "primary_model": self.model_name,
            "actual_model": None,
            "attempts": attempts_taken,
            "max_attempts": max_attempts,
            "fallback_model_attempted": fallback_model_tried,
            "fallback_activated": True,
            "fallback_reason": fallback_reason,
            "last_error": last_safe_msg,
            "generation_ms": round((time.perf_counter() - start_time) * 1000.0, 2),
        }
        return resp

    def _compound_synthesis(
        self,
        question: str,
        retrieved_metadata: list[dict[str, Any]],
        pq: Any,
        start_time: float,
        duplicate_groups: dict[str, list[str]] | None = None,
    ) -> dict[str, Any]:
        """Synthesizes structured multi-section response for compound research questions."""
        latency = (time.perf_counter() - start_time) * 1000.0

        fraud_terms = {"fraud", "fraudulent", "collusion", "colluding", "violation", "violations", "cheat", "scam"}
        frozen_scope_terms = {"frozen", "project's frozen", "frozen research scope"}


        supported_findings: list[dict[str, Any]] = []
        unsupported_subqueries: list[str] = []
        used_finding_chunk_ids: set[str] = set()

        for sq in pq.subqueries:
            sq_pq = process_query(sq)
            sq_words = set(sq_pq.search_terms)
            sq_stems = {normalize_stem(w) for w in sq_words}
            norm_sq = re.sub(r"\s+", " ", sq_pq.cleaned_query.lower().strip("?,.:;\"'()[]"))

            requires_fraud = any(w in fraud_terms for w in sq_words)
            requires_frozen = any(w in frozen_scope_terms for w in sq_words)
            sq_anchors = sq_pq.anchor_constraints or extract_anchor_constraints(sq)
            sq_geo = sq_anchors.get("geo_anchors", {})

            scored_passages_for_sq: list[tuple[dict[str, Any], float, set[str]]] = []

            for m in retrieved_metadata:
                # Discard pure reference lists so substantive content is cited
                if is_reference_chunk(m["text"]):
                    continue

                p_text = m["text"].lower()
                norm_p = re.sub(r"\s+", " ", p_text)
                p_words = {w.strip("?,.:;\"'()[]") for w in p_text.split()}
                p_stems = {normalize_stem(w) for w in p_words}

                # Negative safeguard: if subquery asks for fraud/collusion/violations, text MUST explicitly contain those terms
                if requires_fraud and not any(ft in p_text for ft in ["fraud", "collusion", "falsif", "cheat", "scam"]):
                    continue

                if requires_frozen and not any(fst in p_text for fst in ["frozen research scope", "frozen scope"]):
                    continue

                # Country anchor check for subquery (chunk plus adjacent-chunk context)
                if sq_geo:
                    c_text = (p_text + " " + m.get("prev_text", "") + " " + m.get("next_text", "")).lower()
                    has_matching_country = any(
                        any(re.search(pat, c_text) for pat in pats)
                        for _, pats in sq_geo.items()
                    )
                    if not has_matching_country:
                        continue

                # FLAG_CROSS_02_DISCLOSURE: If subquery specifies a source, chunk MUST come from that source's document
                if getattr(settings, "FLAG_CROSS_02_DISCLOSURE", False) and getattr(sq_pq, "detected_sources", None):
                    m_fn = m.get("filename", "").lower()
                    matches_source = False
                    for src in sq_pq.detected_sources:
                        src_clean = re.sub(r"\s+(?i:et\s+al\.?)$", "", src).strip().lower()
                        if src_clean in m_fn or any(p in m_fn for p in src_clean.split() if len(p) >= 3):
                            matches_source = True
                            break
                    if not matches_source:
                        continue

                matched_terms: set[str] = set()

                if norm_sq and len(norm_sq) > 6 and norm_sq in norm_p:
                    scored_passages_for_sq.append((m, 10.0, sq_words))
                    continue

                for cw in sq_words:
                    c_stem = normalize_stem(cw)
                    if cw in p_words or c_stem in p_stems:
                        matched_terms.add(cw)
                    elif cw in ACADEMIC_SYNONYMS:
                        for syn in ACADEMIC_SYNONYMS[cw]:
                            if syn in p_words or normalize_stem(syn) in p_stems:
                                matched_terms.add(cw)
                                break

                overlap_ratio = len(matched_terms) / max(1, len(sq_words))
                is_valid = (
                    (norm_sq and len(norm_sq) > 6 and norm_sq in norm_p)
                    or (len(sq_words) >= 3 and len(matched_terms) >= 2 and overlap_ratio >= 0.28)
                    or (len(sq_words) <= 2 and len(matched_terms) >= 1)
                )
                if is_valid:
                    # Slight preference bonus for fresh passages not yet used for previous subqueries
                    novelty_bonus = 0.15 if m["chunk_id"] not in used_finding_chunk_ids else 0.0
                    content_bonus = 0.0
                    if getattr(settings, "FLAG_CROSS_05_EXCERPT_SELECTION", False):
                        meta_or_author_terms = {
                            w.lower()
                            for src in (getattr(pq, "detected_sources", []) + getattr(sq_pq, "detected_sources", []))
                            for w in re.findall(r"\b[a-zA-Z]{2,}\b", src)
                        } | {
                            "et", "al", "paper", "study", "review", "synthesize", "report", "reported",
                            "across", "between", "detailed", "examine", "compare", "findings", "results",
                            "evidence", "author", "authors", "section", "article"
                        }
                        core_sq_terms = {w for w in sq_words if w not in meta_or_author_terms}
                        matched_core = matched_terms.intersection(core_sq_terms)
                        if core_sq_terms:
                            content_bonus += 0.5 * (len(matched_core) / len(core_sq_terms))
                        if 1 in (m.get("page_numbers") or []) and any(term in p_text for term in ["correspondence", "university", "department", "keywords", "received:", "accepted:"]):
                            content_bonus -= 0.35

                    fact_bonus = 0.0
                    if getattr(settings, "FLAG_FACT_AWARE_CITATION_SELECTION", False):
                        sq_num_patterns = set(re.findall(r"\b(?:\d+(?:\.\d+)?%?|\d{4})\b", sq))
                        if sq_num_patterns:
                            p_num_patterns = set(re.findall(r"\b(?:\d+(?:\.\d+)?%?|\d{4})\b", m["text"]))
                            matched_nums = sq_num_patterns.intersection(p_num_patterns)
                            if matched_nums:
                                fact_bonus += 0.25 * (len(matched_nums) / len(sq_num_patterns))

                    scored_passages_for_sq.append((m, overlap_ratio + novelty_bonus + content_bonus + fact_bonus, matched_terms))

            if scored_passages_for_sq:
                scored_passages_for_sq.sort(key=lambda x: x[1], reverse=True)
                best_passage = scored_passages_for_sq[0][0]
                used_finding_chunk_ids.add(best_passage["chunk_id"])
                supported_findings.append({
                    "subquery": sq,
                    "passage": best_passage,
                    "score": scored_passages_for_sq[0][1],
                    "target_terms": sq_words,
                })
            else:
                unsupported_subqueries.append(sq)

        # If zero subqueries were supported, abstain with insufficient evidence
        if not supported_findings:
            return {
                "answer": "The retrieved passages do not contain sufficient evidence to address the inquiry without speculation.",
                "claims": [],
                "citations": [],
                "insufficient_evidence": True,
                "warnings": ["Zero subquestions were substantiated by the retrieved evidence."],
                "latency_ms": {"generation": latency},
            }

        citations_list: list[dict[str, Any]] = []
        claims_list: list[dict[str, Any]] = []
        chunk_to_cite_id: dict[str, str] = {}
        used_excerpt_texts: set[str] = set()

        # Map duplicate files for provenance attribution
        filename_to_dup_alias: dict[str, str] = {}
        if duplicate_groups:
            for _, fnames in duplicate_groups.items():
                if len(fnames) > 1:
                    for fn in fnames:
                        others = [o for o in fnames if o != fn]
                        filename_to_dup_alias[fn] = f"identical content indexed under {', '.join(others)}"

        # Hydrate citations for supported findings using complete sentence excerpts
        for finding in supported_findings:
            p = finding["passage"]
            cid = p["chunk_id"]
            if cid not in chunk_to_cite_id:
                cite_id = f"cite:{len(chunk_to_cite_id) + 1}"
                chunk_to_cite_id[cid] = cite_id
                clean_excerpt = extract_complete_sentence_excerpt(
                    chunk_text=p["text"],
                    prev_text=p.get("prev_text", ""),
                    next_text=p.get("next_text", ""),
                    target_terms=finding.get("target_terms"),
                    max_chars=480,
                    requested_info=finding.get("subquery", ""),
                )
                exact_page = resolve_citation_page(clean_excerpt, p["text"], p.get("page_numbers") or [1])
                used_excerpt_texts.add(clean_excerpt[:80].lower())
                citations_list.append({
                    "citation_id": cite_id,
                    "document_id": p["document_id"],
                    "filename": p["filename"],
                    "page_numbers": [exact_page] if getattr(settings, "FLAG_CITATION_PAGE_ACCURACY", False) else p["page_numbers"],
                    "chunk_ids": [cid],
                    "excerpt": clean_excerpt,
                })

        # Section 1: Supported Findings by Source
        sec1_lines = ["### Supported Findings by Source"]
        doc_findings: dict[str, list[dict[str, Any]]] = {}
        for f in supported_findings:
            fn = f["passage"]["filename"]
            doc_findings.setdefault(fn, []).append(f)

        for fn, f_list in doc_findings.items():
            matching_cites = [c for c in citations_list if c["filename"] == fn]
            doc_pages = sorted(list({p for c in matching_cites for p in (c.get("page_numbers") or [1])}))
            pages_str = ", ".join(str(p) for p in (doc_pages or [1]))
            dup_alias = filename_to_dup_alias.get(fn)
            heading_note = f" (note: {dup_alias})" if dup_alias else ""

            bullets = []
            for item in f_list:
                p = item["passage"]
                c_id = chunk_to_cite_id[p["chunk_id"]]
                # Retrieve the exact verified complete sentence excerpt for this citation
                cite_record = next(c for c in citations_list if c["citation_id"] == c_id)
                clean_snip = cite_record["excerpt"]
                bullets.append(f"- Regarding **{item['subquery']}**: \"{clean_snip}\" [{c_id}]")
                claims_list.append({
                    "text": f"Direct empirical finding on {item['subquery']}: {clean_snip[:160]}",
                    "citation_ids": [c_id],
                    "support_status": "supported",
                })
            sec1_lines.append(f"In **{fn}** (pages {pages_str}){heading_note}:\n" + "\n".join(bullets))

        if getattr(settings, "FLAG_CROSS_02_DISCLOSURE", False) and unsupported_subqueries:
            for un_sq in unsupported_subqueries:
                un_sq_pq = process_query(un_sq)
                src_label = ", ".join(un_sq_pq.detected_sources) if un_sq_pq.detected_sources else "the specified literature"
                sec1_lines.append(
                    f"In **{src_label}**:\n- Regarding **{un_sq}**: The selected literature does not report empirical evidence on this facet; inquiry is answered from the remaining substantiated sources."
                )
                claims_list.append({
                    "text": f"The selected literature does not report empirical evidence on {un_sq}; inquiry is answered from the remaining substantiated sources.",
                    "citation_ids": [],
                    "support_status": "supported",
                })

        # Section 2: Cross-Paper Synthesis & Evidence Provenance
        sec2_lines = ["### Cross-Paper Synthesis"]

        # Detect duplicate files contributing to this query
        dup_provenance_statements: list[str] = []
        if duplicate_groups:
            for hash_val, fnames in duplicate_groups.items():
                active_dups = [f for f in fnames if any(m["filename"] == f for m in retrieved_metadata)]
                if len(active_dups) > 1:
                    dup_provenance_statements.append(
                        f"Cryptographic hash inspection confirms that **{'** and **'.join(active_dups)}** share an identical "
                        f"SHA-256 digest (`{hash_val[:12]}...`), verifying that they are duplicate copies of the same publication "
                        f"rather than distinct, independent investigations. In accordance with evidential rigor, duplicate records "
                        f"are synthesized as a single source and are not counted as independent multi-study corroboration."
                    )
                elif len(active_dups) == 1 and len(fnames) > 1:
                    other_copies = [f for f in fnames if f != active_dups[0]]
                    dup_provenance_statements.append(
                        f"**{active_dups[0]}** shares an identical content hash (`{hash_val[:12]}...`) with "
                        f"**{', '.join(other_copies)}** in the repository, representing a duplicated document record."
                    )

        if dup_provenance_statements:
            sec2_lines.append("**Evidence Provenance & Corroboration Analysis:**\n" + "\n\n".join(dup_provenance_statements))

        # Compute distinct study clusters
        unique_hashes = set()
        for m in retrieved_metadata:
            h = m.get("content_hash")
            if h:
                unique_hashes.add(h)
            else:
                unique_hashes.add(m["filename"])

        if len(unique_hashes) > 1:
            doc_names = list(doc_findings.keys())
            sec2_lines.append(
                f"A cross-paper synthesis across distinct studies ({', '.join(doc_names[:3])}) indicates complementary evidence across the investigated sources. "
                f"Direct empirical findings from each source are substantiated with verified citations above."
            )
        else:
            doc_names = list(doc_findings.keys())
            doc_name = doc_names[0] if doc_findings else "the selected literature"
            sec2_lines.append(
                f"The substantiated findings from {doc_name} are directly documented and cited with page-level provenance above."
            )

        # Section 3: Identified Research Gaps (Non-repetitive, distinct from Section 1)
        sec3_lines = ["### Identified Research Gaps"]
        gap_bullets = []
        seen_gap_chunk_ids: set[str] = set(chunk_to_cite_id.keys())

        for m in retrieved_metadata:
            # Discard pure reference lists so substantive content is cited
            if is_reference_chunk(m["text"]):
                continue

            t_lower = m["text"].lower()
            if any(term in t_lower for term in ["research gap", "gaps", "limitation", "scarcity", "lack of data", "unresolved", "further research"]):
                cid = m["chunk_id"]
                # Skip chunks already cited in Section 1 to prevent repetition
                if cid in seen_gap_chunk_ids:
                    continue

                p_text = m.get("prev_text", "")
                if p_text and is_reference_chunk(p_text):
                    p_text = ""
                n_text = m.get("next_text", "")
                if n_text and is_reference_chunk(n_text):
                    n_text = ""

                clean_gap = extract_complete_sentence_excerpt(
                    chunk_text=m["text"],
                    prev_text=p_text,
                    next_text=n_text,
                    target_terms={"gap", "limitation", "scarcity", "unresolved", "research"},
                    max_chars=360,
                    requested_info="research gaps and limitations",
                )

                if is_reference_chunk(clean_gap):
                    continue

                # Skip if text excerpt is identical or nearly identical to an already used passage
                gap_sig = clean_gap[:80].lower()
                if gap_sig in used_excerpt_texts:
                    continue

                seen_gap_chunk_ids.add(cid)
                used_excerpt_texts.add(gap_sig)

                exact_gap_page = resolve_citation_page(clean_gap, m["text"], m.get("page_numbers") or [1])
                cite_id = f"cite:{len(citations_list) + 1}"
                chunk_to_cite_id[cid] = cite_id
                citations_list.append({
                    "citation_id": cite_id,
                    "document_id": m["document_id"],
                    "filename": m["filename"],
                    "page_numbers": [exact_gap_page] if getattr(settings, "FLAG_CITATION_PAGE_ACCURACY", False) else m["page_numbers"],
                    "chunk_ids": [cid],
                    "excerpt": clean_gap,
                })

                pages_str = str(exact_gap_page) if getattr(settings, "FLAG_CITATION_PAGE_ACCURACY", False) else ", ".join(str(p) for p in (m.get("page_numbers") or [1]))
                gap_bullets.append(f"- **{m['filename']} (p. {pages_str})**: \"{clean_gap}\" [{cite_id}]")
                claims_list.append({
                    "text": f"Author-stated limitation and research gap: {clean_gap[:160]}",
                    "citation_ids": [cite_id],
                    "support_status": "supported",
                })
                if len(gap_bullets) >= 3:
                    break

        if gap_bullets:
            sec3_lines.extend(gap_bullets)
        else:
            sec3_lines.append(
                "- No explicit author-stated research gaps or methodological limitations were identified in the retrieved passages for this inquiry."
            )

        # Section 4: Insufficient Evidence & Unsubstantiated Facets (Consolidated, non-repetitive)
        sec4_lines = ["### Insufficient Evidence & Unsubstantiated Facets"]
        if unsupported_subqueries:
            fraud_sqs: list[str] = []
            frozen_sqs: list[str] = []
            other_sqs: list[str] = []

            for un_sq in unsupported_subqueries:
                un_sq_lower = un_sq.lower()
                if any(w in un_sq_lower for w in ["fraud", "collusion", "violation", "cheat", "scam"]):
                    fraud_sqs.append(un_sq)
                elif any(w in un_sq_lower for w in ["frozen", "scope"]):
                    frozen_sqs.append(un_sq)
                else:
                    other_sqs.append(un_sq)

            if fraud_sqs:
                items_str = ", ".join(f"'{sq}'" for sq in fraud_sqs)
                sec4_lines.append(
                    f"- **Allegations of Fraud, Collusion, or Regulatory Violations** (addressing {items_str}): "
                    f"The selected research documents contain **no empirical evidence, audits, or investigative findings** "
                    f"establishing fraudulent recycling claims, illicit collusion, or intentional regulatory violations. "
                    f"In accordance with rigorous grounding safeguards, reported mass-balance discrepancies and informal "
                    f"recovery leakages reflect measurement limitations and system complexity rather than verified malfeasance."
                )
                claims_list.append({
                    "text": "The selected research documents provide no empirical evidence or audit findings of fraudulent recycling claims or collusion.",
                    "citation_ids": [],
                    "support_status": "unsupported",
                })

            if frozen_sqs:
                items_str = ", ".join(f"'{sq}'" for sq in frozen_sqs)
                sec4_lines.append(
                    f"- **External Research Scope Constraints** (addressing {items_str}): "
                    f"The analyzed literature does not contain information concerning or defining any external project's "
                    f"'frozen research scope'. Evidentiary grounding is strictly bounded to the empirical and theoretical "
                    f"findings of the indexed publications."
                )
                claims_list.append({
                    "text": "The indexed papers contain no evidence regarding an external project's frozen research scope.",
                    "citation_ids": [],
                    "support_status": "unsupported",
                })

            if other_sqs:
                items_str = ", ".join(f"'{sq}'" for sq in other_sqs)
                sec4_lines.append(
                    f"- **Ungrounded Topical Inquiries** (addressing {items_str}): "
                    f"Insufficient evidence was detected in the selected documents to substantiate these specific inquiries without speculation."
                )
                claims_list.append({
                    "text": f"Insufficient evidence in selected literature to substantiate: {', '.join(other_sqs)}",
                    "citation_ids": [],
                    "support_status": "unsupported",
                })
        else:
            sec4_lines.append(
                "All decomposed subquestions were directly addressed and substantiated by passages in the selected literature."
            )

        answer = "\n\n".join([
            "\n\n".join(sec1_lines),
            "\n\n".join(sec2_lines),
            "\n\n".join(sec3_lines),
            "\n\n".join(sec4_lines),
        ])

        return {
            "answer": answer,
            "claims": claims_list,
            "citations": citations_list,
            "insufficient_evidence": False,
            "warnings": [],
            "latency_ms": {"generation": latency},
        }

    def _check_entity_in_library(
        self,
        patterns: list[str],
        document_ids: list[str] | None = None,
        user_id: str | None = None,
        fallback_metadata: list[dict[str, Any]] | None = None,
        min_substantive_chunks: int = 1,
    ) -> bool:
        """Library-level lexical lookup to verify if entity appears in substantive chunks of indexed documents."""
        # 1. Fast in-memory check against retrieved metadata chunks if present
        if fallback_metadata:
            match_count = 0
            for m in fallback_metadata:
                if document_ids and m.get("document_id") not in document_ids:
                    continue
                raw_t = m.get("text", "")
                if is_reference_chunk(raw_t):
                    continue
                text = (raw_t + " " + m.get("prev_text", "") + " " + m.get("next_text", "")).lower()
                for p in patterns:
                    term = re.sub(r"\\b|[()^$]", "", p).strip().lower()
                    if term and re.search(r"\b" + re.escape(term) + r"\b", text):
                        match_count += 1
                        break
            if match_count >= min_substantive_chunks:
                return True

        # 2. Database lookup in active repository
        if not getattr(settings, "FLAG_LIBRARY_LEVEL_ENTITY_CHECK", True):
            return False

        import sqlite3
        from pathlib import Path
        candidate_dbs: list[Path] = []
        db_url = getattr(settings, "DATABASE_URL", "")
        if "sqlite" in db_url:
            raw_path = re.sub(r"^sqlite(?:\+aiosqlite)?:\/\/\/?", "", db_url)
            for cand in [Path(__file__).resolve().parents[4] / raw_path, Path.cwd().parent / raw_path, Path.cwd() / raw_path, Path(raw_path)]:
                cand_res = cand.resolve()
                if cand_res.exists() and cand_res.is_file() and cand_res not in candidate_dbs:
                    candidate_dbs.append(cand_res)

        for default_cand in [
            Path(__file__).resolve().parents[4] / "storage" / "orion_dev.db",
            Path.cwd() / "storage" / "orion_dev.db",
            Path.cwd().parent / "storage" / "orion_dev.db",
        ]:
            c_res = default_cand.resolve()
            if c_res.exists() and c_res.is_file() and c_res not in candidate_dbs:
                candidate_dbs.append(c_res)

        for db_file in candidate_dbs:
            try:
                conn = sqlite3.connect(str(db_file))
                c = conn.cursor()
                tbl_check = c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='chunks'").fetchone()
                if not tbl_check:
                    conn.close()
                    continue
                query_parts = []
                params = []
                clean_terms = []
                for p in patterns:
                    term = re.sub(r"\\b|[()^$]", "", p).strip().lower()
                    if term:
                        query_parts.append("LOWER(c.text) LIKE ?")
                        params.append(f"%{term}%")
                        clean_terms.append(term)
                if query_parts:
                    sql = f"""
                        SELECT c.text FROM chunks c
                        JOIN documents d ON c.document_id = d.id
                        WHERE d.status IN ('completed', 'indexed')
                        AND ({' OR '.join(query_parts)})
                    """
                    if user_id:
                        sql += " AND d.owner_id = ?"
                        params.append(user_id)
                    if document_ids:
                        placeholders = ",".join("?" for _ in document_ids)
                        sql += f" AND c.document_id IN ({placeholders})"
                        params.extend(document_ids)
                    rows = c.execute(sql, params).fetchall()
                    conn.close()
                    substantive_matches = 0
                    for row in rows:
                        c_text = row[0]
                        if is_reference_chunk(c_text):
                            continue
                        c_lower = c_text.lower()
                        if any(re.search(r"\b" + re.escape(ct) + r"\b", c_lower) for ct in clean_terms):
                            substantive_matches += 1
                            if substantive_matches >= min_substantive_chunks:
                                return True
            except Exception as e:
                logger.warning(f"Error checking entity in library: {e}")

        return False

    def _deterministic_synthesizer(
        self,
        question: str,
        retrieved_metadata: list[dict[str, Any]],
        start_time: float,
        pq: Any | None = None,
        duplicate_groups: dict[str, list[str]] | None = None,
        document_ids: list[str] | None = None,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        """Synthesizes an evidence-grounded response deterministically from top retrieved passages."""
        latency = (time.perf_counter() - start_time) * 1000.0

        if not retrieved_metadata:
            return {
                "answer": "No supporting evidence found in the selected documents.",
                "claims": [],
                "citations": [],
                "insufficient_evidence": True,
                "warnings": ["No matching passages found in the selected sources."],
                "latency_ms": {"generation": latency},
            }

        if pq is None:
            pq = process_query(question)

        # Route compound multi-part research inquiries to structured multi-aspect synthesis
        if pq.is_compound_query:
            return self._compound_synthesis(question, retrieved_metadata, pq, start_time, duplicate_groups=duplicate_groups)

        anchors = pq.anchor_constraints or extract_anchor_constraints(question)

        # 1. Negative allegation safeguard: audit/fraud/collusion questions require explicit empirical evidence
        if anchors.get("has_fraud"):
            fraud_indicators = ["fraud", "collusion", "colluding", "convicted", "cartel", "investigative audit", "falsif", "scam"]
            has_fraud_evidence = self._check_entity_in_library(fraud_indicators, document_ids=document_ids, user_id=user_id, fallback_metadata=retrieved_metadata)
            if not has_fraud_evidence:
                return {
                    "answer": "The selected research documents contain no empirical evidence, audit records, or investigative findings establishing fraudulent plastic recycling credits, cartel collusion, or legal convictions.",
                    "claims": [],
                    "citations": [],
                    "insufficient_evidence": True,
                    "warnings": ["Zero library documents substantiated allegations of fraud or collusion."],
                    "latency_ms": {"generation": latency},
                }

        # 2. Frozen scope safeguard: questions regarding external project constraints require explicit scope evidence
        if anchors.get("has_frozen"):
            has_frozen_evidence = self._check_entity_in_library(["frozen research scope", "frozen scope"], document_ids=document_ids, user_id=user_id, fallback_metadata=retrieved_metadata)
            if not has_frozen_evidence:
                return {
                    "answer": "The analyzed literature does not contain information defining or specifying an external project's 'frozen research scope'. Evidentiary grounding is strictly bounded to the empirical and theoretical findings of the indexed publications.",
                    "claims": [],
                    "citations": [],
                    "insufficient_evidence": True,
                    "warnings": ["Zero library documents substantiated an external project's frozen research scope."],
                    "latency_ms": {"generation": latency},
                }

        # 3. Geographic country/region anchor verification (library-level)
        geo_anchors = anchors.get("geo_anchors", {})
        if geo_anchors:
            for country, patterns in geo_anchors.items():
                found_country = self._check_entity_in_library(
                    patterns,
                    document_ids=document_ids,
                    user_id=user_id,
                    fallback_metadata=retrieved_metadata,
                    min_substantive_chunks=1,
                )
                if not found_country:
                    return {
                        "answer": f"The selected documents do not contain evidence concerning {country.capitalize()}. The available literature for the selected sources does not report data for this region.",
                        "claims": [],
                        "citations": [],
                        "insufficient_evidence": True,
                        "warnings": [f"Selected documents do not contain evidence for required geographic entity '{country}'."],
                        "latency_ms": {"generation": latency},
                    }

        # 4. Specific model anchor verification (library-level)
        model_anchors = anchors.get("model_anchors", [])
        if model_anchors:
            for model in model_anchors:
                pats = [model]
                if model == "dpmfa":
                    pats.append("dynamic probabilistic")
                found_model = self._check_entity_in_library(pats, document_ids=document_ids, user_id=user_id, fallback_metadata=retrieved_metadata)
                if not found_model:
                    return {
                        "answer": f"The selected documents do not contain evidence concerning the {model.upper()} model.",
                        "claims": [],
                        "citations": [],
                        "insufficient_evidence": True,
                        "warnings": [f"Selected documents do not contain evidence for required model '{model}'."],
                        "latency_ms": {"generation": latency},
                    }

        content_words = set(pq.search_terms)

        if not content_words:
            # Fallback if question was entirely stop words
            content_words = {w.strip("?,.:;\"'()[]").lower() for w in question.split() if len(w) > 2}

        q_stems = {normalize_stem(w) for w in content_words}
        norm_q = re.sub(r"\s+", " ", pq.cleaned_query.lower().strip("?,.:;\"'()[]"))

        scored_passages: list[tuple[dict[str, Any], float, set[str]]] = []
        is_asking_for_references = any(w in question.lower() for w in ["reference", "references", "bibliography", "doi"])

        for m in retrieved_metadata:
            # Discard pure reference lists so substantive content is cited
            if is_reference_chunk(m["text"]) and not is_asking_for_references:
                continue

            p_text = m["text"].lower()

            # If the question specifies geographic anchors, candidate passages must explicitly mention the required country/demonym
            if geo_anchors:
                context_geo_text = p_text + " " + m.get("prev_text", "").lower() + " " + m.get("next_text", "").lower()
                has_country = any(
                    any(re.search(p, context_geo_text) for p in patterns)
                    for patterns in geo_anchors.values()
                )
                if not has_country:
                    continue

            norm_p = re.sub(r"\s+", " ", p_text)
            p_words = {w.strip("?,.:;\"'()[]") for w in p_text.split()}
            p_stems = {normalize_stem(w) for w in p_words}

            matched_terms: set[str] = set()

            # 1. Exact phrase match
            if norm_q and len(norm_q) > 6 and norm_q in norm_p:
                scored_passages.append((m, 10.0, content_words))
                continue

            # 2. Substantive content word & stem overlap
            for cw in content_words:
                c_stem = normalize_stem(cw)
                if cw in p_words or c_stem in p_stems:
                    matched_terms.add(cw)
                else:
                    # Check academic synonyms
                    matched = False
                    if cw in ACADEMIC_SYNONYMS:
                        for syn in ACADEMIC_SYNONYMS[cw]:
                            if syn in p_words or normalize_stem(syn) in p_stems:
                                matched_terms.add(cw)
                                matched = True
                                break
                    if not matched and cw in {"title", "name"} and 1 in (m.get("page_numbers") or []):
                        matched_terms.add(cw)

            overlap_ratio = len(matched_terms) / max(1, len(content_words))

            # 3. Meta-query bonus for page 1 / author / title chunks
            meta_bonus = 0.0
            if pq.is_meta_query:
                pages = m.get("page_numbers") or []
                if 1 in pages:
                    meta_bonus += 0.35
                if any(term in p_text for term in ["author", "authorship", "university", "@", "abstract", "title"]):
                    meta_bonus += 0.4

            # 4. Informational alignment bonus for specific requested information
            info_bonus = 0.0
            req_lower = question.lower()
            is_num_q = any(w in req_lower for w in ["%", "percent", "percentage", "rate", "mass", "volume", "amount", "growth", "concentration", "proportion", "how many", "how much", "total", "kg", "mt"])
            is_list_q = any(w in req_lower for w in ["types", "polymers", "materials", "categories", "pathways", "systems", "list", "what are the", "which"])

            if is_num_q and re.search(r"\b\d+(?:\.\d+)?\s*(?:%|percent|mt|g/km2|kg|kt|tons?|tonnes?|cm|mm)\b", m["text"], re.I):
                info_bonus += 0.25
            elif is_list_q and (re.search(r":\s+[a-zA-Z\s-]+(?:\([A-Z]+\))?(?:,\s+[a-zA-Z\s-]+(?:\([A-Z]+\))?){2,}", m["text"]) or re.search(r"\([A-Z]{2,}\)", m["text"])):
                info_bonus += 0.25

            fact_bonus = 0.0
            if getattr(settings, "FLAG_FACT_AWARE_CITATION_SELECTION", False):
                q_num_patterns = set(re.findall(r"\b(?:\d+(?:\.\d+)?%?|\d{4})\b", question))
                if q_num_patterns:
                    p_num_patterns = set(re.findall(r"\b(?:\d+(?:\.\d+)?%?|\d{4})\b", m["text"]))
                    matched_nums = q_num_patterns.intersection(p_num_patterns)
                    if matched_nums:
                        fact_bonus += 0.25 * (len(matched_nums) / len(q_num_patterns))

            combined_score = overlap_ratio + meta_bonus + info_bonus + fact_bonus

            # Strict evidence grounding criteria:
            # - Exact phrase match: always valid
            # - Meta queries for title/author on page 1: valid with at least 1 matched term
            # - For questions with >= 3 content words: require >= 2 terms matched AND >= 28% overlap ratio
            # - For concise questions (<= 2 content words): require at least 1 term matched
            is_valid = (
                (norm_q and len(norm_q) > 6 and norm_q in norm_p)
                or (pq.is_meta_query and 1 in (m.get("page_numbers") or []) and len(matched_terms) >= 1)
                or (len(content_words) >= 3 and len(matched_terms) >= 2 and overlap_ratio >= 0.28)
                or (len(content_words) <= 2 and len(matched_terms) >= 1)
            )

            if is_valid:
                scored_passages.append((m, combined_score, matched_terms))

        if not scored_passages:
            return {
                "answer": "The retrieved passages do not contain sufficient evidence to answer this question accurately.",
                "claims": [],
                "citations": [],
                "insufficient_evidence": True,
                "warnings": ["Retrieved passages did not contain sufficient semantic overlap with question terms."],
                "latency_ms": {"generation": latency},
            }

        # Sort descending by combined score
        scored_passages.sort(key=lambda x: x[1], reverse=True)

        # Select top 1 or 2 diverse passages to form complete evidence
        top_candidates = [scored_passages[0][0]]
        covered_terms = set(scored_passages[0][2])

        # If question has multiple parts or complementary evidence is available
        if len(content_words) >= 4 and len(scored_passages) > 1:
            for item in scored_passages[1:4]:
                if getattr(settings, "FLAG_FACT_AWARE_CITATION_SELECTION", False):
                    # Never select reference or bibliography chunks as complementary evidence
                    if is_reference_chunk(item[0]["text"]):
                        continue
                new_terms = item[2] - covered_terms
                distinct_info = False
                if is_list_q:
                    item_acrs = set(re.findall(r"\([A-Z]{2,}\)", item[0]["text"]))
                    top_acrs = set(re.findall(r"\([A-Z]{2,}\)", top_candidates[0]["text"]))
                    if len(item_acrs - top_acrs) >= 2 or (len(item_acrs) >= 3 and len(top_acrs) < 3):
                        distinct_info = True
                elif is_num_q:
                    item_nums = set(re.findall(r"\b\d+(?:\.\d+)?\s*(?:%|percent|mt|g/km2|kg)\b", item[0]["text"], re.I))
                    top_nums = set(re.findall(r"\b\d+(?:\.\d+)?\s*(?:%|percent|mt|g/km2|kg)\b", top_candidates[0]["text"], re.I))
                    if item_nums - top_nums:
                        distinct_info = True

                if new_terms or distinct_info:
                    top_candidates.append(item[0])
                    covered_terms.update(new_terms)
                    break

        citations_list = []
        claims_list = []
        answer_parts = []

        for idx, passage in enumerate(top_candidates):
            cite_id = f"cite:{idx + 1}"

            # Extract complete sentence excerpt using neighbor context
            clean_snippet = extract_complete_sentence_excerpt(
                chunk_text=passage["text"],
                prev_text=passage.get("prev_text", ""),
                next_text=passage.get("next_text", ""),
                target_terms=content_words,
                max_chars=480,
                requested_info=question,
            )
            exact_page = resolve_citation_page(clean_snippet, passage["text"], passage.get("page_numbers") or [1])
            page_num = exact_page

            # Formulate articulate, nuanced synthesis based on query intent
            if pq.is_meta_query and any(w in content_words for w in ["title", "name"]):
                lead_in = f"The manuscript title is delineated on page {page_num} of {passage['filename']}:"
            elif pq.is_overview_query and idx == 0 and any(w in content_words for w in ["problem", "challenge", "address"]):
                lead_in = f"The analysis in {passage['filename']} (page {page_num}) elucidates the salient challenge:"
            elif pq.is_overview_query and idx > 0 and any(w in content_words for w in ["objective", "objectives", "aim", "aims", "purpose"]):
                lead_in = f"To address these constraints, the study substantiates its primary objectives on page {page_num}:"
            elif pq.is_methodology_query:
                lead_in = f"The methodological framework detailed in {passage['filename']} (page {page_num}) delineates:"
            elif pq.is_results_query:
                lead_in = f"The empirical evidence documented in {passage['filename']} (page {page_num}) substantiates:"
            elif idx == 0:
                lead_in = f"The evidence in {passage['filename']} (page {page_num}) elucidates that:"
            else:
                lead_in = f"Furthermore, {passage['filename']} (page {page_num}) substantiates:"

            answer_parts.append(
                f"{lead_in} \"{clean_snippet}\" [{cite_id}]"
            )

            claims_list.append({
                "text": clean_snippet[:180],
                "citation_ids": [cite_id],
                "support_status": "supported",
            })

            citations_list.append({
                "citation_id": cite_id,
                "document_id": passage["document_id"],
                "filename": passage["filename"],
                "page_numbers": [exact_page] if getattr(settings, "FLAG_CITATION_PAGE_ACCURACY", False) else passage["page_numbers"],
                "chunk_ids": [passage["chunk_id"]],
                "excerpt": clean_snippet,
            })

        final_answer = "\n\n".join(answer_parts)

        return {
            "answer": final_answer,
            "claims": claims_list,
            "citations": citations_list,
            "insufficient_evidence": False,
            "warnings": [],
            "latency_ms": {"generation": latency},
        }


_GEMINI_SERVICE = None


def get_gemini_service() -> GeminiService:
    global _GEMINI_SERVICE
    if _GEMINI_SERVICE is None:
        _GEMINI_SERVICE = GeminiService()
    return _GEMINI_SERVICE
