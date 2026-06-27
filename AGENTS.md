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
with `scripts/planner_cli.py` without writing project files. A weekly menu enters
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

The three dry-run options must be meaningfully different: any pair may share
at most two recipe or idea IDs. No protein may appear more than three times in
one week. Prefer fiber-rich choices, but treat weekly fiber as a comparative
metric rather than sacrificing protein and option variety to maximize it.

Every dry-run meal must include a per-recipe selection explanation. Report
inventory coverage, any required refrigerated ingredients expiring during the
week, day-rule or override fit, recent-repeat status, weather fit when
applicable, and kid score. Derive these claims from proposal inputs rather than
inventing generic rationale.

Read `preferences/weather-rules.json` and the target week's file under
`weather/` before generating proposals. When a forecast location is configured,
refresh the weekly context from a current forecast. A user-confirmed context
may be used without a numeric temperature. Enforce the category's minimum
heat-friendly meal count and excluded tags. Human overrides remain fixed and
do not count as overlap between dry-run options.

Kid-friendly is a validated requirement. Every active recipe and dry-run idea
must score at least 4 out of 5 and state a concrete acceptance rationale based
on familiar format, mild flavor, customization, or separately served
components. The sole exception is an explicitly classified parents-only meal,
which must score 1 and use `Not kid friendly - for the parents only`. Whenever
one is scheduled, assign a rotating option from
`quick-meals/kids-quick-meals.json` and include its cost and inventory needs.

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

Parents-only recipes are never presented as kid-friendly. Their paired quick
meal must appear in the dry run, committed menu, grocery planning, and email
content.

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
