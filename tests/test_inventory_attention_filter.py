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

    def test_expiration_is_editable_with_fresh_produce_default(self) -> None:
        self.assertIn("$expiresPicker.Enabled = $true", self.script)
        self.assertIn(
            "$expiresPicker.Value = $acquiredPicker.Value.AddDays(5)",
            self.script,
        )

    def test_full_view_includes_untracked_catalog_items(self) -> None:
        self.assertIn("'Item ID'", self.script)
        self.assertIn(
            "foreach ($item in @($catalogDocument.items | Sort-Object name))",
            self.script,
        )
        self.assertIn(
            "$trackedItemIds.ContainsKey([string]$item.id)",
            self.script,
        )
        self.assertIn("'Not in inventory'", self.script)
        self.assertIn(
            "$grid.SelectedRows[0].Cells['ItemID'].Value",
            self.script,
        )

    def test_untracked_rows_are_added_but_cannot_be_removed(self) -> None:
        self.assertIn("$removeButton.Enabled = $false", self.script)
        self.assertIn(
            "if ([string]::IsNullOrWhiteSpace($lotId))",
            self.script,
        )
        self.assertIn("$addButton.Text = 'Add to Inventory'", self.script)
        self.assertIn("$addButton.Text = 'Update Lot'", self.script)

    def test_inventory_gui_exposes_mapping_completeness_report(self) -> None:
        self.assertIn(
            "$mappingButton.Text = 'Mapping Completeness'",
            self.script,
        )
        self.assertIn("inventory_mapping_report.py", self.script)
        self.assertIn(
            "$dialog.Text = 'Ingredient Mapping Completeness'",
            self.script,
        )


if __name__ == "__main__":
    unittest.main()
