# Side-Dish Suggestions

The side library in `sides/side-dishes.json` supports recipes and ideas marked
with `meal_scope = "entree"`.

Each side has:

- Stable `SIDE-*` ID
- Seasonal availability
- Fiber and cost estimate
- Kid-friendly score and rationale
- Cooking method
- Normalized inventory requirements

Dry run proposes two compatible sides, avoids repeating the same primary side
type, and favors inventory coverage. Suggested sides contribute to nutrition,
cost, inventory savings, and shopping needs. Complete-meal recipes do not
receive automatic suggestions.
