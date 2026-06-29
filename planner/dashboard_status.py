from __future__ import annotations

import datetime as dt
import json
from collections import Counter
from pathlib import Path

from planner.constants import ROOT
from planner.performance_gate import (
    evaluate_performance,
    load_baseline,
    report_metrics,
)
from scripts.inventory import load_inventory, parse_date, validate_inventory
from scripts.menu_status import split_menu
from scripts.validate_recipes import split_recipe, validate_recipe


RECIPE_EXCLUSIONS = {"README.md", "index.md", "_template.md"}


def build_dashboard_status(
    root: Path = ROOT,
    *,
    today: dt.date | None = None,
) -> dict:
    today = today or dt.date.today()
    collectors = [
        ("validation", "Validation", lambda: validation_status(root)),
        ("simulation", "Simulation", lambda: simulation_status(root)),
        ("recipes", "Recipe Library", lambda: recipe_count_status(root)),
        (
            "inventory",
            "Inventory",
            lambda: inventory_warning_status(root, today=today),
        ),
        ("menu", "Next Menu", lambda: next_menu_status(root, today=today)),
        ("backup", "Latest Backup", lambda: latest_backup_status(root)),
    ]
    items = []
    for key, label, collector in collectors:
        try:
            items.append(collector())
        except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError):
            items.append(
                status_item(
                    key,
                    label,
                    "Unavailable",
                    "Status source could not be evaluated",
                    "error",
                )
            )
    return {
        "schema_version": 1,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "items": items,
    }


def validation_status(root: Path) -> dict:
    recipe_errors: list[str] = []
    recipe_count = 0
    for path in recipe_paths(root):
        recipe_count += 1
        _, _, _, errors = validate_recipe(path)
        recipe_errors.extend(f"{path.name}: {error}" for error in errors)
    inventory_errors = validate_inventory(root)
    errors = recipe_errors + inventory_errors
    return status_item(
        "validation",
        "Validation",
        "Passed" if not errors else "Failed",
        (
            f"{recipe_count} recipes and inventory passed"
            if not errors
            else f"{len(errors)} validation error(s)"
        ),
        "success" if not errors else "error",
    )


def simulation_status(root: Path) -> dict:
    report_candidates = sorted(
        (root / "reports").glob("*.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    baseline_path = root / "planner-data" / "performance-baseline.json"
    report_path = None
    report = None
    for candidate in report_candidates:
        try:
            document = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if "simulation" in document and "results" in document:
            report_path = candidate
            report = document
            break
    if report_path is None or report is None:
        return status_item(
            "simulation",
            "Simulation",
            "Not run",
            "No deterministic simulation report found",
            "warning",
        )
    try:
        baseline = load_baseline(baseline_path)
        metrics = report_metrics(report)
        checks = evaluate_performance(metrics, baseline)
        failed = [check for check in checks if not check["passed"]]
        iterations = int(report["simulation"]["iterations"])
        successful = int(report["results"]["successful_weeks"])
        report_date = dt.datetime.fromtimestamp(
            report_path.stat().st_mtime
        ).strftime("%b %d")
        if failed:
            return status_item(
                "simulation",
                "Simulation",
                "Regression",
                f"{len(failed)} gate failure(s) | {iterations:,} weeks",
                "error",
            )
        stale = latest_simulation_input_mtime(root) > report_path.stat().st_mtime
        return status_item(
            "simulation",
            "Simulation",
            "Stale" if stale else "Passed",
            f"{successful:,}/{iterations:,} weeks | report {report_date}",
            "warning" if stale else "success",
        )
    except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError):
        return status_item(
            "simulation",
            "Simulation",
            "Invalid",
            "Latest report or baseline could not be evaluated",
            "error",
        )


def latest_simulation_input_mtime(root: Path) -> float:
    patterns = (
        "planner/**/*.py",
        "planner-data/*.json",
        "recipes/*.md",
        "inventory/*.json",
        "preferences/*.json",
        "quick-meals/*.json",
        "sides/*.json",
    )
    mtimes = [
        path.stat().st_mtime
        for pattern in patterns
        for path in root.glob(pattern)
        if path.is_file()
    ]
    return max(mtimes, default=0.0)


def recipe_count_status(root: Path) -> dict:
    counts: Counter[str] = Counter()
    for path in recipe_paths(root):
        metadata, _ = split_recipe(path)
        counts[str(metadata.get("status", "unknown"))] += 1
    total = sum(counts.values())
    return status_item(
        "recipes",
        "Recipe Library",
        f"{total} recipes",
        (
            f"{counts['candidate']} candidate | "
            f"{counts['approved']} approved | "
            f"{counts['retired']} retired"
        ),
        "success",
    )


def inventory_warning_status(root: Path, *, today: dt.date) -> dict:
    catalog, stock, _ = load_inventory(root)
    lots = list(stock.get("items", []))
    quantities: Counter[str] = Counter()
    low = 0
    expiring = 0
    expired = 0
    for lot in lots:
        item_id = str(lot.get("item_id", ""))
        quantity = lot.get("quantity")
        if isinstance(quantity, (int, float)):
            quantities[item_id] += float(quantity)
        if lot.get("level") == "low":
            low += 1
        expiration = parse_date(lot.get("expires_on"))
        if expiration is None:
            continue
        if expiration < today:
            expired += 1
        elif expiration <= today + dt.timedelta(days=7):
            expiring += 1
    below_minimum = sum(
        1
        for item_id, item in catalog.items()
        if float(item.get("minimum", 0)) > quantities[item_id]
    )
    warning_count = low + below_minimum + expiring + expired
    detail = (
        f"{low + below_minimum} low | "
        f"{expiring} expiring | {expired} expired"
    )
    return status_item(
        "inventory",
        "Inventory",
        "Ready" if warning_count == 0 else f"{warning_count} warning(s)",
        detail,
        "error" if expired else ("warning" if warning_count else "success"),
    )


def next_menu_status(root: Path, *, today: dt.date) -> dict:
    current_monday = today - dt.timedelta(days=today.weekday())
    menus: list[tuple[dt.date, Path]] = []
    for path in (root / "menus").glob("*/*.md"):
        try:
            week = dt.date.fromisoformat(path.stem)
        except ValueError:
            continue
        if week >= current_monday:
            menus.append((week, path))
    if not menus:
        return status_item(
            "menu",
            "Next Menu",
            "Not planned",
            f"No menu from {current_monday.strftime('%b %d')} onward",
            "warning",
        )
    week, path = min(menus, key=lambda item: item[0])
    try:
        metadata, _ = split_menu(path)
        planning_status = str(metadata["status"])
    except (KeyError, OSError, ValueError):
        return status_item(
            "menu",
            "Next Menu",
            "Invalid",
            f"Week of {week.strftime('%b %d, %Y')}",
            "error",
        )
    state = (
        "success"
        if planning_status in {"approved", "completed", "archived"}
        else "warning"
        if planning_status in {"draft", "generated"}
        else "info"
    )
    return status_item(
        "menu",
        "Next Menu",
        planning_status.title(),
        f"Week of {week.strftime('%b %d, %Y')}",
        state,
    )


def latest_backup_status(root: Path) -> dict:
    manifests: list[tuple[dt.datetime, dict]] = []
    for path in (root / ".backup").glob("*/manifest.json"):
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
            created_at = dt.datetime.fromisoformat(document["created_at"])
            manifests.append((created_at, document))
        except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError):
            continue
    if not manifests:
        return status_item(
            "backup",
            "Latest Backup",
            "None",
            "No GUI pre-write backup found",
            "warning",
        )
    created_at, document = max(manifests, key=lambda item: item[0])
    local_time = created_at.astimezone()
    age = dt.datetime.now(dt.timezone.utc) - created_at.astimezone(
        dt.timezone.utc
    )
    return status_item(
        "backup",
        "Latest Backup",
        local_time.strftime("%b %d, %I:%M %p").replace(" 0", " "),
        (
            f"{document.get('operation', 'unknown operation')} | "
            f"{int(document.get('file_count', 0))} files"
        ),
        "success" if age <= dt.timedelta(days=7) else "warning",
    )


def recipe_paths(root: Path) -> list[Path]:
    return [
        path
        for path in sorted((root / "recipes").glob("*.md"))
        if path.name not in RECIPE_EXCLUSIONS
    ]


def status_item(
    key: str,
    label: str,
    value: str,
    detail: str,
    state: str,
) -> dict:
    return {
        "key": key,
        "label": label,
        "value": value,
        "detail": detail,
        "state": state,
    }
