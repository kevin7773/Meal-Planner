from __future__ import annotations


STATIC_REASONS = {
    "RULE-ACTIVE-STATUS": (
        "inactive_status",
        "Recipe is inactive or retired.",
    ),
    "RULE-GENERATED-DAY": (
        "different_generated_day",
        "Generated idea belongs to a different day.",
    ),
    "RULE-MEXICAN-MONDAY": (
        "mexican_monday",
        "Recipe does not satisfy the Mexican Monday rule.",
    ),
    "RULE-TUESDAY-LOW-EFFORT": (
        "tuesday_low_effort",
        "Cooking method does not satisfy Tuesday's low-effort rule.",
    ),
    "RULE-THURSDAY-LOW-EFFORT": (
        "thursday_low_effort",
        "Cooking method does not satisfy Thursday's low-effort rule.",
    ),
    "RULE-SEASON": (
        "season",
        "Recipe is not approved for the planning season.",
    ),
    "RULE-WEATHER": (
        "weather",
        "Recipe conflicts with the active weather rules.",
    ),
}
CONSTRAINT_REASONS = {
    "duplicate_recipe": (
        "duplicate_recipe",
        "Recipe was already selected for another day this week.",
    ),
    "protein_cap": (
        "protein_cap",
        "Recipe would exceed the weekly protein cap.",
    ),
    "user_idea_cap": (
        "queued_idea_cap",
        "Recipe would exceed the queued-idea limit.",
    ),
    "option_overlap": (
        "option_overlap",
        "Recipe would exceed the overlap limit between proposals.",
    ),
}


def explain_planning_trace(trace: dict) -> dict:
    decisions = 0
    explained = 0
    for day in trace.get("days", []):
        selected_id = day.get("selected_recipe_id")
        selected = next(
            (
                candidate
                for candidate in day.get("candidates", [])
                if candidate.get("recipe_id") == selected_id
            ),
            {},
        )
        for candidate in day.get("candidates", []):
            decisions += 1
            outcome = candidate.get("outcome")
            if candidate.get("recipe_id") == selected_id or outcome == "selected":
                candidate.update(
                    decision="Selected",
                    reason_code="selected",
                    reason=(
                        "Selected as the winning viable assignment for this day."
                        if candidate.get("rank") is not None
                        else "Selected by a fixed human override."
                    ),
                )
            elif outcome == "filtered":
                reason_code, reason = STATIC_REASONS.get(
                    candidate.get("stopped_rule_id"),
                    (
                        "eligibility_filter",
                        f"Recipe was removed by {candidate.get('stopped_at')}.",
                    ),
                )
                candidate.update(
                    decision="Rejected",
                    reason_code=reason_code,
                    reason=reason,
                )
            elif outcome == "constraint_rejected":
                reason_code, reason = CONSTRAINT_REASONS.get(
                    candidate.get("constraint_reason"),
                    (
                        "constraint",
                        "Recipe failed a weekly assignment constraint.",
                    ),
                )
                candidate.update(
                    decision="Rejected",
                    reason_code=reason_code,
                    reason=reason,
                )
            elif outcome == "backtracked":
                candidate.update(
                    decision="Rejected",
                    reason_code="backtracked_dead_end",
                    reason=(
                        "Recipe was tried, but it left no valid assignment for "
                        "the remaining days."
                    ),
                )
            elif (
                candidate.get("recent_repeat")
                and not selected.get("recent_repeat")
            ):
                candidate.update(
                    decision="Rejected",
                    reason_code="recent_rotation",
                    reason=(
                        "Recent rotation preference favored a recipe not used "
                        "within the rotation window."
                    ),
                )
            elif (
                candidate.get("inventory_score") is not None
                and selected.get("inventory_score") is not None
                and candidate["inventory_score"] < selected["inventory_score"]
            ):
                candidate.update(
                    decision="Rejected",
                    reason_code="inventory_ranking",
                    reason=(
                        "Lower inventory match than the selected recipe "
                        f"({candidate['inventory_score']}/100 vs "
                        f"{selected['inventory_score']}/100)."
                    ),
                )
            else:
                candidate.update(
                    decision="Rejected",
                    reason_code="lower_ranking",
                    reason=(
                        "Ranked below the selected recipe after rotation, "
                        "inventory, diversity, and review priorities."
                    ),
                )
            if candidate.get("reason"):
                explained += 1
    score = round(explained / decisions * 100, 1) if decisions else 100.0
    result = {
        "score": score,
        "decisions": decisions,
        "explained": explained,
        "unexplained": decisions - explained,
    }
    trace["explainability"] = result
    return result
