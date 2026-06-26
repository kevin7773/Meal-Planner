# Meal Planner Instructions

Treat the rules in `preferences/` as requirements. Before generating a menu,
read all preference files, `recipes/index.md`, and the recent entries in
`preferences/meal-history.md`.

Approved recipes in `recipes/` are the source of truth. Schedule an approved
recipe without changing its ingredients or directions. A variation must become
a new candidate revision before use. Use candidate recipes only when the menu
needs a gap filled, and identify them clearly for family review.

Use `prompts/weekly-menu-prompt.md` as the source of truth for the weekly run.
Create all dated artifacts requested there and update meal history only after
the plan is complete.

Every scheduled library recipe must include its recipe ID, revision, and status
in the menu, meal history, and email output. Never mark a recipe approved or
add a rating without explicit family feedback.

Do not send email until all recipes, quantities, dates, and grocery totals have
been checked. Every planned day, including Thursday, must appear in the weekly
email output.

When a family preference conflicts with variety, safety, or seasonality, follow
the explicit family preference and note the tradeoff in rotation notes.
