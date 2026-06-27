# Family High-Fiber Dinner Planner

[![Validate planner](https://github.com/kevin7773/Meal-Planner/actions/workflows/validate-recipes.yml/badge.svg)](https://github.com/kevin7773/Meal-Planner/actions/workflows/validate-recipes.yml)

This repository schedules practical, kid-friendly weekly dinners for a family
of four from a version-controlled recipe library. It invents candidate recipes
only when the approved library cannot fill the week.

## Weekly Workflow

1. Double-click `Plan Week.cmd` and generate three side-effect-free dry runs.
2. Compare shopping cost after inventory, fiber, rotation score, and warnings.
3. Commit one selected proposal, which creates a `draft` weekly menu.
4. Generate the grocery list and email drafts.
5. Validate the generated week and wait for explicit approval.
6. Send the approved emails and update meal history with recipe IDs and
   revisions.

The recurring Codex automation runs every Saturday at 8:00 AM Eastern for the
upcoming Monday through Sunday.

## Repository Layout

- `prompts/`: weekly generation instructions
- `planner/`: dry-run planning, assignment, scoring, reporting, and commit logic
- `planner-data/`: versioned generated-idea candidate pools
- `telemetry/`: aggregate planner-engine performance and constraint pressure
- `recipes/`: version-controlled recipe runbooks and library index
- `preferences/`: family rules, seasonal rules, and meal history
- `templates/`: required output formats
- `menus/`: completed weekly menus
- `grocery-lists/`: consolidated weekly shopping lists
- `email-outputs/`: three email-ready messages per week
- `docs/architecture.md`: component boundaries and end-to-end data flow
- `docs/planning-lifecycle.md`: weekly planning states and transition rules
- `inventory/`: ingredient catalog, stock lots, and normalized recipe requirements

`family_high_fiber_dinner_planner.md` is the original ChatGPT project handoff.

## Recipe Lifecycle

Recipes move from `candidate` to `approved` only after explicit family
feedback. Approved recipes are scheduled unchanged. Improvements create a new
revision with a dated history entry; unsuccessful recipes can be `retired`
without losing their history.

Run `python scripts/validate_recipes.py` after changing the recipe library.
Run `python scripts/menu_status.py check <menu-path>` to validate a weekly
menu's lifecycle metadata.
Run `python scripts/inventory.py validate` after changing inventory data.
Run `python scripts/planner_cli.py telemetry` to inspect planner-engine
performance and constraint pressure.
Run `python scripts/planner_cli.py telemetry --recipes` to compare recipe
eligibility, selection rate, and normalized ranking score.
Run `python scripts/planner_cli.py telemetry --drift` to inspect protein,
cooking-method, seasonal, Blackstone, prep-time, cost, and fiber trends.
Run `python scripts/planner_cli.py telemetry --rules` to inspect registered,
tested, monthly-used, and unused planning rules.

## Dry Run

`Plan Week.cmd` opens the comparison GUI. Generation reads the recipe library
and meal history but writes nothing. Each option reports estimated cost,
average fiber, recipe rotation score, blocking errors, and warnings. Only
`Commit Selected` creates a file, and that file begins at planning status
`draft`.

Every proposed meal also includes a **Why selected** block with its own
inventory coverage, expiring refrigerated ingredients, day-rule fit, recent
rotation result, weather fit, and kid score.

Each pair of options shares at most two recipe or idea IDs, and no protein
appears more than three times in a proposed week. Fiber remains a comparison
metric and preference rather than overriding those variety constraints.

Dry runs also read `preferences/weather-rules.json` and an optional weekly
context under `weather/<year>/`. Hot-weather rules favor cold, no-cook,
minimal-cook, and outdoor-cooked meals while excluding seasonally inappropriate
soups and heavy dishes.

When the approved library is not large enough, options contain temporary
`IDEA-*` recipes generated from the family and seasonal rules. Unselected ideas
disappear. Selected ideas are expanded into full `FDP-*` candidate recipes
before the week advances to `generated`.

## Kitchen Inventory

Double-click `Kitchen Inventory.cmd` to add and edit stock. The model tracks
exact quantities for staples, pantry, refrigerated, frozen, and fresh items;
expiration dates for refrigerated food; acquired dates and FIFO ordering for
frozen food; and `full/half/low` levels for consumables.

Dry run uses inventory coverage to rank recipe choices and reports estimated
shopping cost after stock, approximate savings, fresh weekly purchases, and
low-stock warnings. Fresh produce from an earlier week is not carried forward
automatically.

## Recipe Import

Double-click `Import Recipe.cmd` to preview and import a `.txt`/`.md` recipe, a
public recipe URL, or recipe text pasted directly into the editor. URL imports
prefer schema.org Recipe data. Imports are created as candidates with source
attribution and must be reviewed for quantities, seasoning classification, and
inventory mapping before scheduling.

The same window includes a **Recipe idea** field for meals that do not yet have
a recipe. Saved ideas receive `IDEA-USER-*` IDs and are deliberately surfaced
in compatible dry-run options. Only selected ideas are expanded into full
`FDP-*` candidates. After an import or saved idea, the window stays open and
resets for the next entry.

Set **Meal coverage** to `entree` when the imported recipe or idea does not
include sides. Dry run then proposes two seasonal, kid-friendly, fiber-aware
side dishes and includes them in cost and inventory calculations.

Parents-only recipes use the fixed reason
`Not kid friendly - for the parents only` and a kid-friendly score of 1. When
one is selected, the planner adds a rotating quick meal for the children and
includes that meal in cost and inventory estimates.

## Meal Overrides

Double-click `Override Meal.cmd` to replace a planned day with dining out, a
special occasion, a skipped meal, a custom plan, or another library recipe.
The original recipe is preserved in an override audit record. Menu and email
drafts are updated, grocery deltas are calculated, and the week returns to
`draft` for regeneration and validation. Completed and archived weeks remain
immutable.
