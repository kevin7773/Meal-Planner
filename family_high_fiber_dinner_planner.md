# Family High-Fiber Dinner Planner

A GitHub-friendly project guide for generating weekly kid-friendly, high-fiber family dinner menus with recipes, grocery lists, leftover planning, and email-ready outputs.

This project is designed for a family of 4 and emphasizes fiber, kid-friendly meals, seasonal produce, ingredient reuse, and practical weeknight cooking.

---

## Project Goals

Generate a weekly dinner plan for the upcoming Monday through Sunday that includes:

- Dates for each day
- Complete dinner recipes
- Exact ingredient quantities
- All seasoning and spice quantities
- Detailed step-by-step cooking directions
- Explicit seasoning references in the cooking directions
- Estimated fiber per serving
- Leftover reuse notes
- Categorized grocery list
- Email-ready outputs split into reliable message sizes

---

## Recommended Repository Structure

```text
family-dinner-planner/
├── README.md
├── prompts/
│   └── weekly-menu-prompt.md
├── preferences/
│   ├── family-preferences.md
│   ├── seasonal-rules.md
│   ├── meal-history.md
│   └── rotation-rules.md
├── menus/
│   └── 2026/
│       ├── 2026-06-22.md
│       └── 2026-06-29.md
├── grocery-lists/
│   └── 2026/
│       └── 2026-06-22-grocery-list.md
├── email-outputs/
│   └── 2026/
│       └── 2026-06-22/
│           ├── email-1-mon-tue.md
│           ├── email-2-wed-thu-fri.md
│           └── email-3-sat-sun.md
└── templates/
    ├── weekly-menu-template.md
    ├── recipe-template.md
    ├── grocery-list-template.md
    └── email-template.md
```

---

# Weekly Menu Generation Prompt

## Objective

Generate a kid-friendly, high-fiber dinner menu for a family of 4 for the upcoming Monday through Sunday.

The menu should be practical for weeknight cooking, flavorful, seasonal, and designed to reduce grocery waste.

---

## Required Weekly Output

For each week, generate:

1. Weekly dinner menu
2. Complete recipes
3. Exact ingredient quantities
4. All seasoning and spice quantities
5. Detailed step-by-step cooking directions
6. Estimated fiber per serving
7. Leftover reuse notes
8. Categorized grocery list
9. Three separate email-ready outputs

---

## Required Format for Each Dinner

Each dinner must include:

```markdown
## Day, Month Date — Meal Name

**Estimated Fiber:** X grams per serving
**Active Prep Time:** X minutes
**Cook Time:** X minutes
**Cooking Method:** Grill / Blackstone / Smoker / Slow Cooker / Minimal-Cook / Stovetop / Oven

### Ingredients

#### Main Ingredients
- Ingredient with exact quantity

#### Seasonings
- Seasoning with exact quantity

#### Optional Toppings or Sides
- Ingredient with exact quantity

### Directions

1. Step-by-step instructions.
2. Explicitly mention each seasoning used.
3. Include doneness guidance where applicable.
4. Keep active prep under 60 minutes.

### Leftover Reuse Notes

- Explain what to save.
- Explain how it will be reused later in the week.
```

---

# Family Preferences

## Mexican Monday

Monday is always **Mexican Monday**.

Monday should be a Mexican-inspired meal such as:

- Tacos
- Fajita bowls
- Quesadillas
- Enchiladas
- Burrito bowls
- Taco pasta
- Smash tacos
- Taco salads
- Mexican rice bowls
- Blackstone chicken fajitas

Mexican Monday should remain kid-friendly and flavorful.

---

## Fiber Priorities

Prioritize fiber from:

- Beans
- Vegetables
- Fruit
- Whole grains
- Legumes

Preferred fiber target:

- Aim for approximately **10–15 grams of fiber per serving** when practical.
- Do not make meals feel overly “health food” focused.
- Keep meals family-friendly and flavorful.

---

## Bean Preference

Prefer the following when a recipe calls for beans:

1. Pinto beans
2. Mexican-style pinto beans
3. Refried pinto beans

Avoid black beans unless there is a specific reason they are clearly better for the recipe.

---

## Protein Preference

Preferred protein order:

1. Poultry
2. Beef
3. Seafood

Specific rules:

- Prefer chicken and turkey for tacos, bowls, burgers, sliders, pasta, and similar meals.
- Limit beef-centered meals to roughly every other week when practical.
- Substitute ground chicken or turkey where appropriate.
- Seafood is welcome occasionally, especially salmon.

---

## Pork Preference

Avoid pork recipes unless the pork is used as:

- Bacon
- Sausage
- Ham
- Ham steaks
- Occasional slow-cooker pulled pork

Do not make pork a frequent centerpiece.

---

# Seasonal Rules

## June–August: Summer Rules

During June, July, and August, favor:

- Outdoor grill meals
- Smoker meals
- Blackstone meals
- Slow-cooker meals
- Minimal-cook meals
- No-cook meals

Avoid:

- Soups
- Chili
- Heavy casseroles
- Long indoor oven meals
- Heavy baked pasta dishes unless specifically requested

Important summer rule:

> **Do not suggest soups during June, July, or August.**

---

## Summer Produce Priorities

During summer, prioritize:

- Corn
- Tomatoes
- Bell peppers
- Zucchini
- Cucumbers
- Berries
- Peaches
- Watermelon
- Green beans
- Fresh herbs when practical

---

## Tuesday and Thursday Rules

Tuesday and Thursday should be either:

- Slow-cooker meals
- Minimal-cook meals
- No-cook meals

During summer, Tuesday and Thursday should avoid soups.

Good summer Tuesday/Thursday examples:

- Slow-cooker BBQ chicken sliders
- Slow-cooker chicken taco meat for bowls
- BBQ chicken baked potato bar
- Chicken Caesar wraps
- Turkey or chicken sandwich bar
- Pasta salad with grilled chicken
- Rotisserie chicken rice bowls
- Slow-cooker salsa chicken
- No-cook taco salad
- Blackstone leftovers night

---

# Meal Rotation Rules

## Avoid Repeating the Previous Week

Do not repeat the exact same dinner lineup from the previous week.

When possible:

- Avoid repeating the same main dish within 2–3 weeks.
- Rotate cooking methods.
- Rotate flavor profiles.
- Reuse family favorites without making the week feel identical.

---

## Established Kid Favorites

Track and periodically rotate these favorites:

- Tacos
- Quesadillas
- Chicken fajitas
- BBQ chicken sandwiches or sliders
- Pizza-style pasta
- Calzones
- Chicken Alfredo tortellini
- Chili
- Salmon
- Spaghetti bake

Summer note:

- Chili and soups should be reserved for fall and winter.
- Spaghetti bake and heavy casseroles are better for cooler months.

---

## Blackstone Variety

Increase Blackstone variety with options such as:

- Hibachi chicken
- Fried rice
- Chicken cheesesteak bowls
- Turkey cheesesteak bowls
- Chicken fajitas
- Smash tacos
- Breakfast-for-dinner
- Stir fry
- Chicken burrito bowls
- Turkey burger bowls

---

# Leftover and Ingredient Reuse Rules

Intentionally reuse leftovers and ingredients across the week to reduce waste and grocery cost.

Examples:

- Monday fajita chicken can become Wednesday tacos, bowls, or fried rice.
- Extra BBQ chicken can become lunches, wraps, baked potatoes, or sliders.
- Bell peppers and onions can be used in fajitas, cheesesteak bowls, skewers, and tacos.
- Brown rice can be used in bowls and fried rice.
- Pinto beans can be used in Mexican Monday, taco sides, bowls, and salads.
- Watermelon, peaches, and berries can appear as sides multiple times.

Each weekly plan should include at least 2–3 intentional reuse notes.

---

# Seasoning Rules

Every recipe must include all seasonings and spice quantities in the ingredients list.

Every seasoning must also be explicitly referenced in the cooking directions.

Do not assume seasonings are obvious.

Bad example:

> Season chicken and grill.

Good example:

> In a small bowl, combine 1 teaspoon garlic powder, 1 teaspoon onion powder, 1 teaspoon smoked paprika, 1 teaspoon kosher salt, and 1/2 teaspoon black pepper. Sprinkle the seasoning mixture evenly over the chicken before grilling.

Recipes should be fully seasoned and flavorful rather than bland.

---

# Grocery List Rules

Generate a categorized grocery list with exact quantities.

Use these categories:

```markdown
# Grocery List

## Produce
## Meat & Seafood
## Dairy
## Bakery
## Grains & Pasta
## Canned & Jarred Goods
## Frozen
## Condiments & Sauces
## Seasonings & Spices
## Optional Toppings
```

The grocery list should consolidate duplicate ingredients across all meals.

Example:

If Monday uses 3 bell peppers and Saturday uses 2 bell peppers, the grocery list should show:

- 5 bell peppers

not two separate entries.

---

# Email Delivery Rules

To prevent truncation or incomplete emails, split the weekly menu into **three separate emails**.

Send to:

```text
klsmallwood73@gmail.com
```

## Email 1

Subject format:

```text
Weekly Dinner Menu: Monday–Tuesday, <date range>
```

Contents:

- Monday full recipe
- Tuesday full recipe
- Any relevant leftover notes for those days

## Email 2

Subject format:

```text
Weekly Dinner Menu: Wednesday-Friday, <date range>
```

Contents:

- Wednesday full recipe
- Thursday full recipe
- Friday full recipe

## Email 3

Subject format:

```text
Weekly Dinner Menu: Saturday–Sunday, <date range>
```

Contents:

- Saturday full recipe
- Sunday full recipe
- Categorized grocery list for the full week
- Weekly leftover notes
- Weekly meal rotation notes

---

# Thursday Handling

Thursday must be planned and included in the second weekly email.

If Thursday is included in internal planning:

- It must follow Tuesday/Thursday rules.
- During summer it must not be soup.
- It should be slow-cooker, minimal-cook, or no-cook.

---

# Quality Checklist

Before finalizing any weekly menu, verify:

- [ ] Monday is Mexican Monday.
- [ ] The menu is for the upcoming Monday through Sunday.
- [ ] Dates are included for each day.
- [ ] All recipes are kid-friendly.
- [ ] Fiber is prioritized from beans, vegetables, fruit, and whole grains.
- [ ] Pinto beans are preferred over black beans.
- [ ] June–August menus avoid soups.
- [ ] June–August menus favor grill, smoker, and Blackstone meals.
- [ ] Tuesday and Thursday are slow-cooker, minimal-cook, or no-cook.
- [ ] Poultry is prioritized.
- [ ] Beef is limited.
- [ ] Pork is avoided except approved uses.
- [ ] Leftovers and ingredients are intentionally reused.
- [ ] Seasonal summer produce is prioritized.
- [ ] Family favorites are rotated.
- [ ] The previous week’s exact lineup is not repeated.
- [ ] Active prep is generally under 60 minutes.
- [ ] Every recipe includes exact seasoning quantities.
- [ ] Every seasoning is referenced in the cooking directions.
- [ ] The grocery list is categorized and consolidated.
- [ ] Email output is split into three separate emails.
- [ ] Thursday is included in the second weekly email.

---

# Suggested Weekly Workflow

1. Review the previous week’s menu.
2. Select a new lineup that avoids direct repetition.
3. Confirm Monday is Mexican Monday.
4. Pick Tuesday and Thursday slow-cooker/minimal-cook meals.
5. Choose 2–3 grill, smoker, or Blackstone meals during summer.
6. Build intentional ingredient reuse into the week.
7. Estimate fiber per serving for each dinner.
8. Generate full recipes with exact ingredients and seasonings.
9. Consolidate grocery list.
10. Generate three email-ready outputs.
11. Send three separate emails.
12. Save the final menu to `menus/YYYY/YYYY-MM-DD.md`.
13. Save grocery list to `grocery-lists/YYYY/YYYY-MM-DD-grocery-list.md`.
14. Update `preferences/meal-history.md`.

---

# Meal History Template

Use this format to track previous meals and avoid repetition.

```markdown
# Meal History

## Week of YYYY-MM-DD

### Monday
- Meal:
- Protein:
- Cooking method:
- Cuisine/theme:

### Tuesday
- Meal:
- Protein:
- Cooking method:
- Cuisine/theme:

### Wednesday
- Meal:
- Protein:
- Cooking method:
- Cuisine/theme:

### Thursday
- Meal:
- Protein:
- Cooking method:
- Cuisine/theme:

### Friday
- Meal:
- Protein:
- Cooking method:
- Cuisine/theme:

### Saturday
- Meal:
- Protein:
- Cooking method:
- Cuisine/theme:

### Sunday
- Meal:
- Protein:
- Cooking method:
- Cuisine/theme:

## Notes
- Repeats to avoid:
- Family favorites used:
- Ingredients reused:
- What worked:
- What to avoid next time:
```

---

# Weekly Menu Template

```markdown
# Weekly Dinner Menu

**Week of:** YYYY-MM-DD
**Family Size:** 4
**Season:** Summer / Fall / Winter / Spring

---

## Monday, Month DD — Meal Name

**Theme:** Mexican Monday
**Estimated Fiber:** X g per serving
**Active Prep Time:** X minutes
**Cook Time:** X minutes
**Cooking Method:** Blackstone / Grill / Slow Cooker / etc.

### Ingredients

#### Main Ingredients
-

#### Seasonings
-

#### Toppings / Sides
-

### Directions

1.
2.
3.

### Leftover Reuse Notes

-

---

## Tuesday, Month DD — Meal Name

**Estimated Fiber:** X g per serving
**Active Prep Time:** X minutes
**Cook Time:** X minutes
**Cooking Method:** Slow Cooker / Minimal-Cook / No-Cook

### Ingredients

#### Main Ingredients
-

#### Seasonings
-

#### Toppings / Sides
-

### Directions

1.
2.
3.

### Leftover Reuse Notes

-

---

## Wednesday, Month DD — Meal Name

Repeat recipe format.

---

## Thursday, Month DD — Meal Name

Include in the second weekly email.

---

## Friday, Month DD — Meal Name

Repeat recipe format.

---

## Saturday, Month DD — Meal Name

Repeat recipe format.

---

## Sunday, Month DD — Meal Name

Repeat recipe format.

---

# Grocery List

## Produce
-

## Meat & Seafood
-

## Dairy
-

## Bakery
-

## Grains & Pasta
-

## Canned & Jarred Goods
-

## Frozen
-

## Condiments & Sauces
-

## Seasonings & Spices
-

## Optional Toppings
-

---

# Weekly Leftover Plan

-

---

# Rotation Notes

-

---

# Email Outputs

## Email 1: Monday–Tuesday

-

## Email 2: Wednesday-Friday

-

## Email 3: Saturday–Sunday

-
```

---

# Future Enhancements

Potential future project improvements:

## Meal History Engine

Track all previous meals and automatically avoid repeats within a configurable window.

## Pantry Inventory

Track pantry staples already on hand to reduce grocery costs.

## Grocery Cost Optimization

Use store pricing or sale flyers to suggest lower-cost substitutions.

## Nutrition Tracking

Track:

- Fiber
- Protein
- Calories
- Vegetables per serving
- Fruit servings
- Whole grain servings

## PDF Export

Generate polished printable cookbook-style weekly PDFs.

## Grocery App Integration

Potential integrations:

- AnyList
- Apple Reminders
- Google Keep
- Todoist
- Instacart

## Seasonal Rotation

Automatically shift meal style by season:

### Summer

- Grill
- Smoker
- Blackstone
- Minimal oven

### Fall

- Sheet pan meals
- Chili
- Soups
- Pasta bakes

### Winter

- Slow cooker
- Comfort food
- Casseroles
- Roasts

### Spring

- Lighter bowls
- Grilled chicken
- Salads
- Fresh vegetables

---

# Current Automation Summary

The current recurring automation runs:

```text
Every Saturday at 8:00 AM Eastern
```

It generates the upcoming week’s menu and sends it as three separate emails:

1. Monday–Tuesday
2. Wednesday through Friday
3. Saturday–Sunday plus grocery list

Recipient:

```text
klsmallwood73@gmail.com
```

---

# Notes

This project should be treated as a living system.

Each week’s results should improve based on:

- What meals the family liked
- What meals were too much work
- What ingredients were wasted
- What leftovers were actually used
- What grocery items were too expensive
- Seasonal availability
- Schedule constraints
