"""
Unit tests for extracted pure modules (sources, crawl, relevance, resolve, verify, metrics).
Runs completely offline with zero external network or database requirements.
"""

from app.crawl.simhash import compute_simhash, hamming_distance
from app.metrics.calibration import compute_expected_calibration_error
from app.metrics.expectations import run_output_expectation_suite
from app.metrics.wilson import compute_wilson_interval
from app.rag.grounded_extract import verify_grounded_span
from app.relevance.concepts import resolve_concept
from app.relevance.fusion import reciprocal_rank_fusion
from app.relevance.lexical import compute_trigram_set, score_lexical_bm25, trigram_similarity
from app.relevance.tokenize import tokenize_profile
from app.resolve.blocking import get_blocking_geohashes
from app.resolve.normalize import normalize_business_name, normalize_domain, normalize_phone_e164
from app.verify.phone import verify_phone


def test_simhash_distance() -> None:
    text1 = "Sri Lakshmi Pooja Stores Whitefield selling agarbatti and camphor items"
    text2 = "Sri Lakshmi Pooja Stores Whitefield selling agarbatti and camphor products"
    text3 = "Divine Footwear and Leather Shoes Bangalore City"

    h1 = compute_simhash(text1)
    h2 = compute_simhash(text2)
    h3 = compute_simhash(text3)

    assert hamming_distance(h1, h2) <= 8  # Minor modification
    assert hamming_distance(h1, h3) > 10  # Substantive difference


def test_wilson_confidence_interval() -> None:
    # 45 successes out of 50
    point, low, high = compute_wilson_interval(45, 50)
    assert point == 0.9
    assert 0.78 <= low <= 0.85
    assert 0.94 <= high <= 0.98


def test_ece_calibration_error() -> None:
    probs = [0.9, 0.8, 0.7, 0.6, 0.4, 0.2]
    truth = [1, 1, 1, 0, 0, 0]
    ece = compute_expected_calibration_error(probs, truth)
    assert 0.0 <= ece <= 1.0


def test_grounded_span_verification() -> None:
    source = "Contact our store at +91 98450 12345 or visit us in Whitefield, Bengaluru."
    assert verify_grounded_span("+91 98450 12345", "+91 98450 12345", source) is True
    assert verify_grounded_span("info@fake.com", "info@fake.com", source) is False


def test_lexical_scoring_and_fusion() -> None:
    card = resolve_concept("pooja stores")
    prof = tokenize_profile("Sri Raghavendra Pooja Samagri Bhandar", ["general_store"])
    score = score_lexical_bm25(prof, card)
    assert score >= 0.5  # Matches defining pooja and samagri

    fused = reciprocal_rank_fusion([0.9, 0.1], [0.8, 0.2], k=60)
    assert len(fused) == 2
    assert fused[0] > fused[1]


def test_normalize_and_blocking() -> None:
    assert normalize_business_name("Archies Gift Shoppe Pvt Ltd") == "archies gift shoppe"
    assert normalize_phone_e164("080-2845-1234") is not None
    assert normalize_domain("https://www.williampenn.net/store/about") == "williampenn.net"

    hashes = get_blocking_geohashes(12.97, 77.75)
    assert len(hashes) >= 5


def test_phone_verification_libphonenumber() -> None:
    res_mobile = verify_phone("+919845012345", has_website=False)
    assert res_mobile.is_valid is True
    assert res_mobile.number_type in ("MOBILE", "FIXED_LINE_OR_MOBILE")
    assert res_mobile.personal_risk is True  # Mobile with no website

    res_with_web = verify_phone("+919845012345", has_website=True)
    assert res_with_web.personal_risk is False

    res_invalid = verify_phone("12345")
    assert res_invalid.is_valid is False
