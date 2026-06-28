from __future__ import annotations

import datetime as dt
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.dry_run import generate_proposals, load_recipes
from scripts.inventory import assess_inventory, fifo_plan, validate_inventory


ROOT = Path(__file__).resolve().parents[1]


class InventoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        shutil.copytree(ROOT / "inventory", self.root / "inventory")
        shutil.copytree(ROOT / "planner-data", self.root / "planner-data")
        shutil.copytree(ROOT / "recipes", self.root / "recipes")
        (self.root / "preferences").mkdir()
        shutil.copy2(
            ROOT / "preferences" / "weather-rules.json",
            self.root / "preferences" / "weather-rules.json",
        )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def write_stock(self, items: list[dict]) -> None:
        document = {
            "schema_version": 1,
            "updated_at": "2026-06-26T12:00:00Z",
            "items": items,
        }
        (self.root / "inventory" / "stock.json").write_text(
            json.dumps(document, indent=2),
            encoding="utf-8",
        )

    def test_inventory_documents_are_valid(self) -> None:
        self.assertEqual(validate_inventory(self.root), [])

    def test_inventory_rejects_unsupported_schema_version(self) -> None:
        path = self.root / "inventory" / "catalog.json"
        document = json.loads(path.read_text(encoding="utf-8"))
        document["schema_version"] = 2
        path.write_text(json.dumps(document), encoding="utf-8")

        self.assertIn(
            "inventory/catalog.json: unsupported schema_version 2; "
            "supported version(s): 1",
            validate_inventory(self.root),
        )

    def test_frozen_expiration_is_six_months_after_acquisition(self) -> None:
        frozen_lot = {
            "lot_id": "frozen",
            "item_id": "chicken-breast",
            "quantity": 2,
            "level": None,
            "acquired_on": "2026-06-27",
            "expires_on": "2026-07-04",
        }
        self.write_stock([frozen_lot])
        self.assertIn(
            "frozen: frozen stock expires_on must be six months "
            "after acquired_on",
            validate_inventory(self.root),
        )

        frozen_lot["expires_on"] = "2026-12-27"
        self.write_stock([frozen_lot])
        self.assertEqual(validate_inventory(self.root), [])

    def test_frozen_fifo_uses_oldest_lot_first(self) -> None:
        self.write_stock(
            [
                {
                    "lot_id": "new",
                    "item_id": "chicken-breast",
                    "quantity": 2,
                    "level": None,
                    "acquired_on": "2026-06-20",
                    "expires_on": None,
                },
                {
                    "lot_id": "old",
                    "item_id": "chicken-breast",
                    "quantity": 2,
                    "level": None,
                    "acquired_on": "2026-06-01",
                    "expires_on": None,
                },
            ]
        )
        plan = fifo_plan("chicken-breast", 3, root=self.root)
        self.assertEqual(
            plan,
            [
                {"lot_id": "old", "quantity": 2.0},
                {"lot_id": "new", "quantity": 1.0},
            ],
        )

    def test_old_fresh_produce_does_not_carry_into_new_week(self) -> None:
        self.write_stock(
            [
                {
                    "lot_id": "peppers",
                    "item_id": "bell-pepper",
                    "quantity": 3,
                    "level": None,
                    "acquired_on": "2026-06-20",
                    "expires_on": None,
                }
            ]
        )
        assessment = assess_inventory(
            [{"item_id": "bell-pepper", "quantity": 3}],
            root=self.root,
            as_of=dt.date(2026, 6, 26),
            week_of=dt.date(2026, 6, 29),
        )
        self.assertEqual(assessment["buy"][0]["quantity"], 3)
        self.assertEqual(assessment["buy"][0]["reason"], "fresh weekly purchase")

    def test_low_consumable_and_staple_generate_warnings(self) -> None:
        self.write_stock(
            [
                {
                    "lot_id": "salt",
                    "item_id": "kosher-salt",
                    "quantity": None,
                    "level": "low",
                    "acquired_on": None,
                    "expires_on": None,
                },
                {
                    "lot_id": "rice",
                    "item_id": "brown-rice",
                    "quantity": 1,
                    "level": None,
                    "acquired_on": None,
                    "expires_on": None,
                },
            ]
        )
        assessment = assess_inventory(
            [
                {"item_id": "kosher-salt", "quantity": 1},
                {"item_id": "brown-rice", "quantity": 2},
            ],
            root=self.root,
        )
        self.assertTrue(any("Kosher salt is low" in item for item in assessment["warnings"]))
        self.assertTrue(any("Brown rice" in item for item in assessment["warnings"]))

    def test_dry_run_prefers_matching_inventory(self) -> None:
        for recipe in load_recipes(self.root).values():
            if int(recipe["id"].split("-")[1]) > 4:
                Path(recipe["path"]).unlink()
        self.write_stock(
            [
                {
                    "lot_id": "turkey",
                    "item_id": "ground-turkey",
                    "quantity": 2,
                    "level": None,
                    "acquired_on": "2026-06-01",
                    "expires_on": None,
                },
                {
                    "lot_id": "rice",
                    "item_id": "brown-rice",
                    "quantity": 3,
                    "level": None,
                    "acquired_on": None,
                    "expires_on": None,
                },
            ]
        )
        proposals = generate_proposals(dt.date(2026, 6, 29), 3, root=self.root)
        self.assertEqual(proposals[0]["meals"][0]["name"], "Mild Turkey Taco Brown Rice Bowls")
        self.assertGreater(
            proposals[0]["inventory_coverage_score"],
            proposals[1]["inventory_coverage_score"],
        )


if __name__ == "__main__":
    unittest.main()
