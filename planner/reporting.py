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
        f"Explainability score: {proposal['explainability_score']:.1f}/100",
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
    trace = proposal.get("planning_trace")
    if trace:
        lines.extend(
            [
                "",
                "PLANNING TRACE",
                (
                    "Candidate recipes available: "
                    f"{trace['candidate_recipes_available']}"
                ),
                f"Candidate evaluations: {trace['candidate_evaluations']}",
                (
                    "Search candidate attempts: "
                    f"{trace['search_candidate_attempts']}"
                ),
                (
                    "Explainability score: "
                    f"{trace['explainability']['score']:.1f}/100 "
                    f"({trace['explainability']['explained']}/"
                    f"{trace['explainability']['decisions']} decisions)"
                ),
                "Search order: " + " -> ".join(trace["search_order"]),
            ]
        )
        for day_trace in trace["days"]:
            lines.extend(["", day_trace["day"], "-" * len(day_trace["day"])])
            lines.append(
                f"Started with {day_trace['started_count']} recipes"
            )
            for stage in day_trace["stages"]:
                suffix = " (sorted)" if stage.get("action") == "sorted" else ""
                lines.append(
                    f"  {stage['name']}: {stage['before']} -> "
                    f"{stage['after']}{suffix}"
                )
            lines.append(
                "  Selected: "
                f"{day_trace['selected_recipe_id']} - "
                f"{day_trace['selected_name']}"
            )
            lines.append("  Candidate decisions:")
            for candidate in day_trace["candidates"]:
                rank = (
                    f"rank {candidate['rank']}, "
                    f"score {candidate['ranking_score']:.1f}/100, "
                    f"inventory {candidate['inventory_score']}/100, "
                    if candidate.get("rank") is not None
                    else ""
                )
                lines.append(
                    f"    - {candidate['recipe_id']} ({candidate['name']}): "
                    f"{rank}{candidate['decision']} - {candidate['reason']}"
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
    lines.extend(["", "No planning artifacts were written."])
    return "\n".join(lines)
