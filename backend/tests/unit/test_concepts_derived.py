from app.relevance.concepts import resolve_concept


def test_resolve_concept_electrical_shops_returns_card_with_categories():
    card = resolve_concept("electrical shops")
    assert card is not None
    assert not card.is_synthesized
    assert len(card.categories.defining) > 0
    # Should have defining terms and categories
    assert any("electric" in c or "hardware" in c or "appliance" in c for c in card.categories.defining)
    assert len(card.get_strong_defining_terms()) > 0


def test_resolve_concept_hotel_returns_reviewed_card():
    card = resolve_concept("hotel")
    assert card is not None
    assert not card.is_synthesized
    assert not card.is_derived
    assert "hotel" in card.concept_id
