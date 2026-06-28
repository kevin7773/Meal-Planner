from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from planner.recipe_editor import (
    find_imported_recipe,
    imported_recipes,
    promote_imported_recipe,
    update_imported_recipe,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Inspect and revise imported recipe runbooks."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list")
    list_parser.add_argument("--json", action="store_true")

    show_parser = subparsers.add_parser("show")
    show_parser.add_argument("--id", required=True)
    show_parser.add_argument("--json", action="store_true")

    promote_parser = subparsers.add_parser("promote")
    promote_parser.add_argument("--id", required=True)
    promote_parser.add_argument("--actor", required=True)
    promote_parser.add_argument("--note", required=True)

    update_parser = subparsers.add_parser("update")
    update_parser.add_argument("--id", required=True)
    update_parser.add_argument("--name", required=True)
    update_parser.add_argument("--protein", required=True)
    update_parser.add_argument("--meal-scope", required=True)
    update_parser.add_argument("--prep-minutes", required=True, type=int)
    update_parser.add_argument("--cook-minutes", required=True, type=int)
    update_parser.add_argument("--fiber", required=True, type=float)
    update_parser.add_argument("--cost", required=True, type=float)
    update_parser.add_argument("--kid-reason", required=True)
    update_parser.add_argument("--method", required=True)
    update_parser.add_argument("--seasons", required=True)
    update_parser.add_argument(
        "--card-file",
        type=Path,
        help="JSON file containing edited ingredients and directions.",
    )
    update_parser.add_argument(
        "--change-note",
        default="Updated imported recipe metadata through the GUI",
    )
    args = parser.parse_args()

    try:
        if args.command == "list":
            recipes = imported_recipes()
            if args.json:
                print(json.dumps(recipes, indent=2))
            else:
                for recipe in recipes:
                    print(f"{recipe['id']}|{recipe['name']}")
            return 0
        if args.command == "show":
            recipe = find_imported_recipe(args.id)
            print(
                json.dumps(recipe, indent=2)
                if args.json
                else f"{recipe['id']}|{recipe['name']}"
            )
            return 0
        if args.command == "promote":
            revision, path = promote_imported_recipe(
                args.id,
                actor=args.actor,
                note=args.note,
            )
            print(f"{args.id}|{revision}|{path}")
            return 0

        card_sections = (
            json.loads(args.card_file.read_text(encoding="utf-8"))
            if args.card_file
            else None
        )
        if card_sections is not None and not isinstance(card_sections, dict):
            raise ValueError("Recipe card JSON must be an object")

        revision, path = update_imported_recipe(
            args.id,
            name=args.name,
            protein=args.protein,
            meal_scope=args.meal_scope,
            prep_minutes=args.prep_minutes,
            cook_minutes=args.cook_minutes,
            fiber_grams=args.fiber,
            estimated_cost_usd=args.cost,
            kid_friendly_reason=args.kid_reason,
            cooking_method=args.method,
            seasons=[
                item.strip()
                for item in args.seasons.split(",")
                if item.strip()
            ],
            card_sections=card_sections,
            change_note=args.change_note,
        )
        print(f"{args.id}|{revision}|{path}")
        return 0
    except (OSError, ValueError) as error:
        print(f"Recipe edit failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
