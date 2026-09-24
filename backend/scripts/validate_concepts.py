"""
Validate Concept Cards Script — LeadCore Zero

Loads and validates every YAML concept card in config/concepts/ against the ConceptCard Pydantic schema.
Exits 0 if all are valid; exits 1 with details if any fail.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.relevance.concepts import CONCEPTS_DIR, ConceptCard, load_card_from_disk


def validate_all_concepts() -> int:
    if not CONCEPTS_DIR.exists():
        print(f"Error: Concepts directory not found at {CONCEPTS_DIR}", file=sys.stderr)
        return 1

    yaml_files = sorted(list(CONCEPTS_DIR.glob("*.yaml")))
    print(f"Validating {len(yaml_files)} concept cards in {CONCEPTS_DIR}...")

    errors = []
    validated_count = 0

    for yaml_file in yaml_files:
        concept_id = yaml_file.stem
        try:
            card = load_card_from_disk(concept_id)
            if card is None:
                errors.append(f"{yaml_file.name}: Failed to load card")
                continue

            # Ensure basic sanity
            if not card.concept_id:
                errors.append(f"{yaml_file.name}: Missing concept_id")
            if not card.definition:
                errors.append(f"{yaml_file.name}: Missing definition")
            if not card.signals.defining_terms.get("strong") and not card.signals.supporting_terms.get("medium"):
                errors.append(f"{yaml_file.name}: Has neither strong nor medium signal terms")

            validated_count += 1
        except Exception as e:
            errors.append(f"{yaml_file.name}: Validation exception: {e}")

    if errors:
        print(f"\n[ERROR] Validation failed for {len(errors)} cards:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    print(f"[OK] All {validated_count} concept cards are structurally valid and fully conformant.")
    return 0


if __name__ == "__main__":
    sys.exit(validate_all_concepts())
