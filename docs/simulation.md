# Planner Simulation

The planner simulation repeatedly exercises the production assignment engine
against seeded scenarios. It is deterministic scenario sampling: the same
repository data, seed, start week, horizon, ranking variants, and search limit
produce the same planning metrics. Runtime fields such as elapsed seconds and
weeks per second naturally vary.

Run the checked-in performance scenario:

```powershell
python scripts/performance_gate.py check
```

Run a custom simulation:

```powershell
python scripts/planner_simulation.py run --iterations 10000 --seed 42 --json
```

## Scenario Sampling

Each iteration selects:

1. A Monday from the configured horizon.
2. A seeded, season-weighted weather category.
3. A ranking variant.

The performance baseline starts on June 29, 2026 and uses a 52-week horizon, so
all seasons are represented. Ranking variants change the deterministic rotation
offset used to order otherwise comparable candidates. The baseline uses two
variants to exercise more than one valid ordering without introducing
unrepeatable randomness.

## Cache Behavior

Assignments are cached by `(week, weather category, ranking variant)`. Repeated
samples of the same key reuse the assignment, diagnostics, and planning trace,
while still counting as individual observations in aggregate metrics.

Recipe universes are cached by week and generated-idea mode. Inventory scores
are cached by week and recipe ID. The report includes
`unique_scenarios_evaluated` and `scenario_cache_hit_rate` so cache effectiveness
is visible.

## Metrics

| Metric | Meaning |
| --- | --- |
| `successful_weeks`, `failed_weeks`, `success_rate` | Assignment outcomes across sampled weeks. |
| `average_recipe_cost_usd` | Average summed recipe estimates per successful week, before inventory savings, sides, or kids' alternate meals. |
| `average_grocery_bill_usd` | Compatibility alias for `average_recipe_cost_usd`; it is not post-inventory shopping cost. |
| `average_fiber_grams` | Average recipe fiber metadata per selected meal. |
| `average_inventory_coverage_score` | Average inventory match score for selected recipes. |
| Protein, cooking method, seasonal, and weather distributions | Counts and percentages observed in successful assignments. |
| `selected_recipe_source_distribution` | Selected meal counts and percentages for approved, candidate, generated idea, user idea, and override sources. Zero-count sources remain visible. |
| `recipe_utilization` | Per-recipe eligible count, selected count, selection rate, and average ranking score. |
| `underutilized_high_scoring_recipes` | Recipes scoring at least 75/100 but selected below 20%, after a minimum eligibility sample. These are candidates for constraint and day-placement review. |
| `recipe_diversity` | Distinct selected recipes as a percentage of recipes observed as eligible. |
| `constraint_failures` | Filter removals and search rejection pressure by rule; these are diagnostic observations. |
| `final_constraint_violations` | Rules violated by completed menus. Normal repository data must produce zero. |
| `elapsed_seconds`, `weeks_per_second` | Runtime performance only; excluded from deterministic metric comparisons. |

## Performance Gate

The gate reads `planner-data/performance-baseline.json`, runs its exact seeded
scenario, and currently enforces:

- Average recipe cost no more than 10% above the approved `$153.97` baseline.
- Average fiber of at least `8.0` grams.
- Average inventory coverage of at least `25.0/100`.
- Recipe diversity of at least `28.0%`.
- Zero final constraint violations.

Failed checks print the approved baseline, current result, and signed difference
before the enforced threshold, making CI regressions directly actionable.

Intentional baseline changes require:

```powershell
python scripts/performance_gate.py update-baseline --reason "review note"
```

GitHub Actions uploads the complete JSON result as the
`planner-simulation-report` artifact, even when the gate fails.
