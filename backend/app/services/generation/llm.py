"""Google Gemini LLM Service with structured JSON output and test-mode fallback."""

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

    @staticmethod
    def _normalize_stem(word: str) -> str:
        for suffix in ("ability", "ibility", "ship", "tion", "tions", "ing", "ies", "es", "ed", "s"):
            if word.endswith(suffix) and len(word) - len(suffix) >= 3:
                return word[:-len(suffix)]
        return word

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

        stop_words = {
            "what", "is", "the", "for", "and", "in", "of", "a", "an", "to", "on",
            "how", "why", "was", "are", "were", "did", "does", "by", "with", "from",
            "who", "which", "whose", "when", "where", "can", "could", "should", "would",
            "about", "this", "that", "these", "those", "have", "had", "has", "do",
            "been", "being", "into", "than", "then", "there",
        }

        q_lower = question.lower()
        content_words = {
            w.strip("?,.:;\"'()[]") for w in q_lower.split()
            if len(w) > 2 and w.lower() not in stop_words
        }
        q_stems = {self._normalize_stem(w) for w in content_words}

        is_meta_query = any(w in q_lower for w in ["title", "author", "authors", "who", "paper", "name"])
        norm_q = re.sub(r"\s+", " ", q_lower.strip("?,.:;\"'()[]"))

        scored_passages: list[tuple[dict[str, Any], float]] = []

        for m in retrieved_metadata:
            p_text = m["text"].lower()
            norm_p = re.sub(r"\s+", " ", p_text)
            p_words = {w.strip("?,.:;\"'()[]") for w in p_text.split()}
            p_stems = {self._normalize_stem(w) for w in p_words}

            # 1. Exact phrase match
            if norm_q and len(norm_q) > 6 and norm_q in norm_p:
                scored_passages.append((m, 10.0))
                continue

            # 2. Substantive content word & stem overlap
            exact_matches = content_words.intersection(p_words)
            stem_matches = q_stems.intersection(p_stems)
            total_matches = len(exact_matches.union(stem_matches))
            overlap_ratio = total_matches / max(1, len(content_words))

            # 3. Meta-query bonus for page 1 / author / title chunks
            meta_bonus = 0.0
            if is_meta_query:
                if 1 in (m.get("page_numbers") or []):
                    meta_bonus += 0.3
                if any(term in p_text for term in ["author", "authorship", "university", "@", "abstract", "title"]):
                    meta_bonus += 0.4

            combined_score = overlap_ratio + meta_bonus

            # Strict evidence grounding criteria:
            # - For questions with >= 4 content words: require >= 35% overlap and >= 2 substantive terms
            # - For concise questions (< 4 content words): require at least 1 term match
            # - For meta-queries (title/author): require page 1 provenance or explicit meta markers
            is_valid = (
                (overlap_ratio >= 0.35 and total_matches >= 2)
                or (len(content_words) < 4 and total_matches >= 1)
                or (is_meta_query and (1 in (m.get("page_numbers") or []) or any(term in p_text for term in ["author", "authorship", "abstract"])))
            )

            if is_valid:
                scored_passages.append((m, combined_score))

        if not scored_passages:
            return {
                "answer": "The retrieved passages do not contain sufficient evidence to answer this question accurately.",
                "claims": [],
                "citations": [],
                "insufficient_evidence": True,
                "warnings": ["Retrieved passages did not contain sufficient semantic overlap with question terms."],
                "latency_ms": {"generation": latency},
            }

        scored_passages.sort(key=lambda x: x[1], reverse=True)
        top = scored_passages[0][0]
        cite_id = "cite:1"
        page_num = top["page_numbers"][0] if top.get("page_numbers") else 1
        answer = f"Based on {top['filename']} (page {page_num}): {top['text'][:300]}... [{cite_id}]"

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
