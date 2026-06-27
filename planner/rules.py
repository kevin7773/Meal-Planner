from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path

from planner.constants import ROOT
from scripts.schema_version import schema_version_errors


RULE_ID_PATTERN = re.compile(r"^RULE-[A-Z0-9-]+$")


def rule_registry_path(root: Path = ROOT) -> Path:
    return root / "planner-data" / "planning-rules.json"


def load_rule_document(root: Path = ROOT) -> dict:
    return json.loads(rule_registry_path(root).read_text(encoding="utf-8"))


def load_rules(root: Path = ROOT) -> list[dict]:
    return load_rule_document(root)["rules"]


def validate_rules(root: Path = ROOT) -> list[str]:
    try:
        document = load_rule_document(root)
    except (OSError, json.JSONDecodeError) as exc:
        return [f"unable to load planning rules: {exc}"]
    errors = schema_version_errors(
        document,
        "planner-data/planning-rules.json",
    )
    if errors:
        return errors
    rules = document.get("rules")
    if not isinstance(rules, list):
        return ["planning rules must be an array"]
    seen: set[str] = set()
    for rule in rules:
        if not isinstance(rule, dict):
            errors.append("planning rule must be an object")
            continue
        rule_id = rule.get("id")
        if not isinstance(rule_id, str) or not RULE_ID_PATTERN.fullmatch(rule_id):
            errors.append("planning rule has an invalid ID")
            continue
        if rule_id in seen:
            errors.append(f"duplicate planning rule ID: {rule_id}")
        seen.add(rule_id)
        if not str(rule.get("name", "")).strip():
            errors.append(f"{rule_id}: name is required")
        if not str(rule.get("category", "")).strip():
            errors.append(f"{rule_id}: category is required")
        references = rule.get("test_references")
        if not isinstance(references, list) or not references:
            errors.append(f"{rule_id}: at least one test reference is required")
            continue
        for reference in references:
            if not isinstance(reference, str) or "::" not in reference:
                errors.append(f"{rule_id}: invalid test reference {reference}")
                continue
            path_text, test_name = reference.split("::", 1)
            path = root / path_text
            if not path.exists():
                errors.append(f"{rule_id}: missing test file {path_text}")
                continue
            if not re.fullmatch(r"test_[a-z0-9_]+", test_name):
                errors.append(f"{rule_id}: invalid test name {test_name}")
                continue
            source = path.read_text(encoding="utf-8")
            if re.search(rf"(?m)^\s*def {re.escape(test_name)}\(", source) is None:
                errors.append(
                    f"{rule_id}: test reference not found: {reference}"
                )
    telemetry_path = root / "telemetry" / "planner-telemetry.json"
    if telemetry_path.exists():
        try:
            telemetry = json.loads(telemetry_path.read_text(encoding="utf-8"))
            usage_by_month = (
                telemetry.get("aggregate", {}).get("rule_usage_by_month", {})
            )
            used_ids = {
                rule_id
                for usage in usage_by_month.values()
                if isinstance(usage, dict)
                for rule_id in usage
            }
            unknown = sorted(used_ids - seen)
            if unknown:
                errors.append(
                    "telemetry references unregistered rules: "
                    + ", ".join(unknown)
                )
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"unable to inspect telemetry rule usage: {exc}")
    return errors


def rule_coverage_summary(
    telemetry_document: dict,
    rules: list[dict],
    *,
    month: str | None = None,
) -> dict:
    selected_month = month or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m")
    usage = (
        telemetry_document.get("aggregate", {})
        .get("rule_usage_by_month", {})
        .get(selected_month, {})
    )
    used_ids = {
        rule_id for rule_id, count in usage.items() if int(count) > 0
    }
    registered_ids = {rule["id"] for rule in rules}
    unused = [
        {
            "id": rule["id"],
            "name": rule["name"],
            "category": rule["category"],
        }
        for rule in rules
        if rule["id"] not in used_ids
    ]
    return {
        "month": selected_month,
        "rules": len(rules),
        "rules_tested": sum(bool(rule.get("test_references")) for rule in rules),
        "rules_used_this_month": len(registered_ids & used_ids),
        "unused_rules": unused,
        "usage_counts": {
            rule_id: int(usage.get(rule_id, 0))
            for rule_id in sorted(registered_ids)
        },
    }


def format_rule_coverage(summary: dict) -> str:
    lines = [
        "Rule Coverage",
        "",
        f"Month: {summary['month']}",
        f"Rules: {summary['rules']}",
        f"Rules tested: {summary['rules_tested']}",
        f"Rules used this month: {summary['rules_used_this_month']}",
        f"Unused rules: {len(summary['unused_rules'])}",
    ]
    if summary["unused_rules"]:
        lines.extend(["", "Unused Rules"])
        lines.extend(
            f"- {rule['id']}: {rule['name']} [{rule['category']}]"
            for rule in summary["unused_rules"]
        )
    return "\n".join(lines)
