# Weekly Menu Prompt

Generate a kid-friendly, high-fiber dinner plan for a family of four for the
upcoming Monday through Sunday.

Before writing:

1. Read every file in `preferences/`.
2. Read `recipes/index.md` and the applicable files in `recipes/`.
3. Review recent meal history and avoid repeating a main dish within 2-3 weeks
   when practical.
4. Apply the seasonal rules for the dates being planned.

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

Address all three email drafts to `klsmallwood73@gmail.com`. If Gmail access is
available, send the messages only after validating the full plan. Otherwise,
leave complete email-ready drafts in the output folder and report that sending
was unavailable.

Finally, append the week's meals, recipe IDs, revisions, and outcomes to
`preferences/meal-history.md`. Do not promote or rate candidates without
explicit family feedback.
