import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.relevance.concepts import resolve_concept

BENCHMARK_KEYWORDS = [
    # Tier A - Seeded
    "gym", "restaurant", "bakery", "pharmacy", "salon",
    # Tier B - Common
    "hotel", "shopping mall", "hardware store", "furniture store", "dental clinic",
    # Tier C - Indian Colloquial
    "pooja store", "kirana store", "tiffin centre", "coaching centre", "xerox shop",
    # Tier D - Ambiguous / Multi-word
    "degree college", "service apartment", "car service",
    # Tier E - Typos
    "degree collage", "electrical shopp"
]

print("=== CONCEPT CARD RESOLUTION BENCHMARK ===")
hit_count = 0
for kw in BENCHMARK_KEYWORDS:
    card = resolve_concept(kw)
    is_hit = card.provenance != "unresolved"
    if is_hit:
        hit_count += 1
    print(f"Keyword: {kw:<20} | Concept ID: {card.concept_id:<22} | Provenance: {card.provenance:<10} | Conf: {card.confidence:.2f} | Hit: {'[PASS]' if is_hit else '[FAIL]'}")

hit_rate = (hit_count / len(BENCHMARK_KEYWORDS)) * 100
print(f"\nM3 Concept Card Hit Rate: {hit_count}/{len(BENCHMARK_KEYWORDS)} ({hit_rate:.1f}%)")
