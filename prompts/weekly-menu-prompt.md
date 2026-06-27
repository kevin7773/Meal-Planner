# Weekly Menu Prompt

Generate a kid-friendly, high-fiber dinner plan for a family of four for the
upcoming Monday through Sunday.

Before writing any project file, generate three dry-run proposals. Compare
estimated cost, average fiber, recipe rotation score, blocking errors, and
warnings. Present all three and wait for a human selection. Dry run must not
write menus, grocery lists, email drafts, history, or feedback.

Any two proposals may share at most two recipe or idea IDs. No protein may
appear more than three times in one proposal. Prefer higher fiber when choices
are otherwise comparable; protein variety and distinct options take
precedence over maximizing fiber.

Validate and read kitchen inventory before scoring. Report inventory coverage,
estimated savings, shopping cost after inventory, fresh weekly purchases, and
stock warnings. Prefer otherwise comparable plans that use existing pantry,
refrigerated, and frozen ingredients. Do not count expired food or fresh
produce carried over from an earlier week.

Read any existing override record for the target week before planning or
regenerating. Honor dining-out, special-occasion, skip, custom, and alternate
recipe overrides. Exclude superseded meals from grocery quantities and email
content while preserving their audit history.

If the recipe library cannot produce three genuinely distinct, rule-compliant
weeks, invent ephemeral `IDEA-*` recipes in memory. Base them on all family,
seasonal, protein, fiber, cooking-method, and rotation rules. Do not add
unselected ideas to the library.

Read queued `IDEA-USER-*` entries before generating options. Surface each
compatible user idea in the comparison set ahead of generic generated ideas.
When selected, expand it into a complete `FDP-*` candidate and mark its backlog
entry converted.

Every library recipe and generated idea must score at least 4 out of 5 for
kid-friendliness and include a concrete rationale. Reject ideas that are merely
nutritious but rely on unfamiliar composed salads, strongly flavored sauces,
or adult-oriented formats. Prefer familiar, mild, customizable meals with
components that can be served separately.

An explicitly classified parents-only recipe is allowed with score 1 and the
reason `Not kid friendly - for the parents only`. If selected, pair it with a
rotating option from `quick-meals/kids-quick-meals.json`. Show the children's
meal in the proposal and include its cost, inventory, grocery, menu, and email
impact.

For every selected recipe or idea with `meal_scope = "entree"`, propose two
validated side dishes. Prefer seasonal produce, fruit, whole grains, beans, and
stocked ingredients. Count those sides in estimated fiber, cost, inventory
coverage, grocery quantities, menu content, and email drafts. Do not add sides
to `complete-meal` recipes automatically.

After a human commits one proposal, create the weekly menu with planning status
`draft`. Convert every selected `IDEA-*` entry into a complete `FDP-*`
candidate recipe with the next available IDs, then update the draft menu to
those IDs. After all menu, grocery, and email-draft artifacts exist, advance
it to `generated`. Run the recipe and menu validators; advance it to
`validated` only when they pass. Stop there and request human review. Do not
send email during generation.

Before writing:

1. Read `memory.md` and honor any active rebuild hold.
2. Read every file in `preferences/`.
3. Read `recipes/index.md` and the applicable files in `recipes/`.
4. Review recent meal history and avoid repeating a main dish within 2-3 weeks
   when practical.
5. Apply the seasonal rules for the dates being planned.

## Recipe Selection

1. Fill the week with approved library recipes whenever they satisfy the
   schedule, season, rotation, and ingredient-reuse rules.
2. Reproduce approved recipe ingredients and directions exactly. Do not
   silently improvise.
3. If an approved recipe needs a change, create a new candidate revision and
   explain why.
4. Invent a new candidate recipe only when the library cannot fill a slot.
5. Assign each new candidate the next available `FDP-NNNN` ID and add it to
   `recipes/index.md`.
6. Label candidate meals in the weekly menu so the family knows feedback is
   requested.

For every dinner include:

- Day and full date
- Meal name and cooking method
- Recipe ID, revision, and status
- Estimated fiber per serving
- Active prep time and cook time
- Exact quantities for every ingredient and seasoning
- Numbered directions that explicitly name every seasoning
- Doneness guidance where applicable
- Leftover and ingredient reuse notes

Keep active prep under 60 minutes. Build at least 2-3 intentional reuse
connections across the week. Consolidate duplicate grocery ingredients into
one exact total.

Use the files in `templates/` and save:

- `menus/YYYY/YYYY-MM-DD.md`
- `grocery-lists/YYYY/YYYY-MM-DD-grocery-list.md`
- `email-outputs/YYYY/YYYY-MM-DD/email-1-mon-tue.md`
- `email-outputs/YYYY/YYYY-MM-DD/email-2-wed-thu-fri.md`
- `email-outputs/YYYY/YYYY-MM-DD/email-3-sat-sun.md`

Use the Monday date in each filename.

Email 1 contains Monday and Tuesday. Email 2 contains Wednesday, Thursday, and
Friday. Email 3 contains Saturday, Sunday, the full grocery list, leftover
notes, and rotation notes. Every planned day must appear in an email.

Every recipe in every email must display this line directly below its meal
heading:

`**Recipe:** FDP-NNNN rev N (approved/candidate)`

Address all three email drafts to `klsmallwood73@gmail.com`. Send them only
after the weekly menu has been explicitly advanced to `approved`. After all
three sends succeed, advance the menu to `completed`. If any send fails, do not
mark the week completed.

After the meals are served, append the week's meals, recipe IDs, revisions, and
outcomes to `preferences/meal-history.md`. Once feedback is collected, advance
the menu from `completed` to `archived`. Do not promote or rate candidates
without explicit family feedback.
