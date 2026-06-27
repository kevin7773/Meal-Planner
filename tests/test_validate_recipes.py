from __future__ import annotations

import unittest

from scripts.validate_recipes import semantic_errors


def valid_metadata() -> dict:
    return {
        "id": "FDP-0001",
        "name": "Grilled Chicken",
        "tags": ["summer", "chicken"],
        "protein": "chicken",
        "fiber_grams": 10,
        "estimated_cost_usd": 20.0,
        "kid_friendly_score": 5,
        "kid_friendly_reason": "Familiar meal with optional toppings",
        "cooking_method": "grill",
        "cook_time_minutes": 20,
        "seasons": ["summer"],
        "leftover_recipe_ids": [],
    }


def recipe_body(
    *,
    method: str = "Grill",
    cook_time: str = "20 minutes",
    fiber: str = "10 grams per serving",
    leftover_plan: str = "- Use leftovers for lunch.",
) -> str:
    return f"""# Grilled Chicken

## Recipe Card

- **Cook time:** {cook_time}
- **Cooking method:** {method}
- **Estimated fiber:** {fiber}
- **Kid-friendly design:** Familiar meal with optional toppings

## Leftover Plan

{leftover_plan}
"""


class SemanticValidationTests(unittest.TestCase):
    def test_valid_recipe_passes(self) -> None:
        self.assertEqual(
            semantic_errors(valid_metadata(), recipe_body(), {"FDP-0001"}),
            [],
        )

    def test_specialty_protein_can_use_other(self) -> None:
        metadata = valid_metadata()
        metadata["protein"] = "other"
        self.assertEqual(
            semantic_errors(metadata, recipe_body(), {"FDP-0001"}),
            [],
        )

    def test_mexican_monday_requires_allowed_protein_and_fiber(self) -> None:
        metadata = valid_metadata()
        metadata.update(
            tags=["summer", "mexican-monday"],
            protein="vegetarian",
            fiber_grams=7,
        )
        errors = semantic_errors(
            metadata,
            recipe_body(fiber="7 grams per serving"),
            {"FDP-0001"},
        )
        self.assertTrue(any("mexican-monday recipes require chicken" in error for error in errors))
        self.assertIn("mexican-monday recipes require at least 8 fiber grams", errors)

    def test_slow_cooker_requires_three_hours(self) -> None:
        metadata = valid_metadata()
        metadata.update(cooking_method="slow-cooker", cook_time_minutes=120)
        errors = semantic_errors(
            metadata,
            recipe_body(method="Slow cooker", cook_time="2 hours"),
            {"FDP-0001"},
        )
        self.assertIn(
            "slow-cooker recipes require at least 180 cook_time_minutes",
            errors,
        )

    def test_active_recipe_requires_kid_friendly_score(self) -> None:
        metadata = valid_metadata()
        metadata["kid_friendly_score"] = 3
        errors = semantic_errors(metadata, recipe_body(), {"FDP-0001"})
        self.assertIn("active recipes require kid_friendly_score of at least 4", errors)

    def test_parents_only_recipe_can_be_stored_with_low_score(self) -> None:
        metadata = valid_metadata()
        metadata["kid_friendly_score"] = 1
        metadata["kid_friendly_reason"] = "Not kid friendly - for the parents only"
        body = recipe_body().replace(
            "Familiar meal with optional toppings",
            "Not kid friendly - for the parents only",
        )
        errors = semantic_errors(metadata, body, {"FDP-0001"})
        self.assertNotIn(
            "active recipes require kid_friendly_score of at least 4",
            errors,
        )

    def test_summer_recipe_rejects_soup_chili_or_stew(self) -> None:
        metadata = valid_metadata()
        metadata["name"] = "Summer Tomato Soup"
        errors = semantic_errors(metadata, recipe_body(), {"FDP-0001"})
        self.assertTrue(any("summer recipes cannot be" in error for error in errors))

    def test_leftover_reference_must_exist(self) -> None:
        metadata = valid_metadata()
        metadata["leftover_recipe_ids"] = ["FDP-9999"]
        errors = semantic_errors(
            metadata,
            recipe_body(leftover_plan="- Reuse in FDP-9999."),
            {"FDP-0001"},
        )
        self.assertIn("leftover recipe does not exist: FDP-9999", errors)

    def test_recipe_card_must_match_metadata(self) -> None:
        errors = semantic_errors(
            valid_metadata(),
            recipe_body(cook_time="15 minutes", fiber="8 grams per serving"),
            {"FDP-0001"},
        )
        self.assertTrue(any("cook_time_minutes is 20" in error for error in errors))
        self.assertTrue(any("fiber_grams is 10" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
