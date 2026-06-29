from __future__ import annotations

import json
import re
from pathlib import Path

from planner.constants import ROOT
from planner.recipe_images import load_recipe_image_metadata
from scripts.validate_recipes import split_recipe


SCHEMA_VERSION = 1
EXCLUDED_RECIPE_FILES = {"README.md", "index.md"}


def recipe_cache_path(root: Path = ROOT) -> Path:
    return root / "planner-data" / "recipe-cache.json"


def recipe_markdown_paths(root: Path = ROOT) -> list[Path]:
    return sorted(
        path
        for path in (root / "recipes").glob("*.md")
        if not path.name.startswith("_")
        and path.name not in EXCLUDED_RECIPE_FILES
    )


def build_recipe_cache(root: Path = ROOT) -> dict:
    document = recipe_cache_document(root)
    path = recipe_cache_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(document, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return document


def load_recipe_cache(root: Path = ROOT, *, write_if_missing: bool = False) -> dict:
    path = recipe_cache_path(root)
    if not path.exists():
        return build_recipe_cache(root) if write_if_missing else recipe_cache_document(root)
    document = json.loads(path.read_text(encoding="utf-8"))
    if not recipe_cache_is_fresh(document, root=root):
        return build_recipe_cache(root) if write_if_missing else recipe_cache_document(root)
    return document


def recipe_cache_document(root: Path = ROOT) -> dict:
    image_metadata = load_recipe_image_metadata(root).get("recipes", {})
    sources = []
    recipes = []
    errors = []
    for path in recipe_markdown_paths(root):
        stat = path.stat()
        sources.append(
            {
                "filename": path.name,
                "size": stat.st_size,
                "mtime_ns": stat.st_mtime_ns,
            }
        )
        try:
            recipes.append(
                _recipe_record(
                    path,
                    root,
                    stat.st_size,
                    stat.st_mtime_ns,
                    image_metadata,
                )
            )
        except ValueError as error:
            errors.append({"filename": path.name, "error": str(error)})
    return {
        "schema_version": SCHEMA_VERSION,
        "recipes": recipes,
        "sources": sources,
        "errors": errors,
    }


def recipe_cache_is_fresh(document: dict, *, root: Path = ROOT) -> bool:
    if document.get("schema_version") != SCHEMA_VERSION:
        return False
    cached_sources = document.get("sources")
    if not isinstance(cached_sources, list):
        return False
    current_paths = recipe_markdown_paths(root)
    if len(cached_sources) != len(current_paths):
        return False
    by_filename = {}
    for item in cached_sources:
        if not isinstance(item, dict):
            return False
        filename = item.get("filename")
        if not isinstance(filename, str):
            return False
        by_filename[filename] = item
    if len(by_filename) != len(current_paths):
        return False
    for path in current_paths:
        cached = by_filename.get(path.name)
        if cached is None:
            return False
        stat = path.stat()
        if (
            cached.get("size") != stat.st_size
            or cached.get("mtime_ns") != stat.st_mtime_ns
        ):
            return False
    return True


def _recipe_record(
    path: Path,
    root: Path,
    source_size: int,
    source_mtime_ns: int,
    image_metadata: dict[str, dict],
) -> dict:
    metadata, body = split_recipe(path)
    return {
        "id": metadata["id"],
        "name": metadata["name"],
        "revision": metadata["revision"],
        "status": metadata["status"],
        "protein": metadata["protein"],
        "meal_scope": metadata.get("meal_scope", "complete-meal"),
        "prep_minutes": _prep_minutes(body),
        "cook_minutes": metadata["cook_time_minutes"],
        "fiber_grams": metadata["fiber_grams"],
        "estimated_cost_usd": metadata["estimated_cost_usd"],
        "kid_friendly_score": metadata["kid_friendly_score"],
        "kid_friendly_reason": str(metadata.get("kid_friendly_reason", "")),
        "cooking_method": metadata["cooking_method"],
        "seasons": metadata["seasons"],
        "source": metadata.get("source", "Unknown import source"),
        "path": str(path.relative_to(root)).replace("\\", "/"),
        "relative_path": str(path.relative_to(root)).replace("\\", "/"),
        "filename": path.name,
        "tags": metadata.get("tags", []),
        "leftover_recipe_ids": metadata.get("leftover_recipe_ids", []),
        "servings": metadata.get("servings"),
        "created": metadata.get("created"),
        "updated": metadata.get("updated"),
        "rating_average": metadata.get("rating_average"),
        "ratings_count": metadata.get("ratings_count"),
        "card_sections": {
            "ingredients": _body_section(
                body,
                "## Ingredients",
                "## Directions",
            ),
            "directions": _body_section(
                body,
                "## Directions",
                "## Leftover Plan",
            ),
        },
        "image": image_metadata.get(metadata["id"]),
        "source_size": source_size,
        "source_mtime_ns": source_mtime_ns,
    }


def _prep_minutes(body: str) -> int:
    match = re.search(
        r"(?mi)^-\s+\*\*Active prep:\*\*\s*(\d+)\s+minutes?\s*$",
        body,
    )
    return int(match.group(1)) if match else 0


def _body_section(body: str, heading: str, next_heading: str) -> str:
    match = re.search(
        rf"(?ms)^{re.escape(heading)}\s*\n(.*?)(?=^{re.escape(next_heading)}\s*$)",
        body,
    )
    if match is None and heading == "## Ingredients":
        legacy = re.search(
            rf"(?ms)^### Ingredients\s*\n"
            rf"(.*?)(?=^{re.escape(next_heading)}\s*$)",
            body,
        )
        if legacy is not None:
            return legacy.group(1).strip()
        legacy = re.search(
            rf"(?ms)^(### Main Ingredients)\s*\n"
            rf"(.*?)(?=^{re.escape(next_heading)}\s*$)",
            body,
        )
        if legacy is not None:
            return (legacy.group(1) + "\n" + legacy.group(2)).strip()
    if match is None:
        raise ValueError(f"Recipe body is missing {heading}")
    return match.group(1).strip()
