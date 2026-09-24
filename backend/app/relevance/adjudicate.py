"""
R6 — Small-LLM Adjudicator with Literal Evidence Validation (Last Resort, <= 10%)

Uses local Ollama (qwen2.5:3b-instruct / llama3.2:3b) with structured output.
Strict post-validation: 'relevant' is honoured ONLY if the model returns a literal
evidence substring matching a defining/supporting term. Otherwise relegated to 'review'.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from typing import Any

import httpx

from app.relevance.concepts import ConceptCard
from app.relevance.tokenize import TokenizedProfile, sanitize_raw_text, canonicalize_token
from app.settings import settings

logger = logging.getLogger(__name__)


@dataclass
class AdjudicationResult:
    verdict: str   # 'relevant' | 'not_relevant' | 'unsure'
    outcome: str   # 'accepted' | 'rejected' | 'review'
    defining_evidence: str
    reason: str
    is_cached: bool = False


# In-memory session cache
_LLM_CACHE_MEM: dict[str, dict[str, Any]] = {}


def _make_cache_key(concept_id: str, version: int, profile_text: str, model: str) -> str:
    h = hashlib.sha256(profile_text.encode("utf-8")).hexdigest()
    return f"{concept_id}:v{version}:{model}:{h}"


async def adjudicate_candidate(
    profile: TokenizedProfile,
    card: ConceptCard,
    call_budget_remaining: int = 60,
) -> AdjudicationResult:
    """Adjudicate an uncertain candidate via local small-LLM with strict quote validation."""
    if not settings.llm_enabled or call_budget_remaining <= 0:
        return AdjudicationResult(
            verdict="unsure",
            outcome="review",
            defining_evidence="",
            reason="LLM disabled or budget exhausted; assigned to review band",
        )

    model_name = getattr(settings, "relevance_llm_model", "qwen2.5:3b-instruct")
    cache_key = _make_cache_key(card.concept_id, card.version, profile.profile_text, model_name)

    # Check cache
    if cache_key in _LLM_CACHE_MEM:
        cached = _LLM_CACHE_MEM[cache_key]
        return _validate_llm_response(cached, profile, card, is_cached=True)

    # Prepare prompt
    defining_terms_str = ", ".join(list(card.get_strong_defining_terms())[:12])
    supporting_terms_str = ", ".join(list(card.get_supporting_terms())[:12])

    system_prompt = (
        "You are an expert entity relevance classifier for Indian SMB business intelligence. "
        "Your task is to classify whether the given business profile is genuinely an instance of the target concept. "
        "Respond ONLY with valid JSON conforming to the schema:\n"
        '{"verdict": "relevant" | "not_relevant" | "unsure", '
        '"defining_evidence": "exact literal substring copied from profile, or empty string", '
        '"reason": "brief explanation in 25 words or less"}'
    )

    user_prompt = f"""Target Concept: {card.concept_id} ({", ".join(card.labels)})
Definition: {card.definition}
Defining Terms: {defining_terms_str}
Supporting Terms: {supporting_terms_str}

Candidate Profile to evaluate:
\"\"\"{profile.profile_text}\"\"\"

Classify this business. If relevant, you MUST copy the exact substring from the profile proving relevance.
"""

    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "format": "json",
        "stream": False,
        "options": {
            "temperature": 0.0,
            "num_ctx": 2048,
        },
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(f"{settings.ollama_url}/api/chat", json=payload)
            if resp.status_code == 200:
                body = resp.json()
                content = body.get("message", {}).get("content", "{}")
                parsed = json.loads(content)
                _LLM_CACHE_MEM[cache_key] = parsed
                return _validate_llm_response(parsed, profile, card, is_cached=False)
            else:
                logger.warning(f"Ollama returned HTTP {resp.status_code}")
    except Exception as e:
        logger.warning(f"Ollama adjudication error: {e}")

    return AdjudicationResult(
        verdict="unsure",
        outcome="review",
        defining_evidence="",
        reason="LLM unreachable; routed to review",
    )


def _validate_llm_response(
    resp_dict: dict[str, Any],
    profile: TokenizedProfile,
    card: ConceptCard,
    is_cached: bool = False,
) -> AdjudicationResult:
    """Enforce strict post-validation on LLM output."""
    verdict = resp_dict.get("verdict", "unsure").lower()
    evidence_quote = str(resp_dict.get("defining_evidence", "")).strip()
    reason = str(resp_dict.get("reason", ""))[:200]

    if verdict == "not_relevant":
        return AdjudicationResult(
            verdict="not_relevant",
            outcome="rejected",
            defining_evidence="",
            reason=reason or "LLM determined candidate is not relevant",
            is_cached=is_cached,
        )

    if verdict == "relevant":
        # NON-NEGOTIABLE VALIDATION:
        # 1. evidence_quote must be a literal substring of the profile
        # 2. evidence_quote must contain a defining or supporting term
        if evidence_quote and evidence_quote.lower() in profile.profile_text.lower():
            clean_quote = sanitize_raw_text(evidence_quote)
            quote_tokens = [canonicalize_token(t) for t in clean_quote.split()]
            valid_terms = card.get_strong_defining_terms().union(card.get_supporting_terms())

            if any(t in valid_terms for t in quote_tokens) or any(vt in clean_quote for vt in valid_terms):
                return AdjudicationResult(
                    verdict="relevant",
                    outcome="accepted",
                    defining_evidence=evidence_quote,
                    reason=reason or f"Validated evidence: '{evidence_quote}'",
                    is_cached=is_cached,
                )

        # Validation failed -> Relegate to review
        return AdjudicationResult(
            verdict="unsure",
            outcome="review",
            defining_evidence=evidence_quote,
            reason=f"LLM claimed relevant but evidence quote '{evidence_quote}' failed strict validation",
            is_cached=is_cached,
        )

    return AdjudicationResult(
        verdict="unsure",
        outcome="review",
        defining_evidence="",
        reason=reason or "Uncertain; routed to review band",
        is_cached=is_cached,
    )
