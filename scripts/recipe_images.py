from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from planner.recipe_images import (
    SCHEMA_VERSION,
    SUPPORTED_EXTENSIONS,
    load_recipe_image_metadata,
    recipe_image_index,
    recipe_image_metadata_path,
    recipe_name_by_id,
)


def validate(root: Path = PROJECT_ROOT) -> list[str]:
    errors: list[str] = []
    document = load_recipe_image_metadata(root)
    path = recipe_image_metadata_path(root)
    if document.get("schema_version") != SCHEMA_VERSION:
        errors.append(
            f"{path.relative_to(root)}: schema_version must be {SCHEMA_VERSION}"
        )
    recipes = document.get("recipes")
    if not isinstance(recipes, dict):
        return [f"{path.relative_to(root)}: recipes must be an object"]

    known_recipe_ids = set(recipe_name_by_id(root))
    images = recipe_image_index(root)
    for recipe_id in sorted(known_recipe_ids):
        if recipe_id not in recipes:
            errors.append(f"{path.relative_to(root)}: missing image metadata for {recipe_id}")
    for recipe_id, record in sorted(recipes.items()):
        if recipe_id not in known_recipe_ids:
            errors.append(f"{path.relative_to(root)}: unknown recipe_id {recipe_id}")
            continue
        if not isinstance(record, dict):
            errors.append(f"{path.relative_to(root)}: {recipe_id} metadata must be an object")
            continue
        if record.get("recipe_id") != recipe_id:
            errors.append(f"{path.relative_to(root)}: {recipe_id} record must repeat its recipe_id")
        relative_path = record.get("relative_path")
        if not isinstance(relative_path, str) or not relative_path:
            errors.append(f"{path.relative_to(root)}: {recipe_id} requires relative_path")
            continue
        image_path = root / relative_path
        if not image_path.is_file():
            errors.append(f"{path.relative_to(root)}: {recipe_id} image file is missing: {relative_path}")
            continue
        if image_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            errors.append(f"{path.relative_to(root)}: {recipe_id} image extension is unsupported")
        if images.get(recipe_id) != image_path:
            errors.append(f"{path.relative_to(root)}: {recipe_id} metadata does not match the active image file")
        filename = record.get("filename")
        if filename != image_path.name:
            errors.append(f"{path.relative_to(root)}: {recipe_id} filename does not match relative_path")
        for field in ("source_type", "source", "updated"):
            value = record.get(field)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"{path.relative_to(root)}: {recipe_id} requires non-empty {field}")
        if not isinstance(record.get("primary"), bool):
            errors.append(f"{path.relative_to(root)}: {recipe_id} primary must be boolean")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate recipe image metadata.")
    parser.add_argument("command", choices=("validate",))
    args = parser.parse_args()
    if args.command == "validate":
        errors = validate()
        if errors:
            for error in errors:
                print(error, file=sys.stderr)
            return 1
        print(
            json.dumps(
                {
                    "schema_version": SCHEMA_VERSION,
                    "recipe_count": len(recipe_name_by_id(PROJECT_ROOT)),
                    "metadata_path": str(recipe_image_metadata_path(PROJECT_ROOT).relative_to(PROJECT_ROOT)),
                },
                indent=2,
            )
        )
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
