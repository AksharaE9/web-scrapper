"""
app/api/_leads_query.py — Single source of truth query builder for leads (§2.1).

Ensures list, count, export, and compliance endpoints share identical WHERE semantics.
Uses EXISTS subqueries instead of LEFT JOIN to prevent row multiplication on boolean flags.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from psycopg import sql


@dataclass(frozen=True)
class LeadFilters:
    run_id: str
    decision: str | None = None          # None = ALL decisions, 'accepted' | 'review' | 'rejected' | 'all'
    tier: str | None = None
    has_phone: bool | None = None
    has_email: bool | None = None
    new_only: bool = False
    q: str | None = None
    cursor: int | None = None
    include_delivered: bool = False
    include_suppressed: bool = False


BASE_FROM = sql.SQL("""
    FROM run_results rr
    JOIN businesses b ON b.id = rr.business_id
""")

# EXISTS, not LEFT JOIN — a boolean flag must never multiply rows
DELIVERED_EXPR = sql.SQL("EXISTS (SELECT 1 FROM delivered_leads dl WHERE dl.business_id = b.id)")
SUPPRESSED_EXPR = sql.SQL("""EXISTS (
    SELECT 1 FROM suppression_list sl
     WHERE (sl.phone_e164 IS NOT NULL AND sl.phone_e164 = ANY(b.phones_e164))
        OR (sl.domain     IS NOT NULL AND sl.domain     = b.website_domain)
        OR (sl.email      IS NOT NULL AND sl.email      = ANY(b.emails))
)""")


def build_where(f: LeadFilters, include_decision: bool = True) -> tuple[sql.Composable, list[Any]]:
    """
    Build where clause and parameter list from LeadFilters.
    If include_decision is False, the decision filter is omitted (used for grouped tab counts).
    """
    conds: list[sql.Composable] = [sql.SQL("rr.run_id = %s")]
    params: list[Any] = [f.run_id]

    if include_decision and f.decision is not None and f.decision != "all":
        conds.append(sql.SQL("rr.decision = %s"))
        params.append(f.decision)

    if f.tier:
        conds.append(sql.SQL("b.tier = %s"))
        params.append(f.tier)

    if f.has_phone is True:
        conds.append(sql.SQL("COALESCE(array_length(b.phones_e164, 1), 0) > 0"))

    if f.has_email is True:
        conds.append(sql.SQL("COALESCE(array_length(b.emails, 1), 0) > 0"))

    if f.new_only:
        conds.append(sql.SQL("rr.is_new_business = true"))

    if f.q:
        conds.append(sql.SQL("b.name_norm ILIKE %s"))
        params.append(f"%{f.q.lower()}%")

    if f.cursor:
        conds.append(sql.SQL("rr.rank > %s"))
        params.append(f.cursor)

    if not f.include_delivered:
        conds.append(sql.SQL("NOT ") + DELIVERED_EXPR)

    if not f.include_suppressed:
        conds.append(sql.SQL("NOT ") + SUPPRESSED_EXPR)

    return sql.SQL(" AND ").join(conds), params
