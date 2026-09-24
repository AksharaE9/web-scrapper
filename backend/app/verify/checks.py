"""
app/verify/checks.py — Comprehensive verification check runner.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from app.graph.state import CheckResult, ResolvedEntity
from app.verify.email import verify_email
from app.verify.geo import verify_point_in_polygon
from app.verify.phone import verify_phone
from app.verify.web import verify_website


async def run_entity_verification_checks(
    entity: ResolvedEntity,
    boundary_wkt: str | None = None,
    target_locality: str | None = None,
    target_city: str | None = None,
) -> list[CheckResult]:
    """Execute real verification checks over a ResolvedEntity."""
    checks: list[CheckResult] = []
    now_iso = datetime.now(timezone.utc).isoformat()
    has_web = bool(entity.website_url or entity.website_domain)

    # 1. Inside Boundary Check
    if boundary_wkt:
        in_bounds = verify_point_in_polygon(entity.lon, entity.lat, boundary_wkt)
        checks.append(CheckResult(
            check_name="inside_boundary",
            outcome="passed" if in_bounds else "failed",
            detail={"lon": entity.lon, "lat": entity.lat, "in_bounds": in_bounds},
            checked_at=now_iso,
        ))

    # 2. Phone Verification
    if entity.phones_e164:
        first_phone = entity.phones_e164[0]
        p_res = verify_phone(first_phone, has_website=has_web)
        checks.append(CheckResult(
            check_name="phone_valid",
            outcome="passed" if p_res.is_valid else "failed",
            detail={"e164": p_res.e164, "number_type": p_res.number_type, "personal_risk": p_res.personal_risk},
            checked_at=now_iso,
        ))
        if p_res.personal_risk:
            checks.append(CheckResult(
                check_name="personal_number_risk",
                outcome="failed",
                detail={"note": "Mobile number without business website context"},
                checked_at=now_iso,
            ))
    else:
        checks.append(CheckResult(
            check_name="phone_valid",
            outcome="inconclusive",
            detail={"note": "No phone number available"},
            checked_at=now_iso,
        ))

    # 3. Multi-Source Corroboration
    if entity.independent_source_count >= 2:
        checks.append(CheckResult(
            check_name="multi_source_agreement",
            outcome="passed",
            detail={"sources": entity.source_ids, "count": entity.independent_source_count},
            checked_at=now_iso,
        ))

    # 4. Email Verification
    if entity.emails:
        first_email = entity.emails[0]
        e_res = await asyncio.to_thread(verify_email, first_email)
        checks.append(CheckResult(
            check_name="email_syntax",
            outcome="passed" if e_res.syntax_valid else "failed",
            detail={"email": first_email, "valid": e_res.syntax_valid},
            checked_at=now_iso,
        ))
        if e_res.syntax_valid:
            checks.append(CheckResult(
                check_name="email_mx",
                outcome="passed" if e_res.mx_valid else "failed",
                detail={"domain": e_res.domain, "mx_found": e_res.mx_valid},
                checked_at=now_iso,
            ))
    else:
        checks.append(CheckResult(
            check_name="email_syntax",
            outcome="inconclusive",
            detail={"note": "No email available"},
            checked_at=now_iso,
        ))

    # 5. Website Verification
    web_target = entity.website_url or entity.website_domain
    if web_target:
        w_res = await verify_website(web_target, business_name=entity.canonical_name)
        checks.append(CheckResult(
            check_name="website_accessible",
            outcome="passed" if w_res["live"] else "failed",
            detail=w_res,
            checked_at=now_iso,
        ))
    else:
        checks.append(CheckResult(
            check_name="website_accessible",
            outcome="inconclusive",
            detail={"note": "No website discovered"},
            checked_at=now_iso,
        ))

    # 6. Operating status check
    status_lower = (entity.operating_status or "open").lower()
    if any(s in status_lower for s in ["closed", "disused", "permanently_closed", "was:"]):
        checks.append(CheckResult(
            check_name="operating_status_open",
            outcome="failed",
            detail={"status": entity.operating_status},
            checked_at=now_iso,
        ))
    else:
        checks.append(CheckResult(
            check_name="operating_status_open",
            outcome="passed",
            detail={"status": entity.operating_status or "open"},
            checked_at=now_iso,
        ))

    raw_addr_text = (entity.address.get("freeform") or "") if isinstance(entity.address, dict) else str(entity.address or "")
    addr_text = (raw_addr_text or "").lower()
    loc_norm = (target_locality or "").lower().strip()
    has_loc = (loc_norm in addr_text) if loc_norm else True
    checks.append(CheckResult(
        check_name="address_complete",
        outcome="passed" if (has_loc and bool(entity.address)) else "inconclusive",
        detail={"address": entity.address, "mentions_locality": has_loc},
        checked_at=now_iso,
    ))

    return checks
