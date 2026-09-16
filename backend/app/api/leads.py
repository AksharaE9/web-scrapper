"""Leads API router — GET /api/leads, GET /api/leads/{id}, export, delivered, suppress."""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone
from typing import Any

import openpyxl
from fastapi import APIRouter, HTTPException, Query, Response
from psycopg import sql
from pydantic import BaseModel

from app.db.pool import get_conn

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


def _row_to_leadrow(r: Any, run_centroid: tuple[float, float] | None = None) -> LeadRow:
    d = dict(r)
    d["id"] = str(d.get("id"))
    for field in ["phones_e164", "emails", "categories"]:
        val = d.get(field)
        if isinstance(val, str):
            try:
                d[field] = json.loads(val)
            except Exception:
                d[field] = [val] if val.strip() else []
        elif val is None:
            d[field] = []

    website_url = d.get("website_url")
    website_domain = None
    if website_url:
        import urllib.parse
        try:
            parsed = urllib.parse.urlparse(website_url)
            website_domain = parsed.netloc or parsed.path
        except Exception:
            website_domain = website_url

    lon_val = None
    lat_val = None
    if d.get("lon") is not None:
        try:
            lon_val = float(d["lon"])
        except (ValueError, TypeError):
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
        from app.graph.nodes.n1_geo import haversine_distance_m
        dist_m = haversine_distance_m(lon_val, lat_val, run_centroid[0], run_centroid[1])
        distance_km = round(dist_m / 1000.0, 2)

    rank_val = None
    if d.get("rank") is not None:
        try:
            rank_val = int(d["rank"])
        except (ValueError, TypeError):
            pass

    return LeadRow(
        id=str(d.get("id")),
        canonical_name=d.get("canonical_name", ""),
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
    )


@router.get("/runs/{run_id}/leads", response_model=list[LeadRow])
async def list_run_leads(
    run_id: str,
    tier: str | None = None,
    has_phone: bool | None = None,
    has_email: bool | None = None,
    new_only: bool = False,
    q: str | None = None,
    sort: str = "rank",
    cursor: int | None = None,
    limit: int = 100,
) -> list[LeadRow]:
    conditions: list[sql.Composable] = [sql.SQL("rr.run_id = %s")]
    params: list[Any] = [run_id]

    if tier:
        conditions.append(sql.SQL("b.tier = %s"))
        params.append(tier)
    if has_phone is True:
        conditions.append(sql.SQL("array_length(b.phones_e164, 1) > 0"))
    if has_email is True:
        conditions.append(sql.SQL("array_length(b.emails, 1) > 0"))
    if new_only:
        conditions.append(sql.SQL("rr.is_new_business = true"))
    if q:
        conditions.append(sql.SQL("b.name_norm ILIKE %s"))
        params.append(f"%{q.lower()}%")
    if cursor:
        conditions.append(sql.SQL("rr.rank > %s"))
        params.append(cursor)

    where = sql.SQL(" AND ").join(conditions)
    params.append(limit)

    run_centroid = None
    async with get_conn() as conn:
        run_row = await (await conn.execute(
            "SELECT locality, city, state, country, boundary, stats FROM query_runs WHERE id = %s",
            (run_id,)
        )).fetchone()
        if run_row:
            stats_raw = run_row.get("stats")
            if stats_raw:
                try:
                    stats_dict = json.loads(stats_raw) if isinstance(stats_raw, str) else stats_raw
                    cent = stats_dict.get("geo", {}).get("centroid")
                    if cent and len(cent) == 2:
                        run_centroid = (float(cent[0]), float(cent[1]))
                except Exception:
                    pass

            if not run_centroid:
                # Fast heuristic centroids for known top cities/localities if stats empty
                loc_lower = (run_row.get("locality") or "").lower()
                city_lower = (run_row.get("city") or "").lower()
                if "irram" in loc_lower or "errum" in loc_lower:
                    run_centroid = (78.456101, 17.4205559)
                elif "koramangala" in loc_lower:
                    run_centroid = (77.624081, 12.9357366)
                elif "madhapur" in loc_lower:
                    run_centroid = (78.3916304, 17.4408924)
                elif "hyderabad" in city_lower:
                    run_centroid = (78.4740613, 17.360589)
                elif "bengaluru" in city_lower or "bangalore" in city_lower:
                    run_centroid = (77.5945627, 12.9715987)

        query_sql = sql.SQL(
            """
            SELECT b.*, rr.is_new_business, rr.rank,
                   (dl.business_id IS NOT NULL) AS delivered,
                   (sl.id IS NOT NULL) AS suppressed
            FROM run_results rr
            JOIN businesses b ON b.id = rr.business_id
            LEFT JOIN delivered_leads dl ON dl.business_id = b.id
            LEFT JOIN suppression_list sl ON (
                sl.phone_e164 = ANY(b.phones_e164) OR
                sl.domain = b.website_domain
            )
            WHERE {}
            ORDER BY rr.rank ASC
            LIMIT %s
            """
        ).format(where)
        rows = await (await conn.execute(query_sql, params)).fetchall()

    return [_row_to_leadrow(r, run_centroid=run_centroid) for r in rows]


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


@router.get("/runs/{run_id}/export")
async def export_leads(
    run_id: str,
    format: str = Query(default="csv", pattern="^(csv|xlsx)$"),
    include_delivered: bool = False,
) -> Response:
    """Export leads as CSV or XLSX. Excludes delivered and suppressed leads by default."""
    conditions: list[sql.Composable] = [sql.SQL("rr.run_id = %s")]
    params: list[Any] = [run_id]

    if not include_delivered:
        conditions.append(sql.SQL("dl.business_id IS NULL"))
        conditions.append(sql.SQL("sl.id IS NULL"))

    where = sql.SQL(" AND ").join(conditions)

    async with get_conn() as conn:
        export_sql = sql.SQL(
            """
            SELECT b.canonical_name, b.primary_category, b.phones_e164, b.emails,
                   b.website_url, b.address_text, b.locality, b.city, b.state,
                   b.confidence, b.tier, b.independent_source_count,
                   rr.is_new_business
            FROM run_results rr
            JOIN businesses b ON b.id = rr.business_id
            LEFT JOIN delivered_leads dl ON dl.business_id = b.id
            LEFT JOIN suppression_list sl ON (
                sl.phone_e164 = ANY(b.phones_e164) OR
                sl.domain = b.website_domain
            )
            WHERE {}
            ORDER BY rr.rank ASC
            """
        ).format(where)
        rows = await (await conn.execute(export_sql, params)).fetchall()

    if format == "csv":
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=[
            "name", "category", "phones", "emails", "website",
            "address", "locality", "city", "state", "tier", "confidence",
            "independent_sources", "new_lead",
        ])
        writer.writeheader()
        for r in rows:
            phones = r["phones_e164"] if isinstance(r["phones_e164"], list) else json.loads(r["phones_e164"]) if r["phones_e164"] else []
            emails = r["emails"] if isinstance(r["emails"], list) else json.loads(r["emails"]) if r["emails"] else []
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
               "Independent Sources", "New Lead?"]
    ws.append(headers)
    for r in rows:
        phones = r["phones_e164"] if isinstance(r["phones_e164"], list) else json.loads(r["phones_e164"]) if r["phones_e164"] else []
        emails = r["emails"] if isinstance(r["emails"], list) else json.loads(r["emails"]) if r["emails"] else []
        ws.append([
            r["canonical_name"], r["primary_category"] or "",
            "; ".join(phones),
            "; ".join(emails),
            r["website_url"] or "", r["address_text"] or "",
            r["locality"] or "", r["city"] or "", r["state"] or "",
            r["tier"] or "", r["confidence"] or 0,
            r["independent_source_count"] or 0, r["is_new_business"],
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


@router.post("/leads/delivered")
async def mark_delivered(body: dict[str, Any]) -> dict[str, Any]:
    business_ids: list[str] = body.get("business_ids", [])
    channel: str = body.get("channel", "export")
    batch_ref: str = body.get("batch_ref", "")
    now = datetime.now(timezone.utc)

    async with get_conn() as conn:
        for bid in business_ids:
            await conn.execute(
                """
                INSERT INTO delivered_leads (business_id, delivered_at, channel)
                VALUES (%s, %s, %s)
                """,
                (bid, now.isoformat(), channel),
            )
        await conn.commit()
    return {"marked": len(business_ids)}


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
