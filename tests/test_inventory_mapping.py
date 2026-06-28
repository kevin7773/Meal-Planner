from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from planner.inventory_mapping import (
    format_inventory_mapping_report,
    inventory_mapping_report,
)


ROOT = Path(__file__).resolve().parents[1]


class InventoryMappingReportTests(unittest.TestCase):
    def test_report_identifies_missing_and_invalid_mappings(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "recipes").mkdir()
            (root / "inventory").mkdir()
            shutil.copy2(
                ROOT / "recipes" / "chicken-fajitas.md",
                root / "recipes" / "chicken-fajitas.md",
            )
            shutil.copy2(
                ROOT / "recipes" / "10-minute-pasta.md",
                root / "recipes" / "10-minute-pasta.md",
            )
            (root / "inventory" / "catalog.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "items": [{"id": "chicken-breast"}],
                    }
                ),
                encoding="utf-8",
            )
            (root / "inventory" / "recipe-requirements.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "recipes": {
                            "FDP-0001": [
                                {
                                    "item_id": "unknown-pepper",
                                    "quantity": 1,
                                }
                            ]
                        },
                    }
                ),
                encoding="utf-8",
            )

            report = inventory_mapping_report(root)
            text = format_inventory_mapping_report(report)

        self.assertEqual(report["active_recipes"], 2)
        self.assertEqual(report["mapped_recipes"], 1)
        self.assertEqual(report["missing_mapping_count"], 1)
        self.assertEqual(
            report["missing_mappings"][0]["id"],
            "FDP-0012",
        )
        self.assertEqual(
            report["invalid_mappings"][0]["unknown_item_ids"],
            ["unknown-pepper"],
        )
        self.assertIn("FDP-0012", text)
        self.assertIn("unknown-pepper", text)

    def test_repo_mapping_report_has_versioned_shape(self) -> None:
        report = inventory_mapping_report(ROOT)

        self.assertEqual(report["schema_version"], 1)
        self.assertEqual(
            report["mapped_recipes"] + report["missing_mapping_count"],
            report["active_recipes"],
        )
        self.assertGreaterEqual(
            report["mapping_completeness_percent"],
            0,
        )


if __name__ == "__main__":
    unittest.main()
