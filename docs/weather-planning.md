# Weather-Aware Planning

Weekly weather context lives at:

`weather/<year>/<monday-date>.json`

The context records a planning category, optional forecast high, source, and
note. A user-confirmed forecast can set the category without supplying an exact
temperature. Project-wide thresholds and exclusions live in
`preferences/weather-rules.json`.

## Categories

- `normal`: no weather-specific minimum.
- `warm`: at least two heat-friendly meals.
- `hot`: at least three heat-friendly meals; avoid soup, stew, and chili.
- `extreme-heat`: at least four heat-friendly meals; also avoid heavy
  casseroles.

Heat-friendly meals use no-cook, minimal-cook, grill, smoker, or Blackstone
methods, or carry the `cold-meal` or `heat-friendly` tag. Human carryout and
custom overrides also qualify.

Run:

```powershell
python scripts/weather_context.py validate
python scripts/weather_context.py show --week 2026-06-29
```

When `forecast_location` is configured, the weekly planning automation should
retrieve a current forecast before dry-run generation. Until then, create a
weekly context from the user's stated forecast rather than inferring a location.
