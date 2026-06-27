# Meal Overrides

`Override Meal.cmd` supports:

- `dining-out`
- `special-occasion`
- `skip`
- `custom`
- `alternate-recipe`

Overrides apply only to active planned weeks. A generated, validated, reviewed,
or approved week returns to `draft`. Completed and archived weeks are immutable.

Each override:

1. Preserves the original recipe ID in `overrides/YYYY/`.
2. Replaces the affected menu and email-draft section.
3. Adds grocery-list deltas based on normalized recipe requirements.
4. Records the actor, timestamp, type, title, and note.
5. Requires regeneration and validation before approval.
