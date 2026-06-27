from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VALID_CLASSES = {
    "staple",
    "pantry",
    "refrigerated",
    "frozen",
    "fresh-produce",
    "consumable",
}
VALID_LEVELS = {"full", "half", "low"}
LEVEL_COVERAGE = {"full": 1.0, "half": 0.5, "low": 0.15}


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_inventory(root: Path = ROOT) -> tuple[dict[str, dict], dict, dict[str, list[dict]]]:
    inventory_root = root / "inventory"
    catalog_document = read_json(inventory_root / "catalog.json")
    stock = read_json(inventory_root / "stock.json")
    requirements_document = read_json(inventory_root / "recipe-requirements.json")
    catalog = {item["id"]: item for item in catalog_document["items"]}
    return catalog, stock, requirements_document["recipes"]


def parse_date(value: object) -> dt.date | None:
    if value in {None, ""}:
        return None
    if not isinstance(value, str):
        return None
    try:
        return dt.date.fromisoformat(value)
    except ValueError:
        return None


def validate_inventory(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    try:
        catalog_document = read_json(root / "inventory" / "catalog.json")
        stock = read_json(root / "inventory" / "stock.json")
        requirements_document = read_json(
            root / "inventory" / "recipe-requirements.json"
        )
    except (OSError, json.JSONDecodeError, KeyError) as exc:
        return [f"unable to load inventory data: {exc}"]

    catalog_items = catalog_document.get("items")
    if not isinstance(catalog_items, list):
        return ["catalog items must be an array"]
    catalog: dict[str, dict] = {}
    for item in catalog_items:
        item_id = item.get("id")
        if not isinstance(item_id, str) or not item_id:
            errors.append("catalog item has an invalid id")
            continue
        if item_id in catalog:
            errors.append(f"duplicate catalog item: {item_id}")
        catalog[item_id] = item
        if item.get("class") not in VALID_CLASSES:
            errors.append(f"{item_id}: invalid ingredient class")
        if not isinstance(item.get("unit"), str) or not item["unit"]:
            errors.append(f"{item_id}: unit is required")
        if not isinstance(item.get("minimum"), (int, float)) or item["minimum"] < 0:
            errors.append(f"{item_id}: minimum must be non-negative")
        if (
            not isinstance(item.get("unit_cost_usd"), (int, float))
            or item["unit_cost_usd"] < 0
        ):
            errors.append(f"{item_id}: unit_cost_usd must be non-negative")
        if item.get("class") == "consumable" and item.get("unit") != "level":
            errors.append(f"{item_id}: consumables must use level units")

    lots = stock.get("items")
    if not isinstance(lots, list):
        errors.append("stock items must be an array")
        lots = []
    seen_lots: set[str] = set()
    seen_consumables: set[str] = set()
    for lot in lots:
        lot_id = lot.get("lot_id")
        item_id = lot.get("item_id")
        if not isinstance(lot_id, str) or not lot_id:
            errors.append("stock lot has an invalid lot_id")
        elif lot_id in seen_lots:
            errors.append(f"duplicate stock lot: {lot_id}")
        else:
            seen_lots.add(lot_id)
        if item_id not in catalog:
            errors.append(f"{lot_id}: unknown catalog item {item_id}")
            continue
        item_class = catalog[item_id]["class"]
        if item_class == "consumable":
            if lot.get("level") not in VALID_LEVELS:
                errors.append(f"{lot_id}: consumable level must be full, half, or low")
            if item_id in seen_consumables:
                errors.append(f"{item_id}: consumable must have only one stock entry")
            seen_consumables.add(item_id)
        elif (
            not isinstance(lot.get("quantity"), (int, float))
            or lot.get("quantity", 0) < 0
        ):
            errors.append(f"{lot_id}: quantity must be non-negative")
        if item_class in {"frozen", "fresh-produce"} and parse_date(
            lot.get("acquired_on")
        ) is None:
            errors.append(f"{lot_id}: {item_class} stock requires acquired_on")
        if item_class == "refrigerated" and parse_date(lot.get("expires_on")) is None:
            errors.append(f"{lot_id}: refrigerated stock requires expires_on")
        for date_field in ("acquired_on", "expires_on"):
            value = lot.get(date_field)
            if value not in {None, ""} and parse_date(value) is None:
                errors.append(f"{lot_id}: invalid {date_field}")

    requirements = requirements_document.get("recipes")
    if not isinstance(requirements, dict):
        errors.append("recipe requirements must be an object")
        requirements = {}

    recipe_ids: set[str] = set()
    try:
        from scripts.validate_recipes import split_recipe
    except ModuleNotFoundError:
        from validate_recipes import split_recipe
    for path in (root / "recipes").glob("*.md"):
        if path.name.startswith("_") or path.name in {"README.md", "index.md"}:
            continue
        metadata, _ = split_recipe(path)
        recipe_ids.add(metadata["id"])

    for recipe_id in sorted(recipe_ids - set(requirements)):
        errors.append(f"{recipe_id}: missing inventory requirements")
    for recipe_id in sorted(set(requirements) - recipe_ids):
        errors.append(f"{recipe_id}: requirements reference unknown recipe")
    for recipe_id, entries in requirements.items():
        if not isinstance(entries, list):
            errors.append(f"{recipe_id}: requirements must be an array")
            continue
        seen_items: set[str] = set()
        for entry in entries:
            item_id = entry.get("item_id")
            quantity = entry.get("quantity")
            if item_id not in catalog:
                errors.append(f"{recipe_id}: unknown ingredient {item_id}")
            if item_id in seen_items:
                errors.append(f"{recipe_id}: duplicate ingredient {item_id}")
            seen_items.add(item_id)
            if not isinstance(quantity, (int, float)) or quantity <= 0:
                errors.append(f"{recipe_id}/{item_id}: quantity must be positive")

    return errors


def usable_lots(
    item_id: str,
    catalog: dict[str, dict],
    stock: dict,
    *,
    as_of: dt.date,
    week_of: dt.date,
) -> list[dict]:
    item_class = catalog[item_id]["class"]
    lots = [lot for lot in stock.get("items", []) if lot.get("item_id") == item_id]
    usable: list[dict] = []
    for lot in lots:
        expires_on = parse_date(lot.get("expires_on"))
        acquired_on = parse_date(lot.get("acquired_on"))
        if expires_on is not None and expires_on < as_of:
            continue
        if item_class == "fresh-produce" and (
            acquired_on is None or acquired_on < week_of
        ):
            continue
        usable.append(lot)
    if item_class == "frozen":
        usable.sort(key=lambda lot: parse_date(lot.get("acquired_on")) or dt.date.max)
    return usable


def assess_inventory(
    requirements: list[dict],
    *,
    root: Path = ROOT,
    as_of: dt.date | None = None,
    week_of: dt.date | None = None,
) -> dict:
    catalog, stock, _ = load_inventory(root)
    as_of = as_of or dt.date.today()
    week_of = week_of or as_of
    totals: collections.Counter[str] = collections.Counter()
    for requirement in requirements:
        totals[requirement["item_id"]] += float(requirement["quantity"])

    weighted_required = 0.0
    weighted_covered = 0.0
    estimated_savings = 0.0
    buy: list[dict] = []
    warnings: list[str] = []

    for item_id, required in sorted(totals.items()):
        item = catalog.get(item_id)
        if item is None:
            warnings.append(f"Unknown inventory ingredient: {item_id}")
            continue
        item_class = item["class"]
        lots = usable_lots(
            item_id,
            catalog,
            stock,
            as_of=as_of,
            week_of=week_of,
        )
        if item_class == "fresh-produce":
            buy.append(
                {
                    "item_id": item_id,
                    "name": item["name"],
                    "quantity": required,
                    "unit": item["unit"],
                    "reason": "fresh weekly purchase",
                }
            )
            continue
        if item_class == "consumable":
            level = lots[-1].get("level") if lots else None
            coverage = LEVEL_COVERAGE.get(level, 0.0)
            weighted_required += 1
            weighted_covered += coverage
            if level in {None, "low"}:
                warnings.append(f"{item['name']} is {level or 'not recorded'}")
            continue

        available = sum(float(lot.get("quantity", 0)) for lot in lots)
        covered = min(required, available)
        weighted_required += required
        weighted_covered += covered
        estimated_savings += covered * float(item["unit_cost_usd"])
        if available < required:
            buy.append(
                {
                    "item_id": item_id,
                    "name": item["name"],
                    "quantity": round(required - available, 2),
                    "unit": item["unit"],
                    "reason": "insufficient stock",
                }
            )

    for item in catalog.values():
        if item["class"] != "staple":
            continue
        available = sum(
            float(lot.get("quantity", 0))
            for lot in usable_lots(
                item["id"],
                catalog,
                stock,
                as_of=as_of,
                week_of=week_of,
            )
        )
        if available < float(item["minimum"]):
            warnings.append(
                f"Staple below minimum: {item['name']} "
                f"({available:g} {item['unit']}, minimum {item['minimum']:g})"
            )

    coverage_score = (
        round(weighted_covered / weighted_required * 100)
        if weighted_required
        else 100
    )
    return {
        "coverage_score": coverage_score,
        "estimated_savings_usd": round(estimated_savings, 2),
        "buy": buy,
        "warnings": warnings,
    }


def fifo_plan(item_id: str, quantity: float, *, root: Path = ROOT) -> list[dict]:
    catalog, stock, _ = load_inventory(root)
    if item_id not in catalog or catalog[item_id]["class"] != "frozen":
        raise ValueError("FIFO plans apply only to frozen ingredients")
    lots = usable_lots(
        item_id,
        catalog,
        stock,
        as_of=dt.date.today(),
        week_of=dt.date.today(),
    )
    remaining = quantity
    plan: list[dict] = []
    for lot in lots:
        take = min(remaining, float(lot.get("quantity", 0)))
        if take > 0:
            plan.append({"lot_id": lot["lot_id"], "quantity": take})
            remaining -= take
        if remaining <= 0:
            break
    return plan


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate and inspect kitchen inventory.")
    parser.add_argument("command", choices=("validate", "summary"))
    args = parser.parse_args()
    errors = validate_inventory()
    if errors:
        print("Inventory validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    if args.command == "validate":
        print("Inventory catalog, stock, and recipe requirements are valid.")
        return 0
    catalog, stock, requirements = load_inventory()
    print(
        f"{len(catalog)} catalog items, {len(stock['items'])} stock lots, "
        f"{len(requirements)} recipe requirement sets."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
