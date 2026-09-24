#!/usr/bin/env python3
"""
harvest_categories.py — Category Taxonomy Harvester

Queries an existing Overture city-level Parquet cache to discover what
basic_category / taxonomy.primary values are used by businesses matching
a given concept's defining label patterns.

Usage:
    python scripts/harvest_categories.py --keyword "pooja store" --cache-dir ./cache/overture --top 60

Output: YAML-formatted candidate category list for pasting into a concept card.

₹0 rule: uses only the local cache (no network calls).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main() -> None:
    parser = argparse.ArgumentParser(description="Harvest Overture categories for a concept keyword.")
    parser.add_argument("--keyword", required=True, help="Primary keyword / concept ID to harvest for")
    parser.add_argument("--cache-dir", default="./cache/overture", help="Path to Overture cache directory")
    parser.add_argument("--top", type=int, default=60, help="Number of top categories to return")
    parser.add_argument("--name-patterns", nargs="*", help="Additional name patterns to search (regex)")
    args = parser.parse_args()

    try:
        import duckdb
    except ImportError:
        print("ERROR: duckdb is required. Run: pip install duckdb", file=sys.stderr)
        sys.exit(1)

    cache_dir = Path(args.cache_dir).expanduser().resolve()
    if not cache_dir.exists():
        print(f"ERROR: Cache directory not found: {cache_dir}", file=sys.stderr)
        sys.exit(1)

    # Find all parquet files in cache
    parquet_files = list(cache_dir.rglob("*.parquet"))
    if not parquet_files:
        print(f"ERROR: No Parquet files found in {cache_dir}", file=sys.stderr)
        print("Run a LeadCore discovery first to populate the cache.", file=sys.stderr)
        sys.exit(1)

    # Build name pattern from keyword
    kw = args.keyword.lower()
    # Split into component words and create an alternation pattern
    kw_parts = kw.replace("-", " ").replace("_", " ").split()
    # Core patterns for the concept
    name_patterns = args.name_patterns or kw_parts
    pattern = "|".join(f"(?i){p}" for p in name_patterns)

    print(f"\nHarvesting categories for: '{args.keyword}'")
    print(f"Name patterns: {pattern}")
    print(f"Cache files: {len(parquet_files)}")
    print(f"Cache dir: {cache_dir}\n")

    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial;")

    # Use all parquet files with a glob
    parquet_glob = str(cache_dir / "**" / "*.parquet")

    query = f"""
    SELECT
        basic_category,
        taxonomy.primary AS taxonomy_primary,
        count(*) AS n,
        -- Sample names to validate matches
        list(names.primary)[1:3] AS sample_names
    FROM read_parquet('{parquet_glob}', hive_partitioning=0)
    WHERE (
        regexp_matches(names.primary, '{pattern}')
    )
    AND basic_category IS NOT NULL
    GROUP BY 1, 2
    ORDER BY n DESC
    LIMIT {args.top}
    """

    try:
        result = con.execute(query).fetchall()
    except Exception as e:
        print(f"ERROR: DuckDB query failed: {e}", file=sys.stderr)
        print("\nHint: The names column may be a struct. Trying alternate schema...", file=sys.stderr)
        # Try alternate schema where names is a struct
        query_alt = f"""
        SELECT
            basic_category,
            count(*) AS n
        FROM read_parquet('{parquet_glob}', hive_partitioning=0)
        WHERE regexp_matches(names['primary'], '{pattern}')
        AND basic_category IS NOT NULL
        GROUP BY 1
        ORDER BY n DESC
        LIMIT {args.top}
        """
        try:
            result_alt = con.execute(query_alt).fetchall()
            result = [(r[0], None, r[1], []) for r in result_alt]
        except Exception as e2:
            print(f"ERROR: Alternate query also failed: {e2}", file=sys.stderr)
            con.close()
            sys.exit(1)

    con.close()

    if not result:
        print(f"No results found for pattern: {pattern}")
        print("Try broadening the name patterns with --name-patterns")
        return

    print("# ── Candidate category list ─────────────────────────────────────────────")
    print(f"# Keyword: {args.keyword!r}")
    print(f"# Matched {len(result)} category groups\n")
    print("categories:")
    print("  defining:")
    for row in result:
        basic_cat = row[0]
        tax_primary = row[1] if len(row) > 1 else None
        count = row[2] if len(row) > 2 else row[1]
        samples = row[3] if len(row) > 3 else []

        if basic_cat:
            sample_str = f"  # n={count}, e.g. {', '.join(str(s) for s in samples[:2])}" if samples else f"  # n={count}"
            print(f"    - {basic_cat!r}{sample_str}")
        if tax_primary and tax_primary != basic_cat:
            print(f"    - {tax_primary!r}  # taxonomy.primary")

    print("\n# ── Instructions ────────────────────────────────────────────────────────")
    print("# 1. Review the categories above.")
    print("# 2. Add confirmed ones to categories.defining in the concept card.")
    print("# 3. Add categories that 'host' the concept (not primary) to categories.host.")
    print("# 4. Add clearly wrong categories to categories.incompatible.")
    print("# 5. Bump the version number in the concept card YAML.")


if __name__ == "__main__":
    main()
