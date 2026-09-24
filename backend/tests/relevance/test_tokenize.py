"""
R0 Unit Tests — Tokenization, Transliteration, Compound Splitting & Evidence Classification
"""

from app.relevance.tokenize import tokenize_profile

def test_sri_lakshmi_pooja_stores() -> None:
    p = tokenize_profile("Sri Lakshmi Pooja Stores")
    assert "pooja" in p.evidence_tokens
    assert "<shop_word>" in p.evidence_tokens
    assert "sri" in p.non_evidence_tokens or "lakshmi" in p.non_evidence_tokens

def test_divine_footwear() -> None:
    p = tokenize_profile("Divine Footwear")
    assert "footwear" in p.evidence_tokens
    assert "divine" in p.non_evidence_tokens
    assert "divine" not in p.evidence_tokens

def test_deepam_taxi() -> None:
    p = tokenize_profile("Deepam Taxi")
    assert "taxi" in p.evidence_tokens
    assert "deepam" in p.non_evidence_tokens
    assert "deepam" not in p.evidence_tokens

def test_kannada_script_transliteration() -> None:
    p = tokenize_profile("ಶ್ರೀ ಪೂಜಾ ಸ್ಟೋರ್ಸ್")
    # Transliteration or canonicalization yields pooja
    tokens_str = " ".join(p.name_tokens).lower()
    assert "pooja" in tokens_str or "puja" in tokens_str or "pooja" in p.evidence_tokens

def test_compound_splitting_poojastores() -> None:
    p = tokenize_profile("PoojaStores")
    assert "pooja" in p.name_tokens or "pooja" in p.evidence_tokens
    assert "<shop_word>" in p.name_tokens or "<shop_word>" in p.evidence_tokens
