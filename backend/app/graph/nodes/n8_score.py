"""N8 ConfidenceScorer — Multi-source verification scoring and tier assignment."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any
import yaml

from app.graph.runtime import node
from app.graph.state import ResolvedEntity, RunState


CONFIG_PATH = Path(__file__).resolve().parent.parent.parent.parent / "config" / "scoring.yaml"


@lru_cache(maxsize=1)
def load_scoring_config() -> dict[str, Any]:
    """Load and validate scoring configuration."""
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"Scoring configuration not found at {CONFIG_PATH}")
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    # Validate required top-level keys
    expected_sections = {"weights", "penalties", "tiers"}
    missing = expected_sections - set(cfg.keys())
    if missing:
        raise ValueError(f"Missing sections in scoring.yaml: {missing}")

    expected_weights = {
        "base", "phone_valid", "email_valid", "website_accessible",
        "multi_source_agreement", "operating_status_open", "address_complete"
    }
    present_weights = set(cfg.get("weights", {}).keys())
    if expected_weights != present_weights:
        raise ValueError(f"Weight key mismatch in scoring.yaml: expected {expected_weights}, got {present_weights}")

    return cfg


@node("n8_score", critical=True, max_retries=0)
async def run(state: RunState) -> dict[str, Any]:
    cfg = load_scoring_config()
    weights = cfg["weights"]
    penalties = cfg["penalties"]
    tier_thresholds = cfg["tiers"]

    verified_threshold = tier_thresholds.get("verified_threshold", 0.80)
    likely_threshold = tier_thresholds.get("likely_threshold", 0.60)

    entities: list[ResolvedEntity] = state.get("entities", [])
    verifications = state.get("verifications", {})

    scored = []
    for entity in entities:
        checks = verifications.get(entity.id, [])
        passed_checks = {c.check_name for c in checks if c.outcome == "passed"}
        failed_checks = {c.check_name for c in checks if c.outcome == "failed"}

        score = float(weights.get("base", 0.35))

        # Add weights for passed checks
        if "phone_valid" in passed_checks:
            score += weights.get("phone_valid", 0.15)
        if "email_syntax" in passed_checks or "email_valid" in passed_checks:
            score += weights.get("email_valid", 0.10)
        if "website_accessible" in passed_checks:
            score += weights.get("website_accessible", 0.10)
        if "multi_source_agreement" in passed_checks:
            score += weights.get("multi_source_agreement", 0.20)
        if "operating_status_open" in passed_checks:
            score += weights.get("operating_status_open", 0.05)
        if "address_complete" in passed_checks or "address_completeness" in passed_checks:
            score += weights.get("address_complete", 0.05)

        # Apply penalties for failed checks
        if "personal_number_risk" in failed_checks:
            score += penalties.get("personal_number_risk", -0.10)
        if "operating_status_open" in failed_checks:
            score += penalties.get("disused_status", -0.30)

        # Clamp between 0.0 and 0.99
        score = max(0.01, min(0.99, score))

        # Corroboration requirement for Verified tier:
        # Must have at least one external corroboration:
        # - multi-source agreement (≥2 independent sources)
        # - website accessible and validated
        # - or phone confirmed across multiple sources
        has_external_corroboration = (
            "multi_source_agreement" in passed_checks
            or "website_accessible" in passed_checks
            or (entity.independent_source_count >= 2)
        )

        if score >= verified_threshold and has_external_corroboration:
            tier = "Verified"
        elif score >= likely_threshold:
            tier = "Likely"
        else:
            tier = "Unverified"

        scored.append(entity.model_copy(update={"confidence": round(score, 3), "tier": tier}))

    # Sort entities radiating outwards from the locality center:
    # Ring 0 (<1.5km), Ring 1 (1.5-3.5km), Ring 2 (3.5-6km), Ring 3 (>6km)
    def _rank_key(e: ResolvedEntity) -> tuple[int, float, float]:
        d = e.distance_m if e.distance_m is not None else 99999.0
        if d <= 1500:
            ring = 0
        elif d <= 3500:
            ring = 1
        elif d <= 6000:
            ring = 2
        else:
            ring = 3
        return (ring, -e.confidence, d)

    sorted_entities = sorted(scored, key=_rank_key)

    return {"entities": sorted_entities}

