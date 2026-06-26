# Family High-Fiber Dinner Planner

This repository schedules practical, kid-friendly weekly dinners for a family
of four from a version-controlled recipe library. It invents candidate recipes
only when the approved library cannot fill the week.

## Weekly Workflow

1. Read `AGENTS.md` and the files in `preferences/`.
2. Review `recipes/index.md` and `preferences/meal-history.md`.
3. Prefer approved recipes that fit the season and rotation rules.
4. Run the instructions in `prompts/weekly-menu-prompt.md`.
5. Save the menu, grocery list, and email drafts in their dated folders.
6. Update meal history with recipe IDs and revisions.

The recurring Codex automation runs every Saturday at 8:00 AM Eastern for the
upcoming Monday through Sunday.

## Repository Layout

- `prompts/`: weekly generation instructions
- `recipes/`: version-controlled recipe runbooks and library index
- `preferences/`: family rules, seasonal rules, and meal history
- `templates/`: required output formats
- `menus/`: completed weekly menus
- `grocery-lists/`: consolidated weekly shopping lists
- `email-outputs/`: three email-ready messages per week

`family_high_fiber_dinner_planner.md` is the original ChatGPT project handoff.

## Recipe Lifecycle

Recipes move from `candidate` to `approved` only after explicit family
feedback. Approved recipes are scheduled unchanged. Improvements create a new
revision with a dated history entry; unsuccessful recipes can be `retired`
without losing their history.

Run `python scripts/validate_recipes.py` after changing the recipe library.
