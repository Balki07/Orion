"""Google Gemini LLM Service with structured JSON output and test-mode fallback."""

import json
import time
from typing import Any

from app.core.config import settings
from app.core.logging import logger
from app.services.generation.prompts import (
    QA_PROMPT_TEMPLATE,
    SYSTEM_PROMPT,
)


class GeminiService:
    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY
        self.model_name = settings.GEMINI_MODEL
        self._client = None
        if self.api_key:
            self._init_client()

    def _init_client(self) -> None:
        try:
            from google import genai

            self._client = genai.Client(api_key=self.api_key)
            logger.info(f"Initialized Google Gemini client with model '{self.model_name}'.")
        except Exception as e:
            logger.warning(f"Could not initialize google-genai Client: {e}")
            self._client = None

    async def generate_grounded_answer(
        self,
        question: str,
        formatted_context: str,
        retrieved_metadata: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Calls Gemini with structured output constraints to generate evidence-grounded answers."""
        start_time = time.perf_counter()

        # If no context was retrieved at all, abstain immediately
        if not formatted_context.strip():
            latency = (time.perf_counter() - start_time) * 1000.0
            return {
                "answer": "The provided research documents do not contain sufficient evidence to answer this question.",
                "claims": [],
                "citations": [],
                "insufficient_evidence": True,
                "warnings": ["Zero relevant document passages were retrieved."],
                "latency_ms": {"generation": latency},
            }

        prompt = QA_PROMPT_TEMPLATE.format(
            context=formatted_context,
            question=question,
        )

        # 1. Real Gemini execution via official google-genai SDK if API key is present
        if self._client is not None:
            try:
                from google.genai import types

                response = self._client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_PROMPT,
                        temperature=settings.GEMINI_TEMPERATURE,
                        max_output_tokens=settings.GEMINI_MAX_OUTPUT_TOKENS,
                        response_mime_type="application/json",
                    ),
                )

                raw_json = response.text
                parsed = json.loads(raw_json)
                parsed["latency_ms"] = {
                    "generation": (time.perf_counter() - start_time) * 1000.0
                }
                return parsed

            except Exception as e:
                logger.error(f"Gemini API call failed: {e}. Falling back to deterministic synthesizer.", exc_info=True)

        # 2. Deterministic evidence synthesizer (used in local tests or when API key is pending)
        return self._deterministic_synthesizer(question, retrieved_metadata, start_time)

    def _deterministic_synthesizer(
        self,
        question: str,
        retrieved_metadata: list[dict[str, Any]],
        start_time: float,
    ) -> dict[str, Any]:
        """Synthesizes an evidence-grounded response deterministically from top retrieved passages."""
        latency = (time.perf_counter() - start_time) * 1000.0

        if not retrieved_metadata:
            return {
                "answer": "No supporting evidence found in the selected documents.",
                "claims": [],
                "citations": [],
                "insufficient_evidence": True,
                "warnings": ["No matching passages found."],
                "latency_ms": {"generation": latency},
            }

        # Check if substantive question terms appear in retrieved passages
        stop_words = {
            "what", "is", "the", "for", "and", "in", "of", "a", "an", "to", "on",
            "how", "why", "was", "are", "were", "did", "does", "by", "with", "from",
        }
        content_words = {
            w.strip("?,.:;\"'()[]") for w in question.lower().split()
            if len(w) > 2 and w.lower() not in stop_words
        }

        matched_passages = []
        for m in retrieved_metadata:
            p_text = m["text"].lower()
            p_words = {w.strip("?,.:;\"'()[]") for w in p_text.split()}
            overlap = content_words.intersection(p_words)
            overlap_ratio = len(overlap) / max(1, len(content_words))

            # Need at least 40% of substantive question terms present in passage
            if overlap_ratio >= 0.4:
                matched_passages.append(m)

        if not matched_passages:
            return {
                "answer": "The retrieved passages do not contain sufficient evidence to answer this question accurately.",
                "claims": [],
                "citations": [],
                "insufficient_evidence": True,
                "warnings": ["Retrieved passages did not contain sufficient semantic overlap with question terms."],
                "latency_ms": {"generation": latency},
            }

        top = matched_passages[0]
        cite_id = "cite:1"
        answer = f"Based on {top['filename']} (page {top['page_numbers'][0] if top['page_numbers'] else 1}): {top['text'][:300]}... [{cite_id}]"

        return {
            "answer": answer,
            "claims": [
                {
                    "text": top["text"][:200],
                    "citation_ids": [cite_id],
                    "support_status": "supported",
                }
            ],
            "citations": [
                {
                    "citation_id": cite_id,
                    "document_id": top["document_id"],
                    "filename": top["filename"],
                    "page_numbers": top["page_numbers"],
                    "chunk_ids": [top["chunk_id"]],
                    "excerpt": top["text"][:250],
                }
            ],
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
