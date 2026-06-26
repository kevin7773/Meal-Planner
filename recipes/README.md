# Recipe Library

Each recipe is a version-controlled family runbook with a stable ID. The
filename may become friendlier over time; the ID never changes.

## Statuses

- `candidate`: ready to test but not yet family-approved
- `approved`: family-tested source of truth; schedule unchanged
- `retired`: retained for history but no longer scheduled

## Workflow

1. Create a candidate from `_template.md` using the next ID in `index.md`.
2. Test it in a weekly menu and record the recipe ID and revision in meal
   history.
3. Append real ratings and notes after the meal.
4. Promote it to approved only with explicit family feedback.
5. For material changes, increment `revision` and add a revision-history row.
6. Run `python scripts/validate_recipes.py`.

After a meal, double-click `Review Meal.cmd` to open the family questionnaire.
It records an auditable feedback file, appends the rating to the recipe, and
updates the library index. A candidate is approved when it scores at least 4,
the family wants the exact recipe again, and no recipe change is requested.

Ingredient substitutions, quantity changes, seasoning changes, and cooking-step
changes are material. Typo and formatting corrections may retain the revision
but should still be noted in Git history.

Ratings use a 1-5 scale. `rating_average` and `ratings_count` summarize only
recorded ratings in the Ratings table.
