from __future__ import annotations

import copy
import importlib.util
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from validate_judgment import validate as validate_judgment  # noqa: E402
from validate_rubric import validate as validate_rubric  # noqa: E402
from schema_validation import SchemaValidationError, validate_json_schema  # noqa: E402


class ClosedSchemaTests(unittest.TestCase):
    def load_contract(self, name: str) -> tuple[dict[str, object], dict[str, object]]:
        payload = json.loads((ROOT / f"templates/{name}.template.json").read_text())
        schema = json.loads((ROOT / f"schemas/{name}.schema.json").read_text())
        return payload, schema

    def test_rubric_template_is_valid(self) -> None:
        payload = json.loads((ROOT / "templates/rubric.template.json").read_text())
        validate_rubric(payload, template=True)

    def test_rubric_rejects_unknown_fields(self) -> None:
        payload = json.loads((ROOT / "templates/rubric.template.json").read_text())
        payload["unexpected"] = True
        with self.assertRaises(ValueError):
            validate_rubric(payload, template=True)

    def test_judgment_template_is_valid(self) -> None:
        payload = json.loads((ROOT / "templates/judgment.template.json").read_text())
        validate_judgment(payload, template=True)

    def test_judgment_rejects_unknown_fields(self) -> None:
        payload = json.loads((ROOT / "templates/judgment.template.json").read_text())
        payload["unexpected"] = True
        with self.assertRaises(ValueError):
            validate_judgment(payload, template=True)

    def test_schema_rejects_malformed_hash(self) -> None:
        payload, schema = self.load_contract("blind-batch-manifest")
        payload["responses"][0]["response_sha256"] = "NOT-A-HASH"
        with self.assertRaises(SchemaValidationError):
            validate_json_schema(payload, schema)

    def test_schema_enforces_dependent_properties(self) -> None:
        payload, schema = self.load_contract("blind-batch-manifest")
        del payload["item_artifacts"][0]["reference_sha256"]
        with self.assertRaises(SchemaValidationError):
            validate_json_schema(payload, schema)

    def test_schema_enforces_exclusive_maximum(self) -> None:
        payload, schema = self.load_contract("aggregation-config")
        payload["bootstrap"]["confidence_level"] = 1.0
        with self.assertRaises(SchemaValidationError):
            validate_json_schema(payload, schema)

    def test_schema_validates_additional_property_values(self) -> None:
        payload, schema = self.load_contract("aggregation-config")
        payload["item_aggregation"]["method"] = "weighted_mean"
        payload["item_aggregation"]["weights"] = {"temporary-item": 0}
        with self.assertRaises(SchemaValidationError):
            validate_json_schema(payload, schema)

    def test_schema_enforces_date_time_format(self) -> None:
        payload, schema = self.load_contract("blind-batch-manifest")
        payload["created_at"] = "not-a-date"
        with self.assertRaises(SchemaValidationError):
            validate_json_schema(payload, schema)

if __name__ == "__main__":
    unittest.main()
