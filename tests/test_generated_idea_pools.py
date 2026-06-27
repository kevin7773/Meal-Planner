from __future__ import annotations

import datetime as dt
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from planner.proposal import generated_ideas
from scripts.generated_idea_pools import validate_generated_idea_pools


ROOT = Path(__file__).resolve().parents[1]


class GeneratedIdeaPoolTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        shutil.copytree(ROOT / "planner-data", self.root / "planner-data")
        self.path = self.root / "planner-data" / "generated-idea-pools.json"

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def load_document(self) -> dict:
        return json.loads(self.path.read_text(encoding="utf-8"))

    def write_document(self, document: dict) -> None:
        self.path.write_text(
            json.dumps(document, indent=2) + "\n",
            encoding="utf-8",
        )

    def test_generated_idea_pools_are_valid(self) -> None:
        self.assertEqual(validate_generated_idea_pools(self.root), [])

    def test_rejects_unsupported_schema_version(self) -> None:
        document = self.load_document()
        document["schema_version"] = 2
        self.write_document(document)

        self.assertIn(
            "planner-data/generated-idea-pools.json: unsupported "
            "schema_version 2; supported version(s): 1",
            validate_generated_idea_pools(self.root),
        )

    def test_monday_requires_mexican_monday_tag(self) -> None:
        document = self.load_document()
        document["pools"]["Monday"][0]["tags"] = []
        self.write_document(document)

        self.assertIn(
            "Monday slot 1: Monday ideas require mexican-monday tag",
            validate_generated_idea_pools(self.root),
        )

    def test_tuesday_requires_low_effort_method(self) -> None:
        document = self.load_document()
        document["pools"]["Tuesday"][0]["cooking_method"] = "oven"
        self.write_document(document)

        self.assertIn(
            "Tuesday slot 1: Tuesday ideas must use a low-effort method",
            validate_generated_idea_pools(self.root),
        )

    def test_generation_uses_root_specific_data_and_stable_slot(self) -> None:
        document = self.load_document()
        monday = document["pools"]["Monday"]
        monday[0]["name"] = "Custom Pool Quesadillas"
        document["pools"]["Monday"] = list(reversed(monday))
        self.write_document(document)

        ideas = generated_ideas(dt.date(2026, 7, 6), self.root)

        self.assertEqual(
            ideas["IDEA-20260706-MON-1"]["name"],
            "Custom Pool Quesadillas",
        )


if __name__ == "__main__":
    unittest.main()
