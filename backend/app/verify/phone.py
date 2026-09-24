"""
app/verify/phone.py — Rigorous phone validation using libphonenumber.

Validates:
1. is_valid_number (not merely is_possible_number)
2. E.164 canonical normalization
3. Line type classification (MOBILE, FIXED_LINE, TOLL_FREE, VOIP)
4. Personal number risk flag (mobile number with no business website / context)
"""

from __future__ import annotations

import phonenumbers
from phonenumbers import PhoneNumberType


class PhoneVerificationResult:
    def __init__(
        self,
        raw: str,
        is_valid: bool,
        e164: str | None = None,
        number_type: str = "UNKNOWN",
        personal_risk: bool = False,
    ) -> None:
        self.raw = raw
        self.is_valid = is_valid
        self.e164 = e164
        self.number_type = number_type
        self.personal_risk = personal_risk


def verify_phone(phone_str: str, has_website: bool = False, region: str = "IN") -> PhoneVerificationResult:
    """Validate a phone number using libphonenumber."""
    if not phone_str:
        return PhoneVerificationResult(raw="", is_valid=False)

    try:
        parsed = phonenumbers.parse(phone_str, region)
        if not phonenumbers.is_valid_number(parsed):
            return PhoneVerificationResult(raw=phone_str, is_valid=False)

        e164 = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
        num_type_enum = phonenumbers.number_type(parsed)

        type_names = {
            PhoneNumberType.MOBILE: "MOBILE",
            PhoneNumberType.FIXED_LINE: "FIXED_LINE",
            PhoneNumberType.FIXED_LINE_OR_MOBILE: "FIXED_LINE_OR_MOBILE",
            PhoneNumberType.TOLL_FREE: "TOLL_FREE",
            PhoneNumberType.VOIP: "VOIP",
        }
        num_type = type_names.get(num_type_enum, "OTHER")

        # Mobile numbers without any website or verified listing flag personal number risk for DPDP
        personal_risk = (num_type in ("MOBILE", "FIXED_LINE_OR_MOBILE") and not has_website)

        return PhoneVerificationResult(
            raw=phone_str,
            is_valid=True,
            e164=e164,
            number_type=num_type,
            personal_risk=personal_risk,
        )

    except Exception:
        return PhoneVerificationResult(raw=phone_str, is_valid=False)
