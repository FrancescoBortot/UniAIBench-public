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


class ClosedSchemaTests(unittest.TestCase):
    def test_rubric_template_is_valid(self) -> None:
        payload = json.loads((ROOT / "rubrics/templates/rubric.template.json").read_text())
        validate_rubric(payload, template=True)

    def test_rubric_rejects_unknown_fields(self) -> None:
        payload = json.loads((ROOT / "rubrics/templates/rubric.template.json").read_text())
        payload["unexpected"] = True
        with self.assertRaises(ValueError):
            validate_rubric(payload, template=True)

    def test_judgment_template_is_valid(self) -> None:
        payload = json.loads((ROOT / "schemas/judgment.template.json").read_text())
        validate_judgment(payload, template=True)

    def test_judgment_rejects_unknown_fields(self) -> None:
        payload = json.loads((ROOT / "schemas/judgment.template.json").read_text())
        payload["unexpected"] = True
        with self.assertRaises(ValueError):
            validate_judgment(payload, template=True)


if __name__ == "__main__":
    unittest.main()
