from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class InventoryAttentionFilterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.script = (
            ROOT / "scripts" / "inventory-gui.ps1"
        ).read_text(encoding="utf-8")

    def test_filter_covers_each_inventory_attention_signal(self) -> None:
        self.assertIn("function Get-AttentionReasons", self.script)
        self.assertIn("$Lot.level -eq 'low'", self.script)
        self.assertIn("$total -lt $minimum", self.script)
        self.assertIn("$today.AddDays(7)", self.script)
        self.assertIn("Expired ", self.script)

    def test_button_toggles_between_attention_and_full_inventory(self) -> None:
        self.assertIn("$attentionButton.Add_Click", self.script)
        self.assertIn(
            "$script:attentionOnly = -not $script:attentionOnly",
            self.script,
        )
        self.assertIn("'Show All Inventory'", self.script)
        self.assertIn(
            "'Show Low Stock and Expiring'",
            self.script,
        )

    def test_low_stock_uses_aggregate_quantity_across_lots(self) -> None:
        self.assertIn("function Get-QuantityTotals", self.script)
        self.assertIn(
            "$totals[$lot.item_id] += [double]$lot.quantity",
            self.script,
        )

    def test_frozen_expiration_defaults_to_six_months(self) -> None:
        self.assertIn(
            "$expiresPicker.Value = $acquiredPicker.Value.AddMonths(6)",
            self.script,
        )
        self.assertIn(
            "$acquiredPicker.Add_ValueChanged",
            self.script,
        )


if __name__ == "__main__":
    unittest.main()
