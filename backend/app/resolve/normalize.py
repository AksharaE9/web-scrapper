"""
app/resolve/normalize.py — Entity record normalization for linkage and matching.
"""

from __future__ import annotations

import re
import unicodedata
import phonenumbers


def normalize_business_name(name: str) -> str:
    """Lowercase, strip accents, normalize whitespace and legal suffixes."""
    if not name:
        return ""
    # NFKC
    nfkc = unicodedata.normalize("NFKC", name).lower()
    # Strip common business suffixes for matching
    cleaned = re.sub(r"\b(pvt|ltd|private|limited|llp|inc|co|corp|enterprises|traders)\b", "", nfkc)
    cleaned = re.sub(r"[^\w\s]", " ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def normalize_phone_e164(phone: str, default_country: str = "IN") -> str | None:
    """Normalize raw phone to E.164 format."""
    if not phone:
        return None
    try:
        parsed = phonenumbers.parse(phone, default_country)
        if phonenumbers.is_valid_number(parsed):
            return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
    except Exception:
        pass
    # Fallback to digits if 10-12 digits
    digits = re.sub(r"\D", "", phone)
    if len(digits) == 10:
        return f"+91{digits}"
    if len(digits) == 12 and digits.startswith("91"):
        return f"+{digits}"
    return None


def normalize_domain(url_or_domain: str | None) -> str | None:
    """Normalize URL/domain to bare lowercased registrable domain without www."""
    if not url_or_domain:
        return None
    cleaned = url_or_domain.lower().strip()
    cleaned = re.sub(r"^https?://", "", cleaned)
    cleaned = cleaned.split("/")[0].split(":")[0]
    if cleaned.startswith("www."):
        cleaned = cleaned[4:]
    return cleaned if "." in cleaned else None


# Aliases
normalise_phone = normalize_phone_e164
normalise_domain = normalize_domain
normalise_name = normalize_business_name

