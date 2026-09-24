"""
app/crawl/simhash.py — 64-bit content Simhash for change detection and re-verification.

Hamming distance thresholds:
- 0–3: Page content unchanged (no re-parsing required)
- 4–8: Minor edits / date stamps
- 9+: Substantive business detail change (re-extraction required)
"""

from __future__ import annotations

import hashlib
import re


def _tokenize(text: str) -> list[str]:
    # Strip HTML tags, boilerplate whitespace, lowercase
    clean = re.sub(r"<[^>]+>", " ", text)
    tokens = re.findall(r"\b\w{3,}\b", clean.lower())
    return tokens


def compute_simhash(text: str) -> int:
    """Compute 64-bit Simhash for arbitrary web text content."""
    tokens = _tokenize(text)
    if not tokens:
        return 0

    v = [0] * 64
    for token in tokens:
        # 64-bit hash
        h = int(hashlib.md5(token.encode("utf-8")).hexdigest()[:16], 16)
        for i in range(64):
            bit = (h >> i) & 1
            if bit == 1:
                v[i] += 1
            else:
                v[i] -= 1

    fingerprint = 0
    for i in range(64):
        if v[i] > 0:
            fingerprint |= (1 << i)
    return fingerprint


def hamming_distance(hash1: int, hash2: int) -> int:
    """Compute Hamming distance between two 64-bit Simhashes."""
    x = hash1 ^ hash2
    return bin(x).count("1")
