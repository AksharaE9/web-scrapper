"""
Tests for Live Web Enrichment, Scrapling HTML extraction, and Robots.txt policy enforcement.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch
import pytest

from app.crawl.extract_structured import extract_deterministic_secondary, extract_structured_data
from app.crawl.fetcher import FetchResult, fetch_page
from app.crawl.robots import is_url_allowed
from app.graph.nodes.n6_enrich import run as enrich_run
from app.graph.state import LocationInput, QueryInput, ResolvedEntity, RunState


def test_structured_data_and_deterministic_extraction():
    """Verify JSON-LD and regex extract phones, emails, and socials from HTML."""
    sample_html = """
    <!DOCTYPE html>
    <html>
    <head>
        <script type="application/ld+json">
        {
            "@context": "https://schema.org",
            "@type": "LocalBusiness",
            "name": "Sri Lakshmi Pooja Stores",
            "telephone": "+91-9845012345",
            "email": "contact@srilakshmipooja.com"
        }
        </script>
    </head>
    <body>
        <p>Call us at <a href="tel:+919845099999">+91 98450 99999</a></p>
        <p>Email: <a href="mailto:info@srilakshmipooja.com">info@srilakshmipooja.com</a></p>
        <a href="https://instagram.com/srilakshmipooja">Instagram</a>
    </body>
    </html>
    """

    s_data = extract_structured_data(sample_html, "https://srilakshmipooja.com")
    d_data = extract_deterministic_secondary(sample_html)

    assert "+91-9845012345" in s_data["phones"] or "+919845012345" in [p.replace("-", "") for p in s_data["phones"]]
    assert "contact@srilakshmipooja.com" in s_data["emails"]
    assert "info@srilakshmipooja.com" in d_data["emails"]
    assert "instagram" in d_data["socials"]


@pytest.mark.asyncio
async def test_ssrf_protection_blocks_private_ip():
    """Verify SSRF protection stops queries to internal or metadata IPs."""
    res_local = await fetch_page("http://127.0.0.1:8000/admin")
    assert res_local.outcome == "ssrf_blocked"

    res_meta = await fetch_page("http://169.254.169.254/latest/meta-data")
    assert res_meta.outcome == "ssrf_blocked"

    res_priv = await fetch_page("http://192.168.1.1/router")
    assert res_priv.outcome == "ssrf_blocked"


@pytest.mark.asyncio
async def test_website_enrichment_node_updates_entities():
    """N6 enrich node crawls entity domain and enriches phone/email attributes."""
    entity = ResolvedEntity(
        id="ent-123",
        canonical_name="Whitefield Pooja Emporium",
        name_norm="whitefield pooja emporium",
        website_domain="whitefieldpooja.in",
        website_url="https://whitefieldpooja.in",
        phones_e164=[],
        emails=[],
        socials={},
        address={},
        lon=77.749,
        lat=12.969,
        confidence=0.8,
        tier="Likely",
        independent_source_count=1,
        source_ids=["overture:123"],
    )

    sample_html = """
    <html>
        <body>
            <a href="tel:+918028451234">+91 80 2845 1234</a>
            <a href="mailto:support@whitefieldpooja.in">support@whitefieldpooja.in</a>
        </body>
    </html>
    """

    with patch("app.crawl.frontier.DomainFrontier.crawl_domain") as mock_crawl:
        mock_crawl.return_value = [
            FetchResult(
                url="https://whitefieldpooja.in",
                status_code=200,
                html=sample_html,
                outcome="ok",
                simhash=12345,
            )
        ]

        state: RunState = {
            "run_id": "test-run-enrich",
            "query": QueryInput(
                location=LocationInput(locality="Whitefield", city="Bengaluru"),
                keywords=["pooja store"],
                enrich_websites=True,
            ),
            "geo": None,
            "plans": [],
            "candidates": [],
            "source_stats": {},
            "entities": [entity],
            "verifications": {},
            "iteration": 0,
            "budget": None,
            "errors": [],
            "degraded": [],
            "metrics": {},
            "disambiguation_choice": None,
        }

        result = await enrich_run(state)
        assert len(result["entities"]) == 1
        updated = result["entities"][0]
        assert len(updated.phones_e164) > 0 or len(updated.emails) > 0
        assert "source_stats" in result
        assert "enrichment" in result["source_stats"]
