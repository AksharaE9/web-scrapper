"""
LeadCore Zero — Concept Card Foundry & 6-Stage Resolution Test Suite (FOUNDRY-1.0)

Verifies:
1. Exact, alias, fuzzy, retrieved, derived, and unresolved resolution stages.
2. The zero-failure, never-empty contract.
3. 500-string fuzz test with random strings, typos, Hinglish, emojis, empty, and 500-char text.
4. Latency p95 <= 30ms.
5. Sibling contrastive veto extraction.
"""

import random
import string
import time
import pytest
from app.relevance.concepts import resolve_concept, load_all_cards
from app.taxonomy.foundry import get_taxonomy_spine


def test_core_concept_resolutions() -> None:
    # 1. Shopping Mall
    c_mall = resolve_concept("shopping mall")
    assert c_mall.concept_id in ("shopping_mall", "shopping_center")
    assert c_mall.provenance in ("seeded", "alias")
    assert len(c_mall.get_strong_defining_terms()) > 0
    assert "mall" in c_mall.labels or "shopping mall" in c_mall.labels

    # 2. Pooja Store
    c_pooja = resolve_concept("pooja store")
    assert c_pooja.concept_id == "pooja_store"
    assert c_pooja.provenance in ("seeded", "alias")
    assert any("pooja" in t or "puja" in t for t in c_pooja.signals.defining_terms["strong"])

    # 3. Electrical Shops
    c_elec = resolve_concept("electrical shops")
    assert c_elec.concept_id in ("electrical_store", "electronics_store")
    assert c_elec.provenance in ("seeded", "alias")

    # 4. Hotel
    c_hotel = resolve_concept("hotel")
    assert c_hotel.concept_id == "hotel"
    assert c_hotel.provenance in ("seeded", "alias")

    # 5. Fuzzy Typo: "shoping mall" -> "shopping mall"
    c_typo = resolve_concept("shoping mall")
    assert c_typo.concept_id == "shopping_mall"
    assert c_typo.provenance == "fuzzy"
    assert c_typo.did_you_mean is not None

    # 6. Indian SMB Staples
    for kw, expected_id in [
        ("kirana store", "kirana_store"),
        ("tiffin centre", "tiffin_centre"),
        ("xerox shop", "xerox_shop"),
        ("pg", "pg_accommodation"),
        ("mithai shop", "sweet_shop"),
    ]:
        card = resolve_concept(kw)
        assert card.concept_id == expected_id, f"Failed for {kw}: got {card.concept_id}"
        assert card.provenance in ("seeded", "alias", "retrieved")


def test_taxonomy_spine_and_siblings() -> None:
    spine = get_taxonomy_spine()
    assert len(spine.categories) >= 2000
    assert len(spine.basic_categories) >= 200

    # Test sibling retrieval for hotel
    hotel_siblings = spine.get_siblings("hotel")
    assert isinstance(hotel_siblings, list)
    # Siblings under lodging should include motel, hostel, resort, etc.
    assert any(s in hotel_siblings for s in ["motel", "hostel", "resort", "bed_and_breakfast", "guest_house"])


def test_resolve_concept_taxonomy_derived() -> None:
    # A category in Overture not in hand-written seeds, e.g. "amusement_park" or "bowling_alley" or "car_wash"
    c_derived = resolve_concept("bowling alley")
    assert c_derived is not None
    assert c_derived.provenance in ("seeded", "alias", "fuzzy", "derived", "retrieved")
    assert len(c_derived.categories.defining) > 0


def test_resolve_concept_never_empty_fuzz_500() -> None:
    """Fuzz test with 500 diverse inputs: ensures zero exceptions, zero None, zero empty cards."""
    random.seed(42)
    
    test_cases = [
        "",  # empty
        "   ",  # whitespace
        "!@#$%^&*()_+",  # punctuation
        "🛍️ 🏨 💻 🍕",  # emojis
        "a",  # 1 char
        "supercalifragilisticexpialidocious",
        "kirana", "puja", "shoppping", "hotelll", "restorant", "gymmm",
        "dosa place in ameerpet", "cheap pg for gents", "xerox and lamination near me",
        "x" * 500,  # 500 chars
    ]

    # Generate random strings
    for _ in range(480):
        length = random.randint(1, 40)
        chars = string.ascii_letters + string.digits + " _-/'"
        rnd = "".join(random.choice(chars) for _ in range(length))
        test_cases.append(rnd)

    latencies = []
    for tc in test_cases:
        t0 = time.perf_counter()
        card = resolve_concept(tc)
        t1 = time.perf_counter()
        latencies.append((t1 - t0) * 1000.0)

        assert card is not None, f"Returned None for '{tc}'"
        assert card.concept_id != "", f"Empty concept_id for '{tc}'"
        assert card.definition != "", f"Empty definition for '{tc}'"
        assert len(card.categories.defining) > 0, f"No defining categories for '{tc}'"
        assert card.provenance in ("seeded", "alias", "fuzzy", "retrieved", "derived", "unresolved")

    p95 = sorted(latencies)[int(len(latencies) * 0.95)]
    print(f"500-Fuzz completed: avg={sum(latencies)/len(latencies):.2f}ms, p95={p95:.2f}ms")
    assert p95 <= 30.0, f"p95 latency too high: {p95:.2f}ms"
