"""
app/crawl/extract_structured.py — Structured and secondary deterministic web data extraction.

Extracts:
1. JSON-LD / Microdata / RDFa via `extruct` (schema.org/LocalBusiness, schema.org/Organization)
2. Deterministic secondary extraction: tel: & mailto: hrefs, social links, India phone regex
3. Branch disambiguation: matches branch addresses against target locality / city
"""

from __future__ import annotations

import re
import urllib.parse
from typing import Any
import extruct
import phonenumbers
import structlog

log = structlog.get_logger()

INDIA_PHONE_RE = re.compile(
    r"(?:(?:\+91|0091|0)[\s\-]?)?(?:[6-9]\d{9}|[1-9]\d{1,4}[\s\-]?\d{6,8})\b"
)
EMAIL_RE = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")


def extract_structured_data(html: str, base_url: str) -> dict[str, Any]:
    """Extract schema.org structured data using extruct."""
    result: dict[str, Any] = {
        "name": None,
        "phones": [],
        "emails": [],
        "address": None,
        "primary_category": None,
        "jsonld": [],
    }

    try:
        data = extruct.extract(html, base_url=base_url, syntaxes=["json-ld", "microdata"])
        for item in data.get("json-ld", []) + data.get("microdata", []):
            if not isinstance(item, dict):
                continue
            item_type = str(item.get("@type", "")).lower()
            if any(t in item_type for t in ["localbusiness", "store", "organization", "restaurant", "place"]):
                result["jsonld"].append(item)
                if not result["name"] and item.get("name"):
                    result["name"] = str(item["name"]).strip()
                if item.get("telephone"):
                    tel = str(item["telephone"])
                    if tel not in result["phones"]:
                        result["phones"].append(tel)
                if item.get("email"):
                    em = str(item["email"]).strip().lower()
                    if em not in result["emails"]:
                        result["emails"].append(em)
                if item.get("address") and not result["address"]:
                    result["address"] = item["address"]
    except Exception as e:
        log.warning("Structured data extruct extraction failed", error=str(e), url=base_url)

    return result


def extract_deterministic_secondary(html: str) -> dict[str, Any]:
    """Secondary deterministic regex extraction from HTML text and links."""
    phones: set[str] = set()
    emails: set[str] = set()
    socials: dict[str, str] = {}

    # 1. Tel & Mailto links
    tel_matches = re.findall(r'href=[\'"]tel:([^\'"]+)[\'"]', html, re.IGNORECASE)
    for t in tel_matches:
        cleaned = re.sub(r"[^\d+]", "", t)
        if len(cleaned) >= 10:
            phones.add(cleaned)

    mailto_matches = re.findall(r'href=[\'"]mailto:([^\'"]+)[\'"]', html, re.IGNORECASE)
    for m in mailto_matches:
        em = m.split("?")[0].strip().lower()
        if EMAIL_RE.match(em):
            emails.add(em)

    # 2. In-text India phone numbers
    text_phones = INDIA_PHONE_RE.findall(html)
    for raw in text_phones:
        cleaned = re.sub(r"[^\d+]", "", raw)
        try:
            parsed = phonenumbers.parse(cleaned, "IN")
            if phonenumbers.is_valid_number(parsed):
                e164 = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
                phones.add(e164)
        except Exception:
            pass

    # 3. Social profile links
    social_domains = {
        "facebook.com": "facebook",
        "instagram.com": "instagram",
        "linkedin.com": "linkedin",
        "twitter.com": "twitter",
        "x.com": "twitter",
        "youtube.com": "youtube",
    }
    for match in re.findall(r'href=[\'"](https?://[^\'"]+)[\'"]', html, re.IGNORECASE):
        for s_dom, s_key in social_domains.items():
            if s_dom in match and s_key not in socials:
                socials[s_key] = match

    return {
        "phones": list(phones),
        "emails": list(emails),
        "socials": socials,
    }


def disambiguate_branch(
    branches: list[dict[str, Any]],
    target_locality: str | None,
    target_city: str | None,
) -> dict[str, Any] | None:
    """Select the specific branch matching target locality or city tokens."""
    if not branches:
        return None
    if len(branches) == 1:
        return branches[0]

    loc_token = (target_locality or "").lower().strip()
    city_token = (target_city or "").lower().strip()

    for b in branches:
        addr = str(b.get("address", "")).lower()
        if loc_token and loc_token in addr:
            return b
        if city_token and city_token in addr:
            return b

    return branches[0]


# Alias for backward compatibility
extract_page_data = extract_structured_data
