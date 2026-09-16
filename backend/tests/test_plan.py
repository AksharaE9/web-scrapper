"""
Unit tests for Keyword Planning & Rule Matching
"""

from app.graph.nodes.n2_keyword import _build_plan_from_rule, _load_rules, _normalise_keyword


def test_normalise_keyword() -> None:
    assert _normalise_keyword("  GYMS  ") == "gyms"
    assert _normalise_keyword("Café & Bistro") == "cafe & bistro"


def test_keyword_rules_coverage() -> None:
    rules = _load_rules()
    assert "gym" in rules
    assert "salon" in rules
    assert "restaurant" in rules
    assert "pharmacy" in rules

    gym_rule = rules["gym"]
    plan = _build_plan_from_rule("gym", gym_rule)
    assert len(plan.osm_tag_filters) > 0
    assert "leisure=fitness_centre" in plan.osm_tag_filters
    assert len(plan.name_patterns) > 0
    assert len(plan.exclude_patterns) > 0
    assert plan.planner == "taxonomy_rules"
    assert plan.plan_confidence >= 0.8
