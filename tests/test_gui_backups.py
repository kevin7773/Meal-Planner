from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKUP_SCRIPT = ROOT / "scripts" / "gui-backup.ps1"


class GuiBackupTests(unittest.TestCase):
    def run_backup(
        self,
        root: Path,
        operation: str = "test-write",
    ) -> Path:
        command = (
            f". '{BACKUP_SCRIPT}'; "
            f"New-MealPlannerGuiBackup -ProjectRoot '{root}' "
            f"-Operation '{operation}' -Paths @('recipes','inventory','missing')"
        )
        powershell = (
            shutil.which("pwsh")
            or shutil.which("powershell.exe")
            or shutil.which("powershell")
        )
        if powershell is None:
            self.skipTest("PowerShell is not available")
        arguments = [powershell, "-NoProfile", "-NonInteractive"]
        if Path(powershell).name.lower() == "powershell.exe":
            arguments.extend(["-ExecutionPolicy", "Bypass"])
        arguments.extend(["-Command", command])
        result = subprocess.run(
            arguments,
            check=True,
            capture_output=True,
            text=True,
        )
        return Path(result.stdout.strip().splitlines()[-1])

    def test_backup_preserves_files_and_writes_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "recipes").mkdir()
            (root / "inventory").mkdir()
            (root / "recipes" / "dinner.md").write_text(
                "family recipe\n",
                encoding="utf-8",
            )
            (root / "inventory" / "stock.json").write_text(
                '{"schema_version": 1}\n',
                encoding="utf-8",
            )

            backup = self.run_backup(root)
            manifest = json.loads(
                (backup / "manifest.json").read_text(encoding="utf-8")
            )

            self.assertRegex(
                backup.name,
                r"^\d{8}-\d{6}(?:-\d{2})?$",
            )
            self.assertEqual(
                (backup / "recipes" / "dinner.md").read_text(
                    encoding="utf-8"
                ),
                "family recipe\n",
            )
            self.assertEqual(manifest["schema_version"], 1)
            self.assertEqual(manifest["operation"], "test-write")
            self.assertEqual(manifest["file_count"], 2)
            self.assertEqual(
                {entry["path"]: entry["type"] for entry in manifest["paths"]},
                {
                    "recipes": "directory",
                    "inventory": "directory",
                    "missing": "missing",
                },
            )

    def test_same_second_backups_never_overwrite_each_other(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "recipes").mkdir()
            (root / "inventory").mkdir()

            first = self.run_backup(root, "first")
            second = self.run_backup(root, "second")

            self.assertNotEqual(first, second)
            self.assertTrue(first.exists())
            self.assertTrue(second.exists())

    def test_every_state_changing_gui_uses_shared_backup(self) -> None:
        expected_operations = {
            "inventory-gui.ps1": ("inventory-save",),
            "import-recipe-gui.ps1": (
                "recipe-edit-",
                "recipe-import",
                "recipe-idea-save",
                "recipe-promote-",
            ),
            "meal-override-gui.ps1": ("meal-override-",),
            "recipe-feedback.ps1": ("recipe-review-",),
            "plan-week.ps1": (
                "email-settings-save",
                "plan-commit-",
                "review-package-",
                "package-approve-",
                "email-send-",
            ),
        }
        for filename, operations in expected_operations.items():
            script = (ROOT / "scripts" / filename).read_text(encoding="utf-8")
            self.assertIn("gui-backup.ps1", script, filename)
            for operation in operations:
                self.assertIn(operation, script, filename)

    def test_backups_precede_persistent_write_calls(self) -> None:
        inventory = (
            ROOT / "scripts" / "inventory-gui.ps1"
        ).read_text(encoding="utf-8")
        self.assertLess(
            inventory.index("-Operation 'inventory-save'"),
            inventory.index("WriteAllText($stockPath"),
        )

        override = (
            ROOT / "scripts" / "meal-override-gui.ps1"
        ).read_text(encoding="utf-8")
        handler = override.split("$applyButton.Add_Click({", 1)[1]
        self.assertLess(
            handler.index('-Operation "meal-override-'),
            handler.index("$result = & $python @arguments"),
        )

        review = (
            ROOT / "scripts" / "recipe-feedback.ps1"
        ).read_text(encoding="utf-8")
        save_function = review.split("function Save-RecipeFeedback", 1)[1]
        self.assertLess(
            save_function.index('-Operation "recipe-review-'),
            save_function.index("WriteAllText($Recipe.Path"),
        )

        importer = (
            ROOT / "scripts" / "import-recipe-gui.ps1"
        ).read_text(encoding="utf-8")
        edit_branch = importer.split(
            "if ($null -ne $script:editingRecipeId)",
            1,
        )[1]
        self.assertLess(
            edit_branch.index('-Operation "recipe-edit-'),
            edit_branch.index("$result = & $python @arguments"),
        )
        import_branch = importer.split(
            "$arguments = @($importer,'apply')",
            1,
        )[1]
        self.assertLess(
            import_branch.index("-Operation 'recipe-import'"),
            import_branch.index("$result = & $python @arguments"),
        )
        idea_branch = importer.split("$saveIdeaButton.Add_Click({", 1)[1]
        self.assertLess(
            idea_branch.index("-Operation 'recipe-idea-save'"),
            idea_branch.index("$result = & $python @arguments"),
        )
        promotion_branch = importer.split("$promoteButton.Add_Click({", 1)[1]
        self.assertLess(
            promotion_branch.index('-Operation "recipe-promote-'),
            promotion_branch.index("$result = & $python $recipeEditor promote"),
        )

        planner = (
            ROOT / "scripts" / "plan-week.ps1"
        ).read_text(encoding="utf-8")
        ordered_pairs = (
            ("email-settings-save", "WriteAllText("),
            ("plan-commit-", "$result = & $python @arguments"),
            ("review-package-", "Invoke-WeekWorkflow -Command 'generate'"),
            ("package-approve-", "Invoke-WeekWorkflow `"),
            ("email-send-", "Invoke-WeekWorkflow `"),
        )
        for operation, write_call in ordered_pairs:
            operation_index = planner.index(operation)
            self.assertGreater(
                planner.find(write_call, operation_index),
                operation_index,
                operation,
            )

    def test_backup_directory_is_ignored_by_git(self) -> None:
        ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
        self.assertTrue(
            re.search(r"(?m)^\.backup/$", ignore),
        )


if __name__ == "__main__":
    unittest.main()
