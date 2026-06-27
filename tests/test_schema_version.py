from __future__ import annotations

import unittest

from scripts.schema_version import schema_version_errors


class SchemaVersionTests(unittest.TestCase):
    def test_accepts_current_version(self) -> None:
        self.assertEqual(
            schema_version_errors({"schema_version": 1}, "example.json"),
            [],
        )

    def test_requires_version_field(self) -> None:
        self.assertEqual(
            schema_version_errors({}, "example.json"),
            ["example.json: schema_version is required"],
        )

    def test_rejects_non_integer_version(self) -> None:
        self.assertEqual(
            schema_version_errors({"schema_version": "1"}, "example.json"),
            ["example.json: schema_version must be an integer"],
        )

    def test_reports_unsupported_version(self) -> None:
        self.assertEqual(
            schema_version_errors({"schema_version": 2}, "example.json"),
            [
                "example.json: unsupported schema_version 2; "
                "supported version(s): 1"
            ],
        )


if __name__ == "__main__":
    unittest.main()
