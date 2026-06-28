from __future__ import annotations

import json
from pathlib import Path

from planner.constants import ROOT
from scripts.validate_recipes import split_recipe


def inventory_mapping_report(root: Path = ROOT) -> dict:
    catalog_document = json.loads(
        (root / "inventory" / "catalog.json").read_text(encoding="utf-8")
    )
    requirement_document = json.loads(
        (root / "inventory" / "recipe-requirements.json").read_text(
            encoding="utf-8"
        )
    )
    catalog_ids = {
        str(item["id"])
        for item in catalog_document.get("items", [])
    }
    requirement_sets = requirement_document.get("recipes", {})
    recipes = []
    for path in sorted((root / "recipes").glob("*.md")):
        if path.name.startswith("_") or path.name in {
            "README.md",
            "index.md",
        }:
            continue
        metadata, _ = split_recipe(path)
        recipe_id = str(metadata["id"])
        requirements = requirement_sets.get(recipe_id, [])
        unknown_ids = sorted(
            {
                str(requirement.get("item_id"))
                for requirement in requirements
                if requirement.get("item_id") not in catalog_ids
            }
        )
        recipes.append(
            {
                "id": recipe_id,
                "name": str(metadata["name"]),
                "status": str(metadata["status"]),
                "mapped_item_count": len(requirements),
                "missing_mapping": not requirements,
                "unknown_item_ids": unknown_ids,
            }
        )
    active = [
        recipe for recipe in recipes
        if recipe["status"] != "retired"
    ]
    mapped = [
        recipe for recipe in active
        if not recipe["missing_mapping"]
    ]
    missing = [
        recipe for recipe in active
        if recipe["missing_mapping"]
    ]
    invalid = [
        recipe for recipe in recipes
        if recipe["unknown_item_ids"]
    ]
    completeness = (
        round(len(mapped) / len(active) * 100, 1)
        if active
        else 100.0
    )
    return {
        "schema_version": 1,
        "total_recipes": len(recipes),
        "active_recipes": len(active),
        "mapped_recipes": len(mapped),
        "missing_mapping_count": len(missing),
        "mapping_completeness_percent": completeness,
        "missing_mappings": missing,
        "invalid_mappings": invalid,
        "recipes": recipes,
    }


def format_inventory_mapping_report(report: dict) -> str:
    lines = [
        "INGREDIENT MAPPING COMPLETENESS",
        "",
        (
            f"Mapped active recipes: {report['mapped_recipes']}/"
            f"{report['active_recipes']} "
            f"({report['mapping_completeness_percent']:.1f}%)"
        ),
        f"Missing mappings: {report['missing_mapping_count']}",
        f"Invalid catalog references: {len(report['invalid_mappings'])}",
        "",
        "RECIPES MISSING INVENTORY MAPPINGS",
    ]
    if report["missing_mappings"]:
        lines.extend(
            f"- {recipe['id']} | {recipe['name']} | {recipe['status']}"
            for recipe in report["missing_mappings"]
        )
    else:
        lines.append("- None")
    lines.extend(["", "INVALID CATALOG REFERENCES"])
    if report["invalid_mappings"]:
        lines.extend(
            f"- {recipe['id']} | {recipe['name']}: "
            + ", ".join(recipe["unknown_item_ids"])
            for recipe in report["invalid_mappings"]
        )
    else:
        lines.append("- None")
    return "\n".join(lines)
