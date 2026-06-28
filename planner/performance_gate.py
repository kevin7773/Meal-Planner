from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from planner.constants import ROOT
from planner.simulation import run_simulation


BASELINE_PATH = ROOT / "planner-data" / "performance-baseline.json"
REQUIRED_METRICS = {
    "average_grocery_bill_usd",
    "average_fiber_grams",
    "average_inventory_coverage_score",
    "recipe_diversity_percentage",
    "final_constraint_violations",
}
REQUIRED_THRESHOLDS = {
    "max_grocery_cost_increase_percent",
    "minimum_average_fiber_grams",
    "minimum_inventory_coverage_score",
    "minimum_recipe_diversity_percentage",
    "maximum_final_constraint_violations",
}


def load_baseline(path: Path = BASELINE_PATH) -> dict:
    document = json.loads(path.read_text(encoding="utf-8"))
    validate_baseline(document)
    return document


def validate_baseline(document: dict) -> None:
    if not isinstance(document, dict):
        raise ValueError("performance baseline must be a JSON object")
    if document.get("schema_version") != 1:
        raise ValueError("performance baseline schema_version must be 1")

    simulation = document.get("simulation")
    if not isinstance(simulation, dict):
        raise ValueError("performance baseline simulation must be an object")
    required_simulation = {
        "iterations",
        "seed",
        "start_week",
        "horizon_weeks",
        "ranking_variants",
        "search_evaluation_limit",
    }
    missing_simulation = required_simulation - simulation.keys()
    if missing_simulation:
        raise ValueError(
            "performance baseline simulation is missing: "
            + ", ".join(sorted(missing_simulation))
        )
    try:
        start_week = dt.date.fromisoformat(simulation["start_week"])
    except (TypeError, ValueError) as error:
        raise ValueError(
            "performance baseline start_week must be YYYY-MM-DD"
        ) from error
    if start_week.weekday() != 0:
        raise ValueError("performance baseline start_week must be a Monday")
    for key in (
        "iterations",
        "horizon_weeks",
        "ranking_variants",
        "search_evaluation_limit",
    ):
        if not isinstance(simulation[key], int) or simulation[key] < 1:
            raise ValueError(f"performance baseline {key} must be positive")
    if not isinstance(simulation["seed"], int):
        raise ValueError("performance baseline seed must be an integer")

    metrics = document.get("approved_metrics")
    if not isinstance(metrics, dict):
        raise ValueError(
            "performance baseline approved_metrics must be an object"
        )
    missing_metrics = REQUIRED_METRICS - metrics.keys()
    if missing_metrics:
        raise ValueError(
            "performance baseline approved_metrics is missing: "
            + ", ".join(sorted(missing_metrics))
        )

    thresholds = document.get("thresholds")
    if not isinstance(thresholds, dict):
        raise ValueError("performance baseline thresholds must be an object")
    missing_thresholds = REQUIRED_THRESHOLDS - thresholds.keys()
    if missing_thresholds:
        raise ValueError(
            "performance baseline thresholds is missing: "
            + ", ".join(sorted(missing_thresholds))
        )

    for key in REQUIRED_METRICS:
        if not isinstance(metrics[key], (int, float)):
            raise ValueError(
                f"performance baseline metric {key} must be numeric"
            )
    for key in REQUIRED_THRESHOLDS:
        if not isinstance(thresholds[key], (int, float)):
            raise ValueError(
                f"performance baseline threshold {key} must be numeric"
            )


def report_metrics(report: dict) -> dict:
    results = report["results"]
    return {
        "average_grocery_bill_usd": results[
            "average_grocery_bill_usd"
        ],
        "average_fiber_grams": results["average_fiber_grams"],
        "average_inventory_coverage_score": results[
            "average_inventory_coverage_score"
        ],
        "recipe_diversity_percentage": results["recipe_diversity"][
            "percentage"
        ],
        "final_constraint_violations": results[
            "final_constraint_violations"
        ]["total"],
    }


def evaluate_performance(
    current: dict,
    baseline: dict,
) -> list[dict]:
    approved = baseline["approved_metrics"]
    thresholds = baseline["thresholds"]
    checks = []

    cost_limit = round(
        approved["average_grocery_bill_usd"]
        * (
            1
            + thresholds["max_grocery_cost_increase_percent"]
            / 100
        ),
        2,
    )
    checks.append(
        _check(
            "average_grocery_bill_usd",
            current["average_grocery_bill_usd"] <= cost_limit,
            current["average_grocery_bill_usd"],
            f"must be <= ${cost_limit:.2f}",
            approved=approved["average_grocery_bill_usd"],
        )
    )
    checks.append(
        _check(
            "average_fiber_grams",
            current["average_fiber_grams"]
            >= thresholds["minimum_average_fiber_grams"],
            current["average_fiber_grams"],
            (
                "must be >= "
                f"{thresholds['minimum_average_fiber_grams']:.1f} g"
            ),
            approved=approved["average_fiber_grams"],
        )
    )
    checks.append(
        _check(
            "average_inventory_coverage_score",
            current["average_inventory_coverage_score"]
            >= thresholds["minimum_inventory_coverage_score"],
            current["average_inventory_coverage_score"],
            (
                "must be >= "
                f"{thresholds['minimum_inventory_coverage_score']:.1f}/100"
            ),
            approved=approved["average_inventory_coverage_score"],
        )
    )
    checks.append(
        _check(
            "recipe_diversity_percentage",
            current["recipe_diversity_percentage"]
            >= thresholds["minimum_recipe_diversity_percentage"],
            current["recipe_diversity_percentage"],
            (
                "must be >= "
                f"{thresholds['minimum_recipe_diversity_percentage']:.1f}%"
            ),
            approved=approved["recipe_diversity_percentage"],
        )
    )
    checks.append(
        _check(
            "final_constraint_violations",
            current["final_constraint_violations"]
            <= thresholds["maximum_final_constraint_violations"],
            current["final_constraint_violations"],
            (
                "must be <= "
                f"{thresholds['maximum_final_constraint_violations']}"
            ),
            approved=approved["final_constraint_violations"],
        )
    )
    return checks


def _check(
    metric: str,
    passed: bool,
    actual: float,
    requirement: str,
    *,
    approved: float,
) -> dict:
    return {
        "metric": metric,
        "passed": passed,
        "actual": actual,
        "approved": approved,
        "delta": round(actual - approved, 4),
        "requirement": requirement,
    }


def run_performance_gate(
    *,
    baseline_path: Path = BASELINE_PATH,
    root: Path = ROOT,
) -> dict:
    baseline = load_baseline(baseline_path)
    simulation = baseline["simulation"]
    report = run_simulation(
        iterations=simulation["iterations"],
        seed=simulation["seed"],
        start_week=dt.date.fromisoformat(simulation["start_week"]),
        horizon_weeks=simulation["horizon_weeks"],
        ranking_variants=simulation["ranking_variants"],
        search_evaluation_limit=simulation[
            "search_evaluation_limit"
        ],
        root=root,
    )
    metrics = report_metrics(report)
    checks = evaluate_performance(metrics, baseline)
    return {
        "passed": all(check["passed"] for check in checks),
        "metrics": metrics,
        "checks": checks,
        "report": report,
    }


def update_approved_metrics(
    baseline: dict,
    report: dict,
    *,
    reason: str,
) -> dict:
    reason = reason.strip()
    if not reason:
        raise ValueError("baseline update reason cannot be empty")
    updated = dict(baseline)
    updated["approved_metrics"] = report_metrics(report)
    updated["approval"] = {
        "updated_at": dt.datetime.now(dt.timezone.utc)
        .replace(microsecond=0)
        .isoformat(),
        "change_note": reason,
    }
    validate_baseline(updated)
    return updated


def write_baseline(path: Path, document: dict) -> None:
    path.write_text(
        json.dumps(document, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def write_simulation_report(path: Path, report: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
