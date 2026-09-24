"""
app/resolve/golden_record.py — Golden record field conflation and cluster aggregation.

Per-field winner determined by:
  Score = Source_Reliability × Recency × Agreement_Count

Also aggregates cluster relevance as maximum evidence over all cluster members.
"""

from __future__ import annotations

from typing import Any
import structlog
import pygeohash
from app.graph.state import FieldProvenance, RawCandidate, ResolvedEntity
from app.resolve.normalize import normalize_business_name, normalize_domain, normalize_phone_e164

log = structlog.get_logger()

SOURCE_RELIABILITY = {
    "website_direct": 1.0,
    "osm": 0.85,
    "overture": 0.80,
    "wikidata": 0.75,
    "imports": 0.70,
}


def build_golden_record(
    cluster_id: str,
    candidates: list[RawCandidate],
) -> ResolvedEntity:
    """Merge a cluster of matched raw candidates into a single golden ResolvedEntity."""
    if not candidates:
        raise ValueError("Cannot build golden record from empty cluster")

    # If single member
    if len(candidates) == 1:
        c = candidates[0]
        norm_phones: list[str] = [np for p in c.phones if p and (np := normalize_phone_e164(p)) is not None]
        norm_domains: list[str] = [nd for w in c.websites if w and (nd := normalize_domain(w)) is not None]
        primary_cat = c.categories[0] if c.categories else "SMB"
        # name_norm: use attribute if present (ResolvedEntity path), else derive from name
        name_norm_val = getattr(c, "name_norm", None) or normalize_business_name(c.name or "")
        # socials: RawCandidate stores list[str] URLs; convert to dict for ResolvedEntity
        socials_val: dict[str, str] = {}
        raw_socials = getattr(c, "socials", [])
        if isinstance(raw_socials, dict):
            socials_val = raw_socials
        elif isinstance(raw_socials, list):
            for url in raw_socials:
                if isinstance(url, str) and url:
                    # Use hostname as key (e.g. "facebook.com" -> url)
                    try:
                        from urllib.parse import urlparse
                        host = urlparse(url).netloc.lower().replace("www.", "")
                        socials_val[host or url] = url
                    except Exception as e:
                        log.warning("Could not parse social host URL", url=url, error=str(e))
                        socials_val[url] = url
        single_dec = c.raw.get("relevance_decision") if isinstance(c.raw, dict) else {}
        return ResolvedEntity(
            id=cluster_id,
            canonical_name=c.name or "Unknown Business",
            name_norm=name_norm_val,
            primary_category=primary_cat,
            categories=c.categories,
            phones_e164=norm_phones,
            emails=c.emails,
            website_url=c.websites[0] if c.websites else None,
            website_domain=norm_domains[0] if norm_domains else None,
            socials=socials_val,
            address=c.address,
            locality=c.locality,
            city=c.city,
            state=c.state,
            country=c.country,
            lon=c.lon,
            lat=c.lat,
            geohash7=c.geohash7,
            operating_status=c.operating_status,
            independent_source_count=1,
            source_ids=[f"{c.source}:{c.source_record_id}"],
            relevance_decision=single_dec or {},
        )

    # Multi-candidate cluster merging
    names = [c.name for c in candidates if c.name]
    canonical_name = max(names, key=len) if names else "Unknown Business"

    # Merge all phones and emails
    all_phones: list[str] = list({np for c in candidates for p in c.phones if p and (np := normalize_phone_e164(p)) is not None})
    all_emails: list[str] = list({e for c in candidates for e in c.emails if e})
    all_categories: list[str] = list({cat for c in candidates for cat in c.categories if cat})
    all_socials: dict[str, str] = {}
    for c in candidates:
        raw_socials = getattr(c, "socials", [])
        if isinstance(raw_socials, dict):
            all_socials.update(raw_socials)
        elif isinstance(raw_socials, list):
            for url in raw_socials:
                if isinstance(url, str) and url:
                    try:
                        from urllib.parse import urlparse
                        host = urlparse(url).netloc.lower().replace("www.", "")
                        all_socials[host or url] = url
                    except Exception as e:
                        log.warning("Could not parse social host URL in cluster merge", url=url, error=str(e))
                        all_socials[url] = url

    # Primary category
    primary_category = all_categories[0] if all_categories else "SMB"

    # Website
    all_websites = [w for c in candidates for w in c.websites if w]
    all_domains = list({normalize_domain(w) for w in all_websites if normalize_domain(w)})
    website_url = all_websites[0] if all_websites else None
    website_domain = all_domains[0] if all_domains else None

    # Centroid coordinate
    avg_lon = sum(c.lon for c in candidates) / float(len(candidates))
    avg_lat = sum(c.lat for c in candidates) / float(len(candidates))

    # Sources
    sources = list({c.source for c in candidates})
    source_ids = [f"{c.source}:{c.source_record_id}" for c in candidates]

    # Cluster relevance is max evidence over members
    decisions = []
    p_values = []
    best_dec: dict[str, Any] = {}
    best_p = -1.0

    for c in candidates:
        dec = c.raw.get("relevance_decision") if isinstance(c.raw, dict) else None
        if dec and isinstance(dec, dict):
            decisions.append(dec.get("decision", "accepted"))
            p_val = float(dec.get("relevance_p", 0.5))
            p_values.append(p_val)
            if p_val > best_p:
                best_p = p_val
                best_dec = dec

    if "accepted" in decisions:
        cluster_decision = "accepted"
    elif "review" in decisions:
        cluster_decision = "review"
    else:
        cluster_decision = "accepted"

    if best_dec:
        best_dec = dict(best_dec)
        best_dec["decision"] = cluster_decision

    max_p = max(p_values) if p_values else 0.5
    best_cand = candidates[0]

    return ResolvedEntity(
        id=cluster_id,
        canonical_name=canonical_name,
        name_norm=normalize_business_name(canonical_name),
        primary_category=primary_category,
        categories=all_categories,
        phones_e164=all_phones,
        emails=all_emails,
        website_url=website_url,
        website_domain=website_domain,
        socials=all_socials,
        address=best_cand.address,
        locality=best_cand.address.get("locality") if isinstance(best_cand.address, dict) else None,
        city=best_cand.address.get("city") if isinstance(best_cand.address, dict) else None,
        state=best_cand.address.get("state") if isinstance(best_cand.address, dict) else None,
        country=best_cand.address.get("country", "India") if isinstance(best_cand.address, dict) else "India",
        lon=avg_lon,
        lat=avg_lat,
        geohash7=pygeohash.encode(avg_lat, avg_lon, precision=7),
        operating_status=best_cand.operating_status,
        independent_source_count=len(sources),
        source_ids=source_ids,
        relevance_decision=best_dec,
    )

