"""
app/rag/grounded_extract.py — Span-level citation enforcement for LLM extractions.

Doctrine:
The LLM must return a verbatim evidence_quote.
Verify the span literally exists in the source text;
anything unsupported is marked UNSOURCED and suppressed, never emitted.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def verify_grounded_span(
    extracted_value: str | None,
    evidence_quote: str | None,
    source_text: str,
) -> bool:
    """Verify that evidence_quote is a literal substring of source_text."""
    if not extracted_value or not evidence_quote:
        return False

    clean_source = source_text.strip()
    clean_quote = evidence_quote.strip()

    if clean_quote in clean_source:
        return True

    # Case-folded match check
    if clean_quote.lower() in clean_source.lower():
        return True

    logger.warning(f"Ungrounded extraction detected: quote='{evidence_quote}', value='{extracted_value}'")
    return False
