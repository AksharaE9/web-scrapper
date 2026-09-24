"""
app/verify/email.py — Email syntax and DNS MX record validation.

Doctrine:
Verify email syntax via email-validator + DNS MX/A record lookup via dnspython.
NO SMTP callback probing.
"""

from __future__ import annotations

import logging
import dns.resolver
from email_validator import EmailNotValidError, validate_email

logger = logging.getLogger(__name__)


class EmailVerificationResult:
    def __init__(
        self,
        email: str,
        syntax_valid: bool,
        mx_valid: bool,
        domain: str | None = None,
        error: str | None = None,
    ) -> None:
        self.email = email
        self.syntax_valid = syntax_valid
        self.mx_valid = mx_valid
        self.domain = domain
        self.error = error


from functools import lru_cache

# Configured resolver with fast fallbacks
_resolver = dns.resolver.Resolver()
_resolver.nameservers = ["1.1.1.1", "8.8.8.8", "8.8.4.4"]
_resolver.lifetime = 1.0


@lru_cache(maxsize=2048)
def _check_domain_mx(domain: str) -> bool:
    try:
        answers = _resolver.resolve(domain, "MX", lifetime=1.0)
        if answers and len(answers) > 0:
            return True
    except Exception as e_mx:
        logger.debug(f"MX lookup failed for {domain}: {e_mx}")
        try:
            a_answers = _resolver.resolve(domain, "A", lifetime=1.0)
            if a_answers and len(a_answers) > 0:
                return True
        except Exception as e_a:
            logger.debug(f"A lookup failed for {domain}: {e_a}")
            return False
    return False


def verify_email(email_str: str) -> EmailVerificationResult:
    """Validate email syntax and verify DNS MX/A record existence."""
    if not email_str:
        return EmailVerificationResult(email="", syntax_valid=False, mx_valid=False)

    try:
        valid = validate_email(email_str, check_deliverability=False)
        domain = valid.domain
        has_mx = _check_domain_mx(domain)

        return EmailVerificationResult(
            email=valid.normalized,
            syntax_valid=True,
            mx_valid=has_mx,
            domain=domain,
        )

    except EmailNotValidError as e:
        return EmailVerificationResult(
            email=email_str,
            syntax_valid=False,
            mx_valid=False,
            error=str(e),
        )
