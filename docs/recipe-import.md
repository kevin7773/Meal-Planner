# Recipe Cookbook

`Recipe Cookbook.cmd` supports browsing and revising the recipe library, local
text/Markdown imports, public HTTP/HTTPS recipe pages, and text pasted directly
into an in-memory editor. `Import Recipe.cmd` remains a compatibility wrapper
for existing shortcuts and habits.

The Cookbook opens in library mode. Select **Import Recipe** to reveal import
and recipe-idea fields. Selecting **Review** opens the feedback form directly
for the current recipe. `Review Meal.cmd` is retained as a legacy Cookbook
launcher.

Select **Edit** to load the current candidate into the guarded revision
workspace. Approved recipes are canonical and protected from direct edits;
requested changes should be captured through Review before a new candidate
revision is created.

The preview stage writes nothing. URL preview prefers schema.org Recipe JSON-LD
and falls back to visible page text. Downloads are limited to 2 MB, redirects
are revalidated, and private or local network addresses are rejected.

Imported recipes receive the next `FDP-*` ID and enter the library as
`candidate`. The source is recorded in metadata and revision history. Import
also creates an empty inventory requirement set so the inventory validator
remains consistent; that mapping should be completed before scheduling.

Plain-text files need recognizable `Ingredients` and
`Directions`/`Instructions` sections.

Pasted text uses the same section format and is not written to a temporary or
project file during preview.

Successful imports and saved ideas clear the completed form but keep the
importer open, allowing multiple recipes and ideas to be entered in one
session.

## Recipe Ideas

When only a meal concept is known, enter it in the **Recipe idea** field and
save it instead of importing. The idea receives an `IDEA-USER-*` ID and remains
`queued`. Dry run deliberately surfaces compatible queued ideas based on
season, protein, cooking method, cost, fiber, and kid-friendly metadata.

An idea is not a recipe and has no invented ingredients or directions. It
becomes a complete `FDP-*` candidate only after the family selects a week that
contains it.

## Meal Coverage

Choose `complete-meal` when the recipe already includes its intended sides.
Choose `entree` when it describes only the main dish. Entrees receive two
suggestions from the validated side-dish library during dry run. Suggestions
are seasonal, kid-friendly, fiber-aware, inventory-weighted, and included in
the proposal's cost and shopping calculations.

Use protein `other` for specialty ingredients such as pancetta or kielbasa
that do not fit the standard primary-protein choices.

## Kid-Friendly Classification

The importer uses a fixed kid-friendly reason list. Choosing
`Not kid friendly - for the parents only` automatically assigns score 1.
Dry runs may schedule that meal with a separate rotating children's option
from `quick-meals/kids-quick-meals.json`; its cost and inventory requirements
are included in the weekly proposal.
