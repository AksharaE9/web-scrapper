"""
Explainability Engine — Translates machine reason codes and feature contributions into human UI chips
"""

from __future__ import annotations

from typing import Any


def format_reason_chip(code: str, detail: str | None = None, weight: float | None = None) -> dict[str, str]:
    """Return structured chip payload: {type: 'positive'|'negative'|'neutral', label: str, icon: str}."""
    c = code.lower().strip()

    # Category defining & supporting
    if "def_cat" in c or "def_osm" in c or c.startswith("category"):
        label = detail or "listed in defining category"
        return {"type": "positive", "label": label, "icon": "✓"}
    elif "supp_cat" in c:
        return {"type": "positive", "label": detail or "supporting category match", "icon": "✓"}

    # Name defining
    elif "def_name" in c or (c.startswith("name") and "only" not in c):
        return {"type": "positive", "label": detail or "name explicitly matches keyword", "icon": "✓"}

    # Web evidence
    elif "def_web" in c or c.startswith("web"):
        return {"type": "positive", "label": detail or "website corroborates keyword", "icon": "✓"}

    # Supporting terms
    elif "supp_term" in c:
        return {"type": "positive", "label": detail or "supporting terms found in profile", "icon": "✓"}

    # Semantic embeddings
    elif "sem_neg" in c:
        return {"type": "negative", "label": detail or "text resembles incompatible category", "icon": "✗"}
    elif "sem_pos" in c or "bi_encoder" in c:
        sign = "+" if (weight or 0) >= 0 else ""
        lbl = f"semantic match ({sign}{weight:.2f})" if weight is not None else "semantic text match"
        return {"type": "positive", "label": lbl, "icon": "✓"}
    elif "sem_margin" in c:
        return {"type": "positive" if (weight or 0) >= 0 else "negative", "label": detail or "semantic margin match", "icon": "✓" if (weight or 0) >= 0 else "~"}

    # Cross encoder
    elif "ce" in c or "cross_encoder" in c:
        p_val = round((weight or 0) * 100) if weight is not None else None
        if p_val is not None:
            lbl = f"text match ({p_val}%)" if weight is not None else "cross-encoder text match"
        else:
            lbl = detail or "cross-encoder text match"
        return {"type": "positive" if (weight or 0) >= 0.5 else "negative", "label": lbl, "icon": "✓" if (weight or 0) >= 0.5 else "✗"}

    # Hard gates / Vetoes
    elif "veto" in c:
        return {"type": "negative", "label": detail or "incompatible category or term", "icon": "✗"}
    elif "host" in c:
        return {"type": "neutral", "label": detail or "host category only (e.g. restaurant inside hotel)", "icon": "~"}
    elif "nonev" in c or "non_evidence" in c:
        return {"type": "negative", "label": detail or "generic stopword/prefix only", "icon": "✗"}
    elif "outside_boundary" in c:
        return {"type": "negative", "label": detail or "outside search boundary", "icon": "✗"}
    elif "closed" in c:
        return {"type": "negative", "label": detail or "permanently closed", "icon": "✗"}
    elif "name_only" in c:
        return {"type": "neutral", "label": detail or "name-only match (needs corroboration)", "icon": "~"}
    elif "concept_missing" in c:
        return {"type": "neutral", "label": detail or "unreviewed concept card", "icon": "~"}
    elif "llm" in c:
        is_rel = "relevant" in str(detail).lower()
        return {"type": "positive" if is_rel else "neutral", "label": f"AI review: {detail or 'adjudicated'}", "icon": "✓" if is_rel else "?"}

    # Clean fallback
    clean_label = detail or c.replace("f_", "").replace("_", " ")
    return {"type": "neutral", "label": clean_label, "icon": "~"}
