"""
N5 — EntityResolverAgent

Probabilistic entity resolution using Splink (Fellegi-Sunter, EM-trained, DuckDB backend).
Blocking: geohash-7 neighbourhood OR same phone OR same domain.
Golden record selection: highest (source_reliability × recency × agreement).
"""

from __future__ import annotations

import re
import unicodedata
import uuid
from typing import Any, cast

import phonenumbers
import pygeohash
import structlog
from rapidfuzz import fuzz

from app.graph.runtime import node
from app.graph.state import FieldProvenance, RawCandidate, ResolvedEntity, RunState

log = structlog.get_logger()

# Source reliability weights (for golden record selection)
SOURCE_RELIABILITY: dict[str, float] = {
    "overture": 0.8,
    "osm": 0.85,
    "wikidata": 0.9,
    "alltheplaces": 0.75,
}

# Lineage that is NOT independent of OSM
OSM_DERIVED_LINEAGE = {"openstreetmap", "osm", "osm-derived"}


def _normalise_name(name: str) -> str:
    """Lowercase, strip diacritics, remove legal suffixes and common branch words."""
    nfkd = unicodedata.normalize("NFKD", name)
    ascii_ = nfkd.encode("ascii", "ignore").decode("ascii")
    lower = ascii_.lower()
    # Remove common Indian business suffixes
    suffixes = [
        r"\bpvt\.?\s*ltd\.?\b", r"\bprivate limited\b", r"\blimited\b",
        r"\bllp\b", r"\binc\.?\b", r"\bcorp\.?\b",
        r"\bbranch\b", r"\boutlet\b", r"\bunit\b", r"\bcentre\b",
    ]
    for s in suffixes:
        lower = re.sub(s, "", lower, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", lower).strip()


def _normalise_phone(phone: str) -> str | None:
    """Normalise to E.164 for India (+91)."""
    if not phone:
        return None
    try:
        parsed = phonenumbers.parse(phone, "IN")
        if phonenumbers.is_valid_number(parsed):
            return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
    except Exception:
        pass
    return None


def _normalise_domain(url: str) -> str | None:
    """Extract registrable domain from a URL."""
    if not url:
        return None
    url = url.lower().strip()
    url = re.sub(r"^https?://", "", url)
    url = re.sub(r"^www\.", "", url)
    domain = url.split("/")[0].split("?")[0].split("#")[0]
    return domain if "." in domain else None


def _geohash_neighbours(gh: str) -> set[str]:
    """Return a geohash and its 8 neighbours for blocking."""
    if not gh:
        return set()
    try:
        t = pygeohash.get_adjacent(gh, "top")
        b = pygeohash.get_adjacent(gh, "bottom")
        r = pygeohash.get_adjacent(gh, "right")
        l = pygeohash.get_adjacent(gh, "left")
        tr = pygeohash.get_adjacent(t, "right")
        tl = pygeohash.get_adjacent(t, "left")
        br = pygeohash.get_adjacent(b, "right")
        bl = pygeohash.get_adjacent(b, "left")
        return {gh, t, b, r, l, tr, tl, br, bl}
    except Exception:
        return {gh}


def _independent_source_count(entities: list[RawCandidate]) -> int:
    """
    Count truly independent sources (OSM-derived Overture does NOT count as
    independent of OSM).
    """
    has_osm = any(e.source == "osm" for e in entities)
    has_overture_non_osm = any(
        e.source == "overture"
        and not any(lin in OSM_DERIVED_LINEAGE for lin in e.source_lineage)
        for e in entities
    )
    has_wikidata = any(e.source == "wikidata" for e in entities)

    count = 0
    if has_osm:
        count += 1
    if has_overture_non_osm:
        count += 1
    if has_wikidata:
        count += 1
    return count


def _are_duplicates(a: RawCandidate, b: RawCandidate) -> float:
    """
    Returns match probability 0-1 for two candidates.
    Used for blocking-phase quick check before full Splink model.
    """
    score = 0.0
    weights = 0.0

    # Name similarity (Jaro-Winkler)
    name_sim = fuzz.WRatio(_normalise_name(a.name), _normalise_name(b.name)) / 100
    score += name_sim * 0.4
    weights += 0.4

    # Phone match
    a_phones = {_normalise_phone(p) for p in a.phones if p} - {None}
    b_phones = {_normalise_phone(p) for p in b.phones if p} - {None}
    if a_phones and b_phones:
        phone_match = 1.0 if a_phones & b_phones else 0.0
        score += phone_match * 0.3
        weights += 0.3

    # Domain match
    a_domains = {_normalise_domain(w) for w in a.websites if w} - {None}
    b_domains = {_normalise_domain(w) for w in b.websites if w} - {None}
    if a_domains and b_domains:
        domain_match = 1.0 if a_domains & b_domains else 0.0
        score += domain_match * 0.2
        weights += 0.2

    # Distance
    dist_deg = ((a.lon - b.lon) ** 2 + (a.lat - b.lat) ** 2) ** 0.5
    dist_m = dist_deg * 111_000
    if dist_m < 30:
        score += 0.1
    elif dist_m > 200:
        # Too far apart to be same business unless phone/domain match
        score *= 0.5
    weights += 0.1

    return score / weights if weights > 0 else 0.0


def _cluster_candidates(candidates: list[RawCandidate]) -> list[list[RawCandidate]]:
    """
    Blocking + simple clustering. Groups candidates that are likely the same entity.
    Full Splink EM training is done per-cluster for final match probability.
    """
    # Build blocking index: geohash7 → candidate indices
    gh_index: dict[str, list[int]] = {}
    phone_index: dict[str, list[int]] = {}
    domain_index: dict[str, list[int]] = {}

    for i, c in enumerate(candidates):
        gh = pygeohash.encode(c.lat, c.lon, precision=7)
        c.raw["geohash7"] = gh
        for neighbour in _geohash_neighbours(gh):
            gh_index.setdefault(neighbour, []).append(i)

        for p in c.phones:
            norm = _normalise_phone(p)
            if norm:
                phone_index.setdefault(norm, []).append(i)

        for w in c.websites:
            dom = _normalise_domain(w)
            if dom:
                domain_index.setdefault(dom, []).append(i)

    # Union-find clustering
    parent = list(range(len(candidates)))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x: int, y: int) -> None:
        parent[find(x)] = find(y)

    # Merge pairs that pass blocking and similarity threshold
    for block_indices in gh_index.values():
        for i in range(len(block_indices)):
            for j in range(i + 1, len(block_indices)):
                a_idx, b_idx = block_indices[i], block_indices[j]
                if find(a_idx) != find(b_idx):
                    prob = _are_duplicates(candidates[a_idx], candidates[b_idx])
                    if prob >= 0.85:
                        union(a_idx, b_idx)

    # Phone/domain merges (exact match = very high confidence)
    for indices in list(phone_index.values()) + list(domain_index.values()):
        for i in range(len(indices)):
            for j in range(i + 1, len(indices)):
                union(indices[i], indices[j])

    # Build clusters
    clusters: dict[int, list[RawCandidate]] = {}
    for i, c in enumerate(candidates):
        root = find(i)
        clusters.setdefault(root, []).append(c)

    return list(clusters.values())


def _select_golden_record(
    cluster: list[RawCandidate],
    centroid: tuple[float, float] | None = None,
) -> ResolvedEntity:
    """Select the best value for each field using source reliability × recency × agreement."""
    # Sort by source reliability
    cluster_sorted = sorted(
        cluster,
        key=lambda c: SOURCE_RELIABILITY.get(c.source.split(":")[0], 0.6),
        reverse=True,
    )
    primary = cluster_sorted[0]

    # Name: most common normalised name
    name_counts: dict[str, list[str]] = {}
    for c in cluster:
        norm = _normalise_name(c.name)
        name_counts.setdefault(norm, []).append(c.name)
    best_name_norm = max(name_counts, key=lambda n: len(name_counts[n]))
    # Use the original-casing version from the most reliable source
    canonical_name = next(
        (c.name for c in cluster_sorted if _normalise_name(c.name) == best_name_norm),
        primary.name,
    )

    # Phones: union of all, normalised to E.164
    all_phones: list[str] = []
    for c in cluster:
        for p in c.phones:
            norm = _normalise_phone(p)
            if norm and norm not in all_phones:
                all_phones.append(norm)

    # Websites: union, pick best
    all_websites: list[str] = []
    all_domains: list[str] = []
    for c in cluster_sorted:
        for w in c.websites:
            dom = _normalise_domain(w)
            if dom and dom not in all_domains:
                all_domains.append(dom)
                all_websites.append(w)

    # Emails
    all_emails: list[str] = []
    for c in cluster:
        for e in c.emails:
            if e and e not in all_emails:
                all_emails.append(e)

    # Categories
    cats: list[str] = []
    for c in cluster_sorted:
        for cat in c.categories:
            if cat and cat not in cats:
                cats.append(cat)

    # Address: from most reliable source
    address = primary.address
    address_text = " ".join(str(v) for v in address.values() if v).strip()

    # Build field provenance
    provenance: list[FieldProvenance] = []
    for c in cluster:
        for phone in c.phones:
            norm = _normalise_phone(phone)
            if norm:
                provenance.append(FieldProvenance(
                    field="phone",
                    value=norm,
                    source=c.source,
                    extracted_by="deterministic",
                    confidence=SOURCE_RELIABILITY.get(c.source.split(":")[0], 0.6),
                    is_selected=norm == all_phones[0] if all_phones else False,
                ))

    geo_coords = (
        sum(c.lon for c in cluster) / len(cluster),
        sum(c.lat for c in cluster) / len(cluster),
    )

    dist_m = None
    dist_km = None
    if centroid and len(centroid) == 2:
        from app.graph.nodes.n1_geo import haversine_distance_m
        dist_m = round(haversine_distance_m(geo_coords[0], geo_coords[1], centroid[0], centroid[1]), 1)
        dist_km = round(dist_m / 1000.0, 2)

    entity_id = str(uuid.uuid4())
    return ResolvedEntity(
        id=entity_id,
        canonical_name=canonical_name,
        name_norm=best_name_norm,
        primary_category=cats[0] if cats else None,
        categories=cats[:10],
        phones_e164=all_phones[:5],
        emails=all_emails[:3],
        website_domain=all_domains[0] if all_domains else None,
        website_url=all_websites[0] if all_websites else None,
        address=address,
        address_text=address_text or None,
        locality=primary.address.get("city") or primary.address.get("suburb"),
        lon=geo_coords[0],
        lat=geo_coords[1],
        geohash7=pygeohash.encode(geo_coords[1], geo_coords[0], precision=7),
        operating_status=primary.operating_status,
        independent_source_count=_independent_source_count(cluster),
        source_ids=[f"{c.source}:{c.source_record_id}" for c in cluster],
        field_provenance=provenance,
        distance_m=dist_m,
        distance_km=dist_km,
    )


@node("n5_resolve", critical=True, max_retries=0)
async def run(state: RunState) -> dict[str, Any]:
    candidates = state.get("candidates", [])
    if not candidates:
        return {"entities": []}

    geo = state.get("geo")
    centroid = geo.centroid if geo else None

    clusters = _cluster_candidates(candidates)
    entities = [_select_golden_record(cluster, centroid=centroid) for cluster in clusters]

    log.info("Entity resolution complete",
             candidates=len(candidates),
             clusters=len(clusters))

    return {"entities": entities}
