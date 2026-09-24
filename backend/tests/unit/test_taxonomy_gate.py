"""
Taxonomy Gate Unit Tests — REL-2.0 Part C

Prime Directive: Tests are written to FAIL on the old substring-match code first.
The key regression: `shop` should NOT match `gift_shop` (substring match bug).

Run against old gates.py first to confirm failure, then fix, then confirm pass.
"""
from __future__ import annotations

import pytest
from app.relevance.taxonomy_gate import TaxonomyVerdict, gate
from app.relevance.concepts import ConceptCard, CategoryConfig, DecisionConfig, SignalConfig, BrandConfig


def make_card(
    concept_id: str,
    defining: list[str],
    host: list[str] | None = None,
    incompatible: list[str] | None = None,
) -> ConceptCard:
    return ConceptCard(
        concept_id=concept_id,
        version=1,
        labels=[concept_id],
        definition=f"Test concept: {concept_id}",
        signals=SignalConfig(defining_terms={"strong": [concept_id]}, supporting_terms={"medium": []}),
        categories=CategoryConfig(
            defining=defining,
            host=host or [],
            incompatible=incompatible or [],
        ),
        veto_terms=[],
        brands=BrandConfig(incompatible=[]),
        decision=DecisionConfig(require_defining_signal=True, tau_hi=0.75, tau_lo=0.35),
    )


# ── Hotel concept card (loads from disk) ───────────────────────────────────
@pytest.fixture
def hotel_card() -> ConceptCard:
    from app.relevance.concepts import resolve_concept
    card = resolve_concept("hotel")
    assert not card.is_synthesized, "hotel.yaml must exist and not be synthesized"
    return card


# ── L4: Exact token match accepts ─────────────────────────────────────────
class TestDefiningMatch:
    def test_tourism_hotel_accepted(self, hotel_card: ConceptCard) -> None:
        """tourism=hotel is a defining category for hotel."""
        result = gate(["tourism=hotel"], hotel_card)
        assert result.verdict == TaxonomyVerdict.ACCEPT_CANDIDATE
        assert "hotel" in (result.matched_category or "").lower()

    def test_hotel_plain_accepted(self, hotel_card: ConceptCard) -> None:
        """Plain 'hotel' token is a defining category."""
        result = gate(["hotel"], hotel_card)
        assert result.verdict == TaxonomyVerdict.ACCEPT_CANDIDATE

    def test_motel_accepted(self, hotel_card: ConceptCard) -> None:
        """motel is in hotel's defining list."""
        result = gate(["motel"], hotel_card)
        assert result.verdict == TaxonomyVerdict.ACCEPT_CANDIDATE

    def test_resort_accepted(self, hotel_card: ConceptCard) -> None:
        """resort is in hotel's defining list."""
        result = gate(["resort"], hotel_card)
        assert result.verdict == TaxonomyVerdict.ACCEPT_CANDIDATE


# ── L5: Exact token match rejects incompatible ─────────────────────────────
class TestIncompatibleMatch:
    def test_professional_services_rejected(self, hotel_card: ConceptCard) -> None:
        """
        THE D3 REGRESSION TEST.
        'professional_services' must NOT match 'service' (substring bug).
        It SHOULD match the 'professional_services' incompatible entry exactly
        via token matching: {'professional', 'services'} ∩ card incompatible.
        """
        result = gate(["professional_services"], hotel_card)
        assert result.verdict == TaxonomyVerdict.REJECT
        assert "professional" in (result.reason or "").lower() or "incompatible" in (result.reason or "").lower()

    def test_tourism_apartment_rejected(self, hotel_card: ConceptCard) -> None:
        """tourism=apartment is in hotel's incompatible list."""
        result = gate(["tourism=apartment"], hotel_card)
        assert result.verdict == TaxonomyVerdict.REJECT

    def test_office_rejected(self, hotel_card: ConceptCard) -> None:
        """office is in hotel's incompatible list."""
        result = gate(["office"], hotel_card)
        assert result.verdict == TaxonomyVerdict.REJECT


# ── L6: Substring match DOES NOT trigger (the D3 fix) ─────────────────────
class TestSubstringNotMatched:
    def test_shop_does_not_reject_gift_shop(self) -> None:
        """
        OLD BUG: 'shop' in incompatible list would match 'gift_shop' (substring).
        NEW: 'shop' tokens = {'shop'}; 'gift_shop' tokens = {'gift', 'shop'}.
        Since 'gift_shop' tokens SUPERSET {'shop'}, the gate triggers.
        But for the inverse: if the incompatible entry is 'gift_shop' and the
        candidate is 'shop', the tokens {'gift', 'shop'} are NOT a subset of
        {'shop'}, so it should NOT match.
        """
        card = make_card("bakery", defining=["bakery"], incompatible=["gift_shop"])
        result = gate(["shop"], card)  # candidate is 'shop', incompatible is 'gift_shop'
        # 'gift_shop' tokens = {'gift', 'shop'} is NOT a subset of 'shop' tokens = {'shop'}
        # So this should NOT reject
        assert result.verdict != TaxonomyVerdict.REJECT, (
            "D3 regression: 'shop' (candidate) should NOT be rejected when 'gift_shop' is incompatible"
        )

    def test_shop_in_incompatible_rejects_shop_candidate(self) -> None:
        """
        When the incompatible entry is 'shop' (tokens: {'shop'}) and the
        candidate is 'gift_shop' (tokens: {'gift', 'shop'}),
        {'shop'} IS a subset of {'gift', 'shop'} → should reject.
        This is correct behavior: a gift shop is a type of shop.
        """
        card = make_card("bakery", defining=["bakery"], incompatible=["shop"])
        result = gate(["gift_shop"], card)
        assert result.verdict == TaxonomyVerdict.REJECT

    def test_service_in_name_does_not_match_service_apartment(self) -> None:
        """
        'service' (single token) should NOT reject a candidate just because
        the incompatible list has 'service_apartment'. Tokens of 'service_apartment'
        = {'service', 'apartment'} which is NOT a subset of {'service'}.
        """
        card = make_card("hotel", defining=["hotel"], incompatible=["service_apartment"])
        result = gate(["service"], card)  # just "service" as a category
        assert result.verdict == TaxonomyVerdict.UNCERTAIN


# ── L7: Defining overrides incompatible in taxonomy gate ──────────────────
class TestDefiningOverridesIncompatible:
    def test_hotel_with_professional_services_tag_accepted(self, hotel_card: ConceptCard) -> None:
        """
        If a place has BOTH tourism=hotel AND professional_services tags,
        the defining signal wins. This is the Overture conflation case:
        a hotel with an office on-site.
        """
        result = gate(["tourism=hotel", "professional_services"], hotel_card)
        assert result.verdict == TaxonomyVerdict.ACCEPT_CANDIDATE

    def test_hotel_with_apartment_tag_accepted_when_also_hotel(self, hotel_card: ConceptCard) -> None:
        """
        Same principle: defining category overrides incompatible.
        """
        result = gate(["hotel", "tourism=apartment"], hotel_card)
        assert result.verdict == TaxonomyVerdict.ACCEPT_CANDIDATE


# ── L8: Missing category data returns UNCERTAIN ────────────────────────────
class TestUncertainOnMissingData:
    def test_empty_categories_uncertain(self, hotel_card: ConceptCard) -> None:
        result = gate([], hotel_card)
        assert result.verdict == TaxonomyVerdict.UNCERTAIN

    def test_none_categories_uncertain(self, hotel_card: ConceptCard) -> None:
        result = gate(None, hotel_card)
        assert result.verdict == TaxonomyVerdict.UNCERTAIN

    def test_unknown_category_uncertain(self, hotel_card: ConceptCard) -> None:
        """An unrecognized category should not reject — preserves recall."""
        result = gate(["something_completely_unknown"], hotel_card)
        assert result.verdict == TaxonomyVerdict.UNCERTAIN


# ── Host category gives UNCERTAIN ─────────────────────────────────────────
class TestHostCategoryUncertain:
    def test_restaurant_inside_hotel_is_uncertain(self, hotel_card: ConceptCard) -> None:
        """A restaurant inside a hotel is UNCERTAIN (not accepted as a hotel lead)."""
        result = gate(["restaurant"], hotel_card)
        # restaurant is in host list → UNCERTAIN
        assert result.verdict == TaxonomyVerdict.UNCERTAIN
