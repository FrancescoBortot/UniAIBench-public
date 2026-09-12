from __future__ import annotations

import copy
import importlib.util
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "build_public_tables.py"
SPEC = importlib.util.spec_from_file_location("build_public_tables", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
TABLES = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TABLES)


class PublicTableTests(unittest.TestCase):
    def test_released_tables_are_byte_reproducible(self) -> None:
        with tempfile.TemporaryDirectory(prefix="uniaibench-table-test-") as temporary:
            output = Path(temporary)
            TABLES.generate_tables(output)
            self.assertEqual(TABLES.compare_tables(output), [])

    def test_resource_arithmetic_tampering_is_rejected(self) -> None:
        _, catalog, pricing, _, resources = TABLES.read_and_validate_inputs()
        row = copy.deepcopy(resources[0])
        row["analytical_total_tokens"] += 1
        with self.assertRaisesRegex(RuntimeError, "Invalid analytical total"):
            TABLES.validate_resource_row(
                row,
                catalog[row["model"]],
                pricing[row["model"]],
            )

    def test_released_table_inventory_is_complete(self) -> None:
        tracked = {path.name for path in TABLES.TABLE_ROOT.glob("*.csv")}
        self.assertEqual(tracked, TABLES.EXPECTED_TABLES)


if __name__ == "__main__":
    unittest.main()
