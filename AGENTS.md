# Meal Planner Instructions

Treat the rules in `preferences/` as requirements. Before generating a menu,
read all preference files, `recipes/index.md`, and the recent entries in
`preferences/meal-history.md`.

Read `memory.md` before any weekly planning action. It records active rebuilds,
superseded artifacts, and user-directed holds that override normal automation.

Approved recipes in `recipes/` are the source of truth. Schedule an approved
recipe without changing its ingredients or directions. A variation must become
a new candidate revision before use. Use candidate recipes only when the menu
needs a gap filled, and identify them clearly for family review.

Use `prompts/weekly-menu-prompt.md` as the source of truth for the weekly run.
Create all dated artifacts requested there and update meal history only after
the plan is complete.

Weekly menus have a separate planning lifecycle defined in
`docs/planning-lifecycle.md`. The scheduled generation run may advance a menu
only through `validated`. Human review and explicit approval are required
before email delivery. Never send email unless the menu status is `approved`.
After all messages are sent successfully, advance it to `completed`.

Dry run precedes the planning lifecycle. Generate and compare three proposals
with `scripts/dry_run.py` without writing project files. A weekly menu enters
`draft` only after a human selects and commits one proposal.

Before dry run, validate and read `inventory/`. Prefer otherwise comparable
recipes and ideas that use stocked ingredients. Treat fresh produce as a
current-week purchase, use frozen lots FIFO, honor refrigerated expiration
dates, and surface low staple or consumable levels rather than assuming stock.

When the library is too small to produce three distinct weeks, dry run may use
ephemeral `IDEA-*` recipes derived from family and seasonal rules. These ideas
must not enter the recipe library during dry run. After selection, replace each
selected idea with a complete, validated `FDP-*` candidate recipe before the
weekly menu can advance from `draft` to `generated`.

Kid-friendly is a validated requirement. Every active recipe and dry-run idea
must score at least 4 out of 5 and state a concrete acceptance rationale based
on familiar format, mild flavor, customization, or separately served
components.

Imported recipes are always candidates. Preserve their source and do not
silently infer family approval. Review imported quantities, directions,
seasonings, semantic metadata, and inventory requirements before scheduling.

Queued entries in `ideas/recipe-ideas.json` are user intent and should be
surfaced in compatible dry-run options. Do not invent full recipe details when
the idea is merely saved. After selection, convert it into a complete `FDP-*`
candidate, record that ID on the idea, and mark the idea `converted`.

Respect recipe `meal_scope`. A `complete-meal` needs no automatic sides. An
`entree` must receive compatible suggestions from `sides/side-dishes.json`.
Include selected sides in fiber, cost, inventory, grocery, menu, and email
calculations; do not merely mention them in prose.

Meal overrides in `overrides/` are requirements, not suggestions. Preserve the
original meal in the audit record, return an in-progress week to `draft`,
regenerate affected menu/email/grocery artifacts, and validate again. Never
rewrite a `completed` or `archived` week.

Every scheduled library recipe must include its recipe ID, revision, and status
in the menu, meal history, and email output. Never mark a recipe approved or
add a rating without explicit family feedback.

Do not send email until all recipes, quantities, dates, and grocery totals have
been checked and the weekly menu is approved. Every planned day, including
Thursday, must appear in the weekly email output.

When a family preference conflicts with variety, safety, or seasonality, follow
the explicit family preference and note the tradeoff in rotation notes.
