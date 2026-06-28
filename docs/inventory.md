# Kitchen Inventory Model

## Ingredient Classes

| Class | Tracking behavior |
| --- | --- |
| `staple` | Exact quantity with a minimum-stock warning |
| `pantry` | Exact quantity, replenished as needed |
| `refrigerated` | Exact quantity with expiration date |
| `frozen` | Exact quantity in dated lots, consumed FIFO |
| `fresh-produce` | Current-week quantity only; no automatic carryover |
| `consumable` | Approximate `full`, `half`, or `low` level |

The catalog defines stable ingredient IDs and base units.
`recipe-requirements.json` maps each `FDP-*` recipe to those IDs.
`stock.json` contains user-entered lots and levels.

## Workflow

1. Open `Kitchen Inventory.cmd`.
2. Add quantities, lots, expiration dates, or consumable levels.
3. Save inventory.
4. Use **Mapping Completeness** to find recipes with missing or invalid
   ingredient mappings.
5. Open `Plan Week.cmd`.
6. Compare inventory coverage, shopping cost, savings, and warnings.

The same completeness report is available from:

```powershell
python scripts/inventory_mapping_report.py
python scripts/inventory_mapping_report.py --json
```

Planning reads inventory but does not deduct it. Stock should be deducted only
after a completed week or an explicit inventory action, preventing an
unapproved plan from consuming virtual ingredients.
