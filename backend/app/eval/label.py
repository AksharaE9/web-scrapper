"""
Evaluation Labeling CLI — LeadCore Zero v2.1
Interactive keyboard labeling tool for gold evaluation benchmark cases (y = relevant, n = not relevant, s = skip).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
import yaml

EVAL_DIR = Path(__file__).resolve().parent.parent.parent.parent / "eval" / "relevance"


def label_case(case_name: str) -> None:
    case_path = EVAL_DIR / f"{case_name}.yaml"
    if not case_path.exists():
        print(f"Error: Evaluation case file not found: {case_path}")
        sys.exit(1)

    with open(case_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    labels = data.get("labels", [])
    print(f"\n--- Labelling Case: {case_name} ({len(labels)} candidates) ---")
    print("Controls: [y] = Relevant, [n] = Not Relevant, [s] = Skip, [q] = Quit and Save\n")

    changed = False
    for i, item in enumerate(labels, 1):
        curr = item.get("relevant")
        status_str = "Relevant" if curr is True else ("Not Relevant" if curr is False else "Unlabelled")
        print(f"[{i}/{len(labels)}] Name: {item['name']} | Cats: {item.get('categories')} | Current: {status_str}")
        try:
            choice = input("Verdict (y/n/s/q): ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            break

        if choice == "q":
            break
        elif choice == "y":
            item["relevant"] = True
            changed = True
        elif choice == "n":
            item["relevant"] = False
            changed = True
        elif choice == "s":
            continue

    if changed:
        with open(case_path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, sort_keys=False)
        print(f"\nSaved updated labels to {case_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="LeadCore Zero Evaluation Labeling Tool")
    parser.add_argument("--case", type=str, required=True, help="Evaluation case name (e.g. pooja_whitefield)")
    args = parser.parse_args()
    label_case(args.case)


if __name__ == "__main__":
    main()
