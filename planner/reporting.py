from __future__ import annotations


def proposal_report(proposal: dict, number: int | None = None) -> str:
    title = f"Option {number}" if number is not None else "Dry Run"
    lines = [
        title,
        f"Week of: {proposal['week_of']}",
        f"Estimated cost: ${proposal['estimated_cost_usd']:.2f}",
        f"After inventory: ${proposal['estimated_shopping_cost_usd']:.2f}",
        f"Inventory coverage: {proposal['inventory_coverage_score']}/100",
        f"Average fiber: {proposal['average_fiber_grams']:.1f} g/serving",
        f"Kid-friendly score: {proposal['average_kid_friendly_score']:.1f}/5",
        f"Recipe rotation score: {proposal['rotation_score']}/100",
        (
            f"Weather: {proposal['weather_category']} "
            f"({proposal['heat_friendly_meals']} heat-friendly meals)"
        ),
        "",
    ]
    for meal in proposal["meals"]:
        lines.append(
            f"{meal['day']}: {meal['recipe_id']} rev {meal['revision']} - "
            f"{meal['name']} [{meal['cooking_method']}]"
        )
        lines.append(f"  Kid-friendly: {meal['kid_friendly_reason']}")
        lines.append("  Why selected:")
        lines.extend(
            f"    - {reason}"
            for reason in meal["selection_explanation"]["reasons"]
        )
        if meal["side_suggestions"]:
            lines.append(
                "  Suggested sides: "
                + "; ".join(
                    f"{side['name']} ({side['fiber_grams']}g fiber)"
                    for side in meal["side_suggestions"]
                )
            )
        if meal["kids_quick_meal"]:
            quick_meal = meal["kids_quick_meal"]
            lines.append(
                f"  Kids' quick meal: {quick_meal['name']} "
                f"({quick_meal['id']}, ${quick_meal['estimated_cost_usd']:.2f})"
            )
    if proposal["errors"]:
        lines.extend(["", "BLOCKING ERRORS"])
        lines.extend(f"- {error}" for error in proposal["errors"])
    if proposal["warnings"]:
        lines.extend(["", "WARNINGS"])
        lines.extend(f"- {warning}" for warning in proposal["warnings"])
    if proposal["inventory_warnings"]:
        lines.extend(["", "INVENTORY WARNINGS"])
        lines.extend(f"- {warning}" for warning in proposal["inventory_warnings"])
    lines.extend(["", "No files were written."])
    return "\n".join(lines)
