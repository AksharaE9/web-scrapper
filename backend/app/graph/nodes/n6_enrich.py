"""
N6 — WebsiteEnrichmentAgent

Features:
- Concurrent website crawling using DomainFrontier across domains with Semaphore(8)
- Strictly serial crawling within a single domain to preserve per-host politeness
- Soft deadline enforcement to retain and persist partial crawl results on timeouts
- Real-time node_progress SSE events emitted across domains
- Structured data extraction (schema.org/LocalBusiness via extruct)
- Deterministic extraction: tel/mailto hrefs, India phone regex, social profiles
- Dynamic domain cap based on budget and target lead count
- Crawl log event recording
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any
import urllib.parse

from app.crawl.extract_structured import extract_deterministic_secondary, extract_structured_data
from app.crawl.frontier import DomainFrontier
from app.graph.runtime import emit_node_progress, node
from app.graph.state import ResolvedEntity, RunState
from app.settings import settings

logger = logging.getLogger(__name__)


@node("n6_enrich", critical=False, max_retries=1, budget_key="http_calls_used", timeout_seconds=300.0)
async def run(state: RunState) -> dict[str, Any]:
    run_id = state.get("run_id", "unknown")
    iteration = state.get("iteration", 0)
    entities: list[ResolvedEntity] = state.get("entities", [])
    if not entities:
        return {"entities": []}

    query_obj = state.get("query")
    enrich_enabled = getattr(query_obj, "enrich_websites", True)
    if not enrich_enabled:
        return {"entities": entities}

    # Identify entities with website domains
    frontier = DomainFrontier(max_pages_per_domain=3)
    domain_to_entities: dict[str, list[ResolvedEntity]] = {}

    for e in entities:
        target_web = e.website_url or e.website_domain
        if target_web:
            target_url = target_web if target_web.startswith(("http://", "https://")) else f"https://{target_web}"
            dom = urllib.parse.urlparse(target_url).netloc
            if dom:
                frontier.add_url(target_url)
                # Also try standard about/contact subpages
                frontier.add_url(f"https://{dom}/contact")
                frontier.add_url(f"https://{dom}/about")
                domain_to_entities.setdefault(dom, []).append(e)

    # Calculate dynamic domain budget: max(25, min(100, max_results))
    max_results = getattr(query_obj, "max_results", 50) if query_obj else 50
    domain_cap = max(25, min(100, max_results * 2))

    all_domains = list(domain_to_entities.keys())
    target_domains = all_domains[:domain_cap]
    domains_skipped = len(all_domains) - len(target_domains)

    # Read configurable crawl depth from query options (default 3, bounded 1..5)
    max_fetches = 3
    if query_obj and hasattr(query_obj, "options") and isinstance(query_obj.options, dict):
        max_fetches = int(query_obj.options.get("max_crawl_pages", query_obj.options.get("max_fetches", 3)))
    max_fetches = max(1, min(5, max_fetches))

    # Soft deadline: 90s soft budget for enrichment per iteration
    soft_deadline = time.monotonic() + 90.0
    sem = asyncio.Semaphore(settings.crawl_concurrency if hasattr(settings, "crawl_concurrency") else 8)

    done_domains = 0
    ok_domains = 0
    blocked_domains = 0
    failed_domains = 0
    total_fields_enriched = 0
    crawl_log: list[dict[str, Any]] = []
    is_partial = False

    async def crawl_single_domain(dom: str, idx: int) -> None:
        nonlocal done_domains, ok_domains, blocked_domains, failed_domains, total_fields_enriched, is_partial
        if time.monotonic() > soft_deadline:
            is_partial = True
            return

        async with sem:
            if time.monotonic() > soft_deadline:
                is_partial = True
                return

            try:
                results = await frontier.crawl_domain(dom, max_fetches=max_fetches)
                matched_entities = domain_to_entities.get(dom, [])
                domain_had_ok = False

                for res in results:
                    crawl_log.append({
                        "url": res.url,
                        "domain": dom,
                        "status_code": res.status_code,
                        "outcome": res.outcome,
                    })

                    if res.outcome == "ok" and res.html:
                        domain_had_ok = True
                        # 1. Structured data
                        s_data = extract_structured_data(res.html, res.url)
                        # 2. Secondary regex
                        d_data = extract_deterministic_secondary(res.html)

                        all_new_phones = set(s_data.get("phones", []) + d_data.get("phones", []))
                        all_new_emails = set(s_data.get("emails", []) + d_data.get("emails", []))

                        for entity in matched_entities:
                            for p in all_new_phones:
                                if p not in entity.phones_e164:
                                    entity.phones_e164.append(p)
                                    total_fields_enriched += 1
                            for em in all_new_emails:
                                if em not in entity.emails:
                                    entity.emails.append(em)
                                    total_fields_enriched += 1
                            if d_data.get("socials"):
                                for sk, sv in d_data["socials"].items():
                                    if sk not in entity.socials:
                                        entity.socials[sk] = sv
                                        total_fields_enriched += 1

                    elif res.outcome in ("blocked_by_site", "disallow"):
                        blocked_domains += 1
                    else:
                        failed_domains += 1

                if domain_had_ok:
                    ok_domains += 1

            except Exception as err:
                logger.warning(f"Error enriching domain {dom}: {err}")
                failed_domains += 1
            finally:
                done_domains += 1
                if done_domains % 2 == 0 or done_domains == len(target_domains):
                    await emit_node_progress(
                        run_id=run_id,
                        node="n6_enrich",
                        iteration=iteration,
                        done=done_domains,
                        total=len(target_domains),
                        current_domain=dom,
                        extra={
                            "ok": ok_domains,
                            "blocked": blocked_domains,
                            "failed": failed_domains,
                            "fields_enriched": total_fields_enriched,
                        },
                    )

    # Run domain crawling concurrently with Semaphore
    tasks = [crawl_single_domain(dom, idx) for idx, dom in enumerate(target_domains)]
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)

    enrich_stats = {
        "domains_attempted": done_domains,
        "domains_target": len(target_domains),
        "domains_skipped": domains_skipped,
        "domains_ok": ok_domains,
        "domains_blocked": blocked_domains,
        "domains_failed": failed_domains,
        "fields_enriched": total_fields_enriched,
        "partial": is_partial,
    }
    logger.info(
        f"N6 WebsiteEnrichmentAgent complete: {done_domains}/{len(target_domains)} domains crawled, "
        f"{total_fields_enriched} fields enriched (partial={is_partial})"
    )

    return {
        "entities": entities,
        "source_stats": {
            "enrichment": enrich_stats,
        },
        "crawl_log": crawl_log,
    }
