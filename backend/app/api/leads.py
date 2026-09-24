"""Leads API router — GET /api/leads, GET /api/leads/{id}, export, delivered, suppress."""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone
from typing import Any

import openpyxl
import structlog
from fastapi import APIRouter, HTTPException, Query, Response
from psycopg import sql
from pydantic import BaseModel
from app.api._leads_query import (
    BASE_FROM,
    DELIVERED_EXPR,
    SUPPRESSED_EXPR,
    LeadFilters,
    build_where,
)
from app.crawl.extract_structured import extract_page_data
from app.crawl.fetcher import fetch_page
from app.crawl.simhash import hamming_distance
from app.db.pool import get_conn
from app.relevance.concepts import resolve_concept
from app.relevance.engine import evaluate_candidate
from app.relevance.semantic import add_mined_exemplar
from app.resolve.geo_math import haversine_distance_m

log = structlog.get_logger()
router = APIRouter(tags=["leads"])


class LeadRow(BaseModel):
    id: str
    canonical_name: str
    primary_category: str | None = None
    phones_e164: list[str] = []
    emails: list[str] = []
    website_url: str | None = None
    website_domain: str | None = None
    address_text: str | None = None
    locality: str | None = None
    city: str | None = None
    state: str | None = None
    lon: float | None = None
    lat: float | None = None
    geohash7: str | None = None
    confidence: float | None = 0.0
    tier: str | None = "Unverified"
    independent_source_count: int | None = 1
    is_new_business: bool | None = True
    delivered: bool = False
    suppressed: bool = False
    rank: int | None = None
    distance_km: float | None = None
    decision: str | None = "accepted"
    relevance_p: float | None = None
    relevance_stage: str | None = None
    relevance_reasons: list[dict[str, Any]] = []
    relevance_features: dict[str, float] = {}
    reason_code: str | None = None
    source: str | None = None


class DecisionCounts(BaseModel):
    accepted: int = 0
    review: int = 0
    rejected: int = 0


class LeadsResponse(BaseModel):
    items: list[LeadRow]
    total: int
    counts: DecisionCounts
    next_cursor: int | None = None
    filters_applied: dict[str, Any] = {}



def _row_to_leadrow(r: Any, run_centroid: tuple[float, float] | None = None) -> LeadRow:
    d = dict(r)
    d["id"] = str(d.get("id"))
    for field in ["phones_e164", "emails", "categories"]:
        val = d.get(field)
        if isinstance(val, str):
            try:
                d[field] = json.loads(val)
            except Exception as e:
                log.warning(f"Could not parse field {field} JSON '{val}': {e}")
                d[field] = [val] if val.strip() else []
        elif val is None:
            d[field] = []

    # Relevance metadata parsing
    relevance_reasons: list[Any] = []
    reasons_raw = d.get("relevance_reasons")
    if reasons_raw:
        try:
            relevance_reasons = json.loads(reasons_raw) if isinstance(reasons_raw, str) else reasons_raw
        except Exception as e:
            log.warning(f"Could not parse relevance_reasons JSON: {e}")
            pass

    relevance_features: dict[str, Any] = {}
    features_raw = d.get("relevance_features")
    if features_raw:
        try:
            relevance_features = json.loads(features_raw) if isinstance(features_raw, str) else features_raw
        except Exception as e:
            log.warning(f"Could not parse relevance_features JSON: {e}")
            pass

    website_url = d.get("website_url")
    website_domain = None
    if website_url:
        import urllib.parse
        try:
            parsed = urllib.parse.urlparse(website_url)
            website_domain = parsed.netloc or parsed.path
        except Exception as e:
            log.warning(f"Could not parse website_url '{website_url}': {e}")
            website_domain = website_url

    lon_val = None
    lat_val = None
    if d.get("lon") is not None:
        try:
            lon_val = float(d["lon"])
        except (ValueError, TypeError) as e:
            log.warning(f"Could not parse lon '{d['lon']}': {e}")
            pass
    if d.get("lat") is not None:
        try:
            lat_val = float(d["lat"])
        except (ValueError, TypeError):
            pass

    if (lon_val is None or lat_val is None) and d.get("geom"):
        import re
        m = re.search(r"POINT\s*\(\s*([-\d.]+)\s+([-\d.]+)\s*\)", str(d["geom"]), re.IGNORECASE)
        if m:
            try:
                lon_val = float(m.group(1))
                lat_val = float(m.group(2))
            except Exception:
                pass

    distance_km = None
    if lon_val is not None and lat_val is not None and run_centroid and len(run_centroid) == 2:
        dist_m = haversine_distance_m(lon_val, lat_val, run_centroid[0], run_centroid[1])
        distance_km = round(dist_m / 1000.0, 2)

    rank_val = None
    if d.get("rank") is not None:
        try:
            rank_val = int(d["rank"])
        except (ValueError, TypeError):
            pass

    return LeadRow(
        id=d["id"] if d.get("id") is not None else "",
        canonical_name=d.get("canonical_name", d.get("name", "")),
        primary_category=d.get("primary_category"),
        phones_e164=d.get("phones_e164") or [],
        emails=d.get("emails") or [],
        website_url=website_url,
        website_domain=website_domain,
        address_text=d.get("address_text"),
        locality=d.get("locality"),
        city=d.get("city"),
        state=d.get("state"),
        lon=lon_val,
        lat=lat_val,
        geohash7=d.get("geohash7"),
        confidence=float(d.get("confidence") or 0.0),
        tier=d.get("tier") or "Unverified",
        independent_source_count=int(d.get("independent_source_count") or 1),
        is_new_business=bool(d.get("is_new_business", True)),
        delivered=bool(d.get("delivered", False)),
        suppressed=bool(d.get("suppressed", False)),
        rank=rank_val,
        distance_km=distance_km,
        decision=d.get("decision", "accepted"),
        relevance_p=float(d["relevance_p"]) if d.get("relevance_p") is not None else None,
        relevance_stage=d.get("relevance_stage"),
        relevance_reasons=relevance_reasons,
        relevance_features=relevance_features,
        reason_code=d.get("reason_code") or d.get("reason"),
        source=d.get("source"),
    )


@router.get("/runs/{run_id}/leads", response_model=LeadsResponse)
async def list_run_leads(
    run_id: str,
    decision: str = "accepted",
    tier: str | None = None,
    has_phone: bool | None = None,
    has_email: bool | None = None,
    new_only: bool = False,
    q: str | None = None,
    sort: str = "rank",
    cursor: int | None = None,
    limit: int = 100,
    include_delivered: bool = False,
    include_suppressed: bool = False,
) -> LeadsResponse:
    f = LeadFilters(
        run_id=run_id,
        decision=decision,
        tier=tier,
        has_phone=has_phone,
        has_email=has_email,
        new_only=new_only,
        q=q,
        cursor=cursor,
        include_delivered=include_delivered,
        include_suppressed=include_suppressed,
    )

    async with get_conn() as conn:
        # Grouped counts across decisions matching identical filters without decision
        where_counts, params_counts = build_where(f, include_decision=False)
        counts_sql = sql.SQL("""
            SELECT rr.decision, count(*) AS n
            {BASE_FROM}
            WHERE {where}
            GROUP BY rr.decision
        """).format(BASE_FROM=BASE_FROM, where=where_counts)
        counts_rows = await (await conn.execute(counts_sql, params_counts)).fetchall()
        grouped_counts: dict[str, int] = {r["decision"]: r["n"] for r in counts_rows if r.get("decision")}

        # Check rejected_candidates table for this run (for candidates rejected before persistence)
        rej_where_clauses = [sql.SQL("run_id = %s")]
        rej_params: list[Any] = [run_id]
        if q:
            rej_where_clauses.append(sql.SQL("name ILIKE %s"))
            rej_params.append(f"%{q.lower()}%")
        rej_where_sql = sql.SQL(" AND ").join(rej_where_clauses)

        rej_count_row = await (await conn.execute(
            sql.SQL("SELECT count(*) AS count FROM rejected_candidates WHERE {}").format(rej_where_sql),
            rej_params,
        )).fetchone()
        rej_cands_n = int(rej_count_row["count"]) if (rej_count_row and "count" in rej_count_row) else (list(rej_count_row.values())[0] if rej_count_row else 0)

        counts = DecisionCounts(
            accepted=grouped_counts.get("accepted", 0),
            review=grouped_counts.get("review", 0),
            rejected=grouped_counts.get("rejected", 0) + rej_cands_n,
        )

        # Get run centroid for distance calculation
        run_centroid = None
        run_row = await (await conn.execute(
            "SELECT stats FROM query_runs WHERE id = %s",
            (run_id,),
        )).fetchone()
        if run_row and run_row.get("stats"):
            try:
                stats_dict = json.loads(run_row["stats"]) if isinstance(run_row["stats"], str) else run_row["stats"]
                cent = stats_dict.get("geo", {}).get("centroid")
                if cent and len(cent) == 2:
                    run_centroid = (float(cent[0]), float(cent[1]))
            except Exception:
                pass

        items: list[LeadRow] = []

        if decision == "rejected":
            # 1. Fetch from rejected_candidates table
            rej_query = sql.SQL("""
                SELECT source_record_id AS id, run_id, source, source_record_id, name AS canonical_name,
                       reason, reason_code, relevance_p, features AS relevance_features
                FROM rejected_candidates
                WHERE {}
                ORDER BY name ASC
                LIMIT %s
            """).format(rej_where_sql)
            rej_rows = await (await conn.execute(rej_query, rej_params + [limit])).fetchall()
            for r in rej_rows:
                item = dict(r)
                item["decision"] = "rejected"
                item["tier"] = "Rejected"
                items.append(_row_to_leadrow(item))

            # 2. Also fetch any run_results marked rejected if space remains
            if len(items) < limit and grouped_counts.get("rejected", 0) > 0:
                where_rej, params_rej = build_where(f, include_decision=True)
                query_sql = sql.SQL("""
                    SELECT b.*, rr.is_new_business, rr.rank, rr.decision, rr.relevance_p,
                           rr.relevance_stage, rr.relevance_features, rr.relevance_reasons,
                           {DELIVERED_EXPR} AS delivered,
                           {SUPPRESSED_EXPR} AS suppressed
                    {BASE_FROM}
                    WHERE {where}
                    ORDER BY rr.rank ASC
                    LIMIT %s
                """).format(
                    DELIVERED_EXPR=DELIVERED_EXPR,
                    SUPPRESSED_EXPR=SUPPRESSED_EXPR,
                    BASE_FROM=BASE_FROM,
                    where=where_rej,
                )
                rem_limit = limit - len(items)
                rr_rows = await (await conn.execute(query_sql, params_rej + [rem_limit])).fetchall()
                for r in rr_rows:
                    items.append(_row_to_leadrow(r, run_centroid=run_centroid))

            total = counts.rejected

        elif decision in ("accepted", "review"):
            where_clause, params_list = build_where(f, include_decision=True)
            query_sql = sql.SQL("""
                SELECT b.*, rr.is_new_business, rr.rank, rr.decision, rr.relevance_p,
                       rr.relevance_stage, rr.relevance_features, rr.relevance_reasons,
                       {DELIVERED_EXPR} AS delivered,
                       {SUPPRESSED_EXPR} AS suppressed
                {BASE_FROM}
                WHERE {where}
                ORDER BY rr.rank ASC
                LIMIT %s
            """).format(
                DELIVERED_EXPR=DELIVERED_EXPR,
                SUPPRESSED_EXPR=SUPPRESSED_EXPR,
                BASE_FROM=BASE_FROM,
                where=where_clause,
            )
            rows = await (await conn.execute(query_sql, params_list + [limit])).fetchall()
            items = [_row_to_leadrow(r, run_centroid=run_centroid) for r in rows]
            total = counts.accepted if decision == "accepted" else counts.review

        else:
            # decision == 'all' or None
            where_clause, params_list = build_where(f, include_decision=False)
            query_sql = sql.SQL("""
                SELECT b.*, rr.is_new_business, rr.rank, rr.decision, rr.relevance_p,
                       rr.relevance_stage, rr.relevance_features, rr.relevance_reasons,
                       {DELIVERED_EXPR} AS delivered,
                       {SUPPRESSED_EXPR} AS suppressed
                {BASE_FROM}
                WHERE {where}
                ORDER BY rr.rank ASC
                LIMIT %s
            """).format(
                DELIVERED_EXPR=DELIVERED_EXPR,
                SUPPRESSED_EXPR=SUPPRESSED_EXPR,
                BASE_FROM=BASE_FROM,
                where=where_clause,
            )
            rows = await (await conn.execute(query_sql, params_list + [limit])).fetchall()
            items = [_row_to_leadrow(r, run_centroid=run_centroid) for r in rows]

            # If room in limit, also include rejected candidates
            if len(items) < limit and rej_cands_n > 0:
                rem_limit = limit - len(items)
                rej_query = sql.SQL("""
                    SELECT source_record_id AS id, run_id, source, source_record_id, name AS canonical_name,
                           reason, reason_code, relevance_p, features AS relevance_features
                    FROM rejected_candidates
                    WHERE {}
                    ORDER BY name ASC
                    LIMIT %s
                """).format(rej_where_sql)
                rej_rows = await (await conn.execute(rej_query, rej_params + [rem_limit])).fetchall()
                for r in rej_rows:
                    item = dict(r)
                    item["decision"] = "rejected"
                    item["tier"] = "Rejected"
                    items.append(_row_to_leadrow(item))

            total = counts.accepted + counts.review + counts.rejected

        next_cursor = items[-1].rank if (len(items) == limit and items and items[-1].rank is not None) else None

        return LeadsResponse(
            items=items,
            total=total,
            counts=counts,
            next_cursor=next_cursor,
            filters_applied={
                "run_id": run_id,
                "decision": decision,
                "tier": tier,
                "has_phone": has_phone,
                "has_email": has_email,
                "new_only": new_only,
                "q": q,
                "cursor": cursor,
                "limit": limit,
            },
        )


@router.get("/leads/{business_id}")
async def get_lead(business_id: str) -> dict[str, Any]:
    """Full lead detail: golden record + field provenance + verifications + sources."""
    async with get_conn() as conn:
        b = await (await conn.execute(
            "SELECT * FROM businesses WHERE id = %s", (business_id,)
        )).fetchone()
        if not b:
            raise HTTPException(status_code=404, detail="Lead not found")

        provenance = await (await conn.execute(
            "SELECT * FROM field_provenance WHERE business_id = %s ORDER BY field, is_selected DESC",
            (business_id,),
        )).fetchall()

        verifications = await (await conn.execute(
            "SELECT * FROM verifications WHERE business_id = %s", (business_id,)
        )).fetchall()

        sources = await (await conn.execute(
            "SELECT * FROM business_sources WHERE business_id = %s", (business_id,)
        )).fetchall()

        runs_appeared = await (await conn.execute(
            """
            SELECT qr.id, qr.created_at, qr.keywords, qr.locality, qr.city, rr.rank
            FROM run_results rr
            JOIN query_runs qr ON qr.id = rr.run_id
            WHERE rr.business_id = %s ORDER BY qr.created_at DESC LIMIT 10
            """,
            (business_id,),
        )).fetchall()

    return {
        "business": dict(b),
        "field_provenance": [dict(r) for r in provenance],
        "verifications": [dict(r) for r in verifications],
        "sources": [dict(r) for r in sources],
        "appeared_in_runs": [dict(r) for r in runs_appeared],
    }


@router.get("/runs/{run_id}/export/compliance")
async def get_export_compliance(
    run_id: str,
    decision: str = "accepted",
    include_delivered: bool = False,
    include_suppressed: bool = False,
) -> dict[str, Any]:
    """Return pre-export compliance metrics, personal mobile risk analysis, and DND notice."""
    f = LeadFilters(
        run_id=run_id,
        decision=decision,
        include_delivered=include_delivered,
        include_suppressed=include_suppressed,
    )
    where_clause, params = build_where(f, include_decision=(decision not in ("all", None)))

    async with get_conn() as conn:
        cur = await conn.execute(
            sql.SQL("""
                SELECT b.phones_e164, b.website_domain, b.website_url,
                       {SUPPRESSED_EXPR} AS is_suppressed
                {BASE_FROM}
                WHERE {where}
            """).format(
                SUPPRESSED_EXPR=SUPPRESSED_EXPR,
                BASE_FROM=BASE_FROM,
                where=where_clause,
            ),
            params,
        )
        leads = await cur.fetchall()

    total = len(leads)
    mobile_count = 0
    landline_count = 0
    suppressed_count = 0

    for l in leads:
        if l.get("is_suppressed"):
            suppressed_count += 1
        phones = l["phones_e164"] if isinstance(l["phones_e164"], list) else json.loads(l["phones_e164"]) if l["phones_e164"] else []
        for p in phones:
            clean_p = p.replace(" ", "").replace("-", "")
            if clean_p.startswith("+91") and len(clean_p) >= 13 and clean_p[3] in "6789":
                mobile_count += 1
            else:
                landline_count += 1

    return {
        "run_id": run_id,
        "decision": decision,
        "total_leads": total,
        "mobile_subscribers_count": mobile_count,
        "landlines_count": landline_count,
        "suppressed_count": suppressed_count,
        "dnd_notice": "Under TRAI TCCCPR & Indian DPDP Act §3(c)(ii), marketing calls to personal mobile subscriber lines require consent or documented B2B lawful basis.",
        "lawful_basis": "DPDP §3(c)(ii) publicly available business contact corroboration",
        "export_allowed": True,
    }


@router.get("/runs/{run_id}/export")
async def export_leads(
    run_id: str,
    format: str = Query(default="csv", pattern="^(csv|xlsx)$"),
    decision: str = "accepted",
    include_delivered: bool = False,
    include_suppressed: bool = False,
) -> Response:
    """Export leads as CSV or XLSX. Defaults to decision='accepted', excluding delivered and suppressed."""
    f = LeadFilters(
        run_id=run_id,
        decision=decision,
        include_delivered=include_delivered,
        include_suppressed=include_suppressed,
    )

    rows: list[dict[str, Any]] = []

    async with get_conn() as conn:
        if decision == "rejected":
            rej_sql = sql.SQL("""
                SELECT name AS canonical_name, '' AS primary_category,
                       ARRAY[]::text[] AS phones_e164, ARRAY[]::text[] AS emails,
                       '' AS website_url, '' AS address_text, '' AS locality,
                       '' AS city, '' AS state, relevance_p AS confidence,
                       'Rejected' AS tier, 1 AS independent_source_count,
                       false AS is_new_business, reason, reason_code
                FROM rejected_candidates
                WHERE run_id = %s
                ORDER BY name ASC
            """)
            r_rows = await (await conn.execute(rej_sql, [run_id])).fetchall()
            rows = [dict(r) for r in r_rows]

            # Also include any run_results marked rejected
            where_clause, params = build_where(f, include_decision=True)
            rr_sql = sql.SQL("""
                SELECT b.canonical_name, b.primary_category, b.phones_e164, b.emails,
                       b.website_url, b.address_text, b.locality, b.city, b.state,
                       b.confidence, b.tier, b.independent_source_count,
                       rr.is_new_business, rr.decision
                {BASE_FROM}
                WHERE {where}
                ORDER BY rr.rank ASC
            """).format(BASE_FROM=BASE_FROM, where=where_clause)
            rr_rows = await (await conn.execute(rr_sql, params)).fetchall()
            rows.extend([dict(r) for r in rr_rows])

        elif decision in ("accepted", "review"):
            where_clause, params = build_where(f, include_decision=True)
            export_sql = sql.SQL("""
                SELECT b.canonical_name, b.primary_category, b.phones_e164, b.emails,
                       b.website_url, b.address_text, b.locality, b.city, b.state,
                       b.confidence, b.tier, b.independent_source_count,
                       rr.is_new_business, rr.decision
                {BASE_FROM}
                WHERE {where}
                ORDER BY rr.rank ASC
            """).format(BASE_FROM=BASE_FROM, where=where_clause)
            db_rows = await (await conn.execute(export_sql, params)).fetchall()
            rows = [dict(r) for r in db_rows]

        else:
            # decision == 'all'
            where_clause, params = build_where(f, include_decision=False)
            export_sql = sql.SQL("""
                SELECT b.canonical_name, b.primary_category, b.phones_e164, b.emails,
                       b.website_url, b.address_text, b.locality, b.city, b.state,
                       b.confidence, b.tier, b.independent_source_count,
                       rr.is_new_business, rr.decision
                {BASE_FROM}
                WHERE {where}
                ORDER BY rr.rank ASC
            """).format(BASE_FROM=BASE_FROM, where=where_clause)
            db_rows = await (await conn.execute(export_sql, params)).fetchall()
            rows = [dict(r) for r in db_rows]

            # Append rejected candidates to complete 'all'
            rej_sql = sql.SQL("""
                SELECT name AS canonical_name, '' AS primary_category,
                       ARRAY[]::text[] AS phones_e164, ARRAY[]::text[] AS emails,
                       '' AS website_url, '' AS address_text, '' AS locality,
                       '' AS city, '' AS state, relevance_p AS confidence,
                       'Rejected' AS tier, 1 AS independent_source_count,
                       false AS is_new_business, reason, reason_code
                FROM rejected_candidates
                WHERE run_id = %s
                ORDER BY name ASC
            """)
            r_rows = await (await conn.execute(rej_sql, [run_id])).fetchall()
            rows.extend([dict(r) for r in r_rows])

    if format == "csv":
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=[
            "name", "category", "phones", "emails", "website",
            "address", "locality", "city", "state", "tier", "confidence",
            "independent_sources", "new_lead", "dnd_subscriber_risk", "compliance_basis",
        ])
        def parse_pg_array(val: Any) -> list[str]:
            """Parse a PostgreSQL array value, which may come as a Python list already,
            a JSON string '[...]', or a pg-literal string '{a,b,c}' or '{a}'."""
            if val is None:
                return []
            if isinstance(val, list):
                return [str(v) for v in val if v]
            s = str(val).strip()
            if s.startswith("["):
                try:
                    return [str(x) for x in json.loads(s) if x]
                except Exception:
                    pass
            if s.startswith("{") and s.endswith("}"):
                inner = s[1:-1]
                if not inner:
                    return []
                return [item.strip().strip('"') for item in inner.split(",") if item.strip()]
            return [s] if s else []

        writer.writeheader()
        for r in rows:
            phones: list[str] = parse_pg_array(r["phones_e164"])
            emails: list[str] = parse_pg_array(r["emails"])
            has_mobile = any(
                p.replace(" ", "").startswith("+91")
                and len(p.replace(" ", "")) >= 13
                and p.replace(" ", "")[3] in "6789"
                for p in phones
            )
            writer.writerow({
                "name": r["canonical_name"],
                "category": r["primary_category"] or "",
                "phones": "; ".join(phones),
                "emails": "; ".join(emails),
                "website": r["website_url"] or "",
                "address": r["address_text"] or "",
                "locality": r["locality"] or "",
                "city": r["city"] or "",
                "state": r["state"] or "",
                "tier": r["tier"] or "",
                "confidence": r["confidence"] or "",
                "independent_sources": r["independent_source_count"] or 0,
                "new_lead": r["is_new_business"],
                "dnd_subscriber_risk": "personal_mobile_line" if has_mobile else "business_landline",
                "compliance_basis": "DPDP_3_c_ii_public_source",
            })
        return Response(
            content=output.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=leads_{run_id[:8]}.csv"},
        )

    # XLSX
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Leads"
    headers = ["Name", "Category", "Phones", "Emails", "Website", "Address",
               "Locality", "City", "State", "Tier", "Confidence",
               "Independent Sources", "New Lead?", "DND Line Risk", "Compliance Basis"]
    ws.append(headers)
    for r in rows:
        phones: list[str] = parse_pg_array(r["phones_e164"])
        emails: list[str] = parse_pg_array(r["emails"])
        has_mobile = any(p.replace(" ", "").startswith("+91") and len(p.replace(" ", "")) >= 13 and p.replace(" ", "")[3] in "6789" for p in phones)
        ws.append([
            r["canonical_name"], r["primary_category"] or "",
            "; ".join(phones),
            "; ".join(emails),
            r["website_url"] or "", r["address_text"] or "",
            r["locality"] or "", r["city"] or "", r["state"] or "",
            r["tier"] or "", r["confidence"] or 0,
            r["independent_source_count"] or 0, r["is_new_business"],
            "Personal Mobile Line" if has_mobile else "Business Landline",
            "DPDP §3(c)(ii) Public Source",
        ])

    # Compliance worksheet
    comp = wb.create_sheet("Compliance & DND Notice")
    comp.append(["Regulation", "Scope", "Statutory Notice"])
    comp.append([
        "TRAI TCCCPR 2018",
        "Commercial Telecommunications",
        "Subscriber preference applies to personal connections regardless of business purpose. Consent or documented B2B lawful basis required.",
    ])
    comp.append([
        "DPDP Act 2023 §3(c)(ii)",
        "Publicly Available Data",
        "Processing of publicly available business contact details is permitted where made public by the data principal.",
    ])

    attr = wb.create_sheet("Attribution")
    attr.append(["Source", "Licence", "Attribution Text"])
    attr.append([
        "OpenStreetMap", "ODbL 1.0",
        "© OpenStreetMap contributors. Data from this file includes data from OpenStreetMap.",
    ])

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return Response(
        content=buf.read(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=leads_{run_id[:8]}.xlsx"},
    )


@router.post("/runs/{run_id}/relevance/relabel")
async def relabel_candidate(run_id: str, body: dict[str, Any]) -> dict[str, Any]:
    """Record human verdict on candidate -> writes gold_labels & concept_exemplars for hard-negative mining."""
    business_id = body.get("business_id")
    verdict = body.get("verdict", "valid")  # 'relevant' | 'not_relevant' | 'valid' | 'invalid'
    notes = body.get("notes")

    is_pos = verdict in ("relevant", "valid", "correct")
    polarity = 1 if is_pos else -1

    async with get_conn() as conn:
        # 1. Insert gold_labels
        await conn.execute(
            """
            INSERT INTO gold_labels (run_id, business_id, label_type, verdict, labeler)
            VALUES (%s, %s, 'lead_relevance', %s, 'human')
            """,
            (run_id, business_id, verdict),
        )

        # 2. Get business profile text for exemplar bank
        cur = await conn.execute(
            "SELECT canonical_name, primary_category, categories, website_domain FROM businesses WHERE id = %s",
            (business_id,),
        )
        brow = await cur.fetchone()
        biz_text = ""
        if brow:
            b_name = brow["canonical_name"] if isinstance(brow, dict) else brow[0]
            b_cat = brow["primary_category"] if isinstance(brow, dict) else brow[1]
            biz_text = f"{b_name} | category: {b_cat}"

        # 3. Get concept_id from run
        cur_run = await conn.execute("SELECT keywords FROM query_runs WHERE id = %s", (run_id,))
        rrow = await cur_run.fetchone()
        kw = "business"
        if rrow:
            kws = rrow["keywords"] if isinstance(rrow, dict) else rrow[0]
            if kws:
                kw = kws[0] if isinstance(kws, list) else str(kws)

        card = resolve_concept(kw)

        if biz_text:
            add_mined_exemplar(card.concept_id, biz_text, polarity)
            try:
                await conn.execute(
                    """
                    INSERT INTO concept_exemplars (concept_id, polarity, text, origin, source_business_id)
                    VALUES (%s, %s, %s, 'human_label', %s)
                    """,
                    (card.concept_id, polarity, biz_text, business_id),
                )
            except Exception:
                pass

        # 4. Update run_results decision
        new_decision = "accepted" if is_pos else "rejected"
        await conn.execute(
            """
            UPDATE run_results
            SET decision = %s
            WHERE run_id = %s AND business_id = %s
            """,
            (new_decision, run_id, business_id),
        )
        await conn.commit()

    return {"status": "ok", "business_id": business_id, "verdict": verdict, "decision": new_decision}


@router.post("/runs/{run_id}/rescore")
async def rescore_run(run_id: str) -> dict[str, Any]:
    """Re-evaluate stored candidates at the current ConceptCard version without re-fetching sources."""
    async with get_conn() as conn:
        # Get run info
        cur_run = await conn.execute("SELECT keywords FROM query_runs WHERE id = %s", (run_id,))
        rrow = await cur_run.fetchone()
        kw = "business"
        if rrow:
            kws = rrow["keywords"] if isinstance(rrow, dict) else rrow[0]
            if kws:
                kw = kws[0] if isinstance(kws, list) else str(kws)

        card = resolve_concept(kw)

        # Get all businesses in run_results
        cur_leads = await conn.execute(
            """
            SELECT b.id, b.canonical_name, b.primary_category, b.categories, b.website_domain,
                   ST_X(b.geom::geometry) AS lon, ST_Y(b.geom::geometry) AS lat
            FROM run_results rr
            JOIN businesses b ON b.id = rr.business_id
            WHERE rr.run_id = %s
            """,
            (run_id,),
        )
        leads = await cur_leads.fetchall()

        rescored_count = 0
        acc_count = 0
        rev_count = 0
        rej_count = 0

        for lead in leads:
            b_id = str(lead["id"]) if isinstance(lead, dict) else str(lead[0])
            b_name = lead["canonical_name"] if isinstance(lead, dict) else lead[1]
            b_cats = lead["categories"] if isinstance(lead, dict) else lead[3]
            if isinstance(b_cats, str):
                try:
                    b_cats = json.loads(b_cats)
                except Exception as e:
                    log.warning(f"Could not parse categories JSON '{b_cats}': {e}")
                    b_cats = [b_cats]
            b_lon = float(lead["lon"]) if (isinstance(lead, dict) and lead.get("lon") is not None) else 77.75
            b_lat = float(lead["lat"]) if (isinstance(lead, dict) and lead.get("lat") is not None) else 12.97

            dec = await evaluate_candidate(
                name=b_name,
                keyword=kw,
                lon=b_lon,
                lat=b_lat,
                categories=b_cats,
                card=card,
            )

            rescored_count += 1
            if dec.outcome == "accepted":
                acc_count += 1
            elif dec.outcome == "review":
                rev_count += 1
            else:
                rej_count += 1

            await conn.execute(
                """
                UPDATE run_results SET
                    decision = %s,
                    relevance_p = %s,
                    relevance_stage = %s,
                    relevance_features = %s,
                    relevance_reasons = %s,
                    concept_id = %s,
                    concept_version = %s,
                    scorer_version = %s
                WHERE run_id = %s AND business_id = %s
                """,
                (
                    dec.outcome,
                    dec.p,
                    dec.stage,
                    json.dumps(dec.features),
                    json.dumps(dec.reasons),
                    dec.concept_id,
                    dec.concept_version,
                    dec.scorer_version,
                    run_id,
                    b_id,
                ),
            )
        await conn.commit()

    return {
        "run_id": run_id,
        "rescored_count": rescored_count,
        "accepted": acc_count,
        "review": rev_count,
        "rejected": rej_count,
        "concept_id": card.concept_id,
        "concept_version": card.version,
    }



@router.post("/leads/{business_id}/suppress")
async def suppress_lead(business_id: str, body: dict[str, Any]) -> dict[str, str]:
    async with get_conn() as conn:
        b = await (await conn.execute(
            "SELECT phones_e164, emails, website_domain FROM businesses WHERE id = %s",
            (business_id,),
        )).fetchone()
        if not b:
            raise HTTPException(status_code=404, detail="Lead not found")

        reason = body.get("reason", "user_requested")
        phones = b["phones_e164"] if isinstance(b["phones_e164"], list) else json.loads(b["phones_e164"]) if b["phones_e164"] else []
        for phone in phones:
            await conn.execute(
                "INSERT INTO suppression_list (phone_e164, reason) VALUES (%s, %s)",
                (phone, reason),
            )
        if b["website_domain"]:
            await conn.execute(
                "INSERT INTO suppression_list (domain, reason) VALUES (%s, %s)",
                (b["website_domain"], reason),
            )
        await conn.commit()
    return {"suppressed": business_id}


@router.post("/leads/reverify")
async def reverify_leads(body: dict[str, Any] = {}) -> dict[str, Any]:
    """
    POST /api/leads/reverify
    Incremental re-verification of leads using HTTP 304 conditional fetches,
    Simhash drift detection, and automated field refreshing.
    """
    lead_ids = body.get("lead_ids", [])
    max_count = int(body.get("limit", 50))

    async with get_conn() as conn:
        if lead_ids:
            cur = await conn.execute(
                "SELECT id, canonical_name, website_url, website_domain FROM businesses WHERE id = ANY(%s) AND website_url IS NOT NULL LIMIT %s",
                (lead_ids, max_count),
            )
        else:
            cur = await conn.execute(
                "SELECT id, canonical_name, website_url, website_domain FROM businesses WHERE website_url IS NOT NULL ORDER BY last_verified_at ASC NULLS FIRST LIMIT %s",
                (max_count,),
            )
        leads = await cur.fetchall()

        results: dict[str, Any] = {
            "total_processed": len(leads),
            "not_modified_304": 0,
            "simhash_unchanged": 0,
            "re_extracted_substantive": 0,
            "failed_or_blocked": 0,
            "leads": [],
        }

        for lead in leads:
            b_id = str(lead["id"])
            url = lead["website_url"]
            name = lead["canonical_name"]

            # Check crawl_log for last etag and simhash
            log_cur = await conn.execute(
                "SELECT etag, last_modified, simhash FROM crawl_log WHERE url = %s ORDER BY fetched_at DESC LIMIT 1",
                (url,),
            )
            prev_crawl = await log_cur.fetchone()
            etag = prev_crawl.get("etag") if prev_crawl else None
            last_mod = prev_crawl.get("last_modified") if prev_crawl else None
            prev_simhash = int(prev_crawl.get("simhash", 0)) if prev_crawl and prev_crawl.get("simhash") else 0

            fetch_res = await fetch_page(url, if_none_match=etag, if_modified_since=last_mod)

            # Record in crawl_log
            await conn.execute(
                """
                INSERT INTO crawl_log (domain, url, http_status, outcome, robots_allowed, etag, last_modified, simhash, fetched_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
                """,
                (
                    lead["website_domain"] or url,
                    url,
                    fetch_res.status_code,
                    fetch_res.outcome,
                    True,
                    fetch_res.etag,
                    fetch_res.last_modified,
                    fetch_res.simhash,
                ),
            )

            status = "failed"
            if fetch_res.status_code == 304 or fetch_res.outcome == "304_not_modified":
                results["not_modified_304"] += 1
                status = "304_not_modified"
                await conn.execute("UPDATE businesses SET last_verified_at = NOW() WHERE id = %s", (b_id,))
            elif fetch_res.status_code == 200:
                dist = hamming_distance(prev_simhash, fetch_res.simhash) if prev_simhash else 0
                if prev_simhash and dist <= 3:
                    results["simhash_unchanged"] += 1
                    status = f"simhash_unchanged (dist={dist})"
                    await conn.execute("UPDATE businesses SET last_verified_at = NOW() WHERE id = %s", (b_id,))
                else:
                    results["re_extracted_substantive"] += 1
                    status = f"re_extracted (dist={dist})"
                    # Re-extract structured details
                    ext_data = extract_page_data(fetch_res.html, url)
                    update_phones = ext_data["phones_e164"]
                    update_emails = ext_data["emails"]
                    if update_phones or update_emails:
                        await conn.execute(
                            """
                            UPDATE businesses SET
                                phones_e164 = array_cat(phones_e164, %s),
                                emails = array_cat(emails, %s),
                                last_verified_at = NOW()
                            WHERE id = %s
                            """,
                            (update_phones, update_emails, b_id),
                        )
                    else:
                        await conn.execute("UPDATE businesses SET last_verified_at = NOW() WHERE id = %s", (b_id,))
            else:
                results["failed_or_blocked"] += 1
                status = f"fetch_error ({fetch_res.outcome})"

            results["leads"].append({"id": b_id, "name": name, "url": url, "status": status})

        await conn.commit()

    return results

