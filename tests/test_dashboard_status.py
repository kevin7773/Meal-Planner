from __future__ import annotations

import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path

from planner.dashboard_status import (
    build_dashboard_status,
    inventory_warning_status,
    latest_backup_status,
    next_menu_status,
)


ROOT = Path(__file__).resolve().parents[1]


class DashboardStatusTests(unittest.TestCase):
    def test_repo_report_exposes_all_operational_statuses(self) -> None:
        report = build_dashboard_status(
            ROOT,
            today=dt.date(2026, 6, 29),
        )
        items = {item["key"]: item for item in report["items"]}

        self.assertEqual(report["schema_version"], 1)
        self.assertEqual(
            set(items),
            {
                "validation",
                "simulation",
                "recipes",
                "inventory",
                "menu",
                "backup",
            },
        )
        self.assertEqual(items["validation"]["state"], "success")
        self.assertEqual(items["recipes"]["value"], "43 recipes")

    def test_expired_inventory_is_an_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inventory = root / "inventory"
            inventory.mkdir()
            self.write_json(
                inventory / "catalog.json",
                {
                    "schema_version": 1,
                    "items": [
                        {
                            "id": "milk",
                            "name": "Milk",
                            "class": "refrigerated",
                            "unit": "cup",
                            "minimum": 0,
                            "unit_cost_usd": 0.3,
                        },
                        {
                            "id": "salt",
                            "name": "Salt",
                            "class": "consumable",
                            "unit": "level",
                            "minimum": 0,
                            "unit_cost_usd": 0.1,
                        },
                    ],
                },
            )
            self.write_json(
                inventory / "stock.json",
                {
                    "schema_version": 1,
                    "items": [
                        {
                            "item_id": "milk",
                            "quantity": 1,
                            "expires_on": "2026-06-28",
                        },
                        {
                            "item_id": "salt",
                            "quantity": None,
                            "level": "low",
                            "expires_on": None,
                        },
                    ],
                },
            )
            self.write_json(
                inventory / "recipe-requirements.json",
                {"schema_version": 1, "recipes": {}},
            )

            result = inventory_warning_status(
                root,
                today=dt.date(2026, 6, 29),
            )

        self.assertEqual(result["state"], "error")
        self.assertEqual(result["value"], "2 warning(s)")
        self.assertIn("1 expired", result["detail"])

    def test_one_broken_source_does_not_hide_other_status_rows(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            report = build_dashboard_status(
                Path(directory),
                today=dt.date(2026, 6, 29),
            )

        items = {item["key"]: item for item in report["items"]}
        self.assertEqual(len(items), 6)
        self.assertEqual(items["inventory"]["value"], "Unavailable")
        self.assertEqual(items["inventory"]["state"], "error")
        self.assertEqual(items["menu"]["value"], "Not planned")
        self.assertEqual(items["backup"]["value"], "None")

    def test_next_menu_prefers_current_or_nearest_future_week(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            menu_root = root / "menus" / "2026"
            menu_root.mkdir(parents=True)
            self.write_menu(menu_root / "2026-06-22.md", "archived")
            self.write_menu(menu_root / "2026-06-29.md", "completed")
            self.write_menu(menu_root / "2026-07-06.md", "draft")

            result = next_menu_status(
                root,
                today=dt.date(2026, 6, 29),
            )

        self.assertEqual(result["value"], "Completed")
        self.assertEqual(result["detail"], "Week of Jun 29, 2026")
        self.assertEqual(result["state"], "success")

    def test_latest_backup_uses_manifest_timestamp(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            older = root / ".backup" / "z-folder"
            newer = root / ".backup" / "a-folder"
            older.mkdir(parents=True)
            newer.mkdir(parents=True)
            self.write_json(
                older / "manifest.json",
                {
                    "created_at": "2026-06-27T20:00:00-04:00",
                    "operation": "older",
                    "file_count": 2,
                },
            )
            self.write_json(
                newer / "manifest.json",
                {
                    "created_at": "2026-06-28T20:00:00-04:00",
                    "operation": "newer",
                    "file_count": 5,
                },
            )

            result = latest_backup_status(root)

        self.assertIn("newer", result["detail"])
        self.assertIn("5 files", result["detail"])

    @staticmethod
    def write_json(path: Path, document: dict) -> None:
        path.write_text(json.dumps(document), encoding="utf-8")

    @staticmethod
    def write_menu(path: Path, status: str) -> None:
        path.write_text(
            "+++\n"
            'week_of = "2026-06-29"\n'
            f'status = "{status}"\n'
            "+++\n\n"
            "# Menu\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    unittest.main()
