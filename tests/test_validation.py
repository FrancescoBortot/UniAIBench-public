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
from validate_model_catalog import main as validate_model_catalog  # noqa: E402
from validate_public_repository import required_checklist_status  # noqa: E402
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


class PublicationGateTests(unittest.TestCase):
    def test_optional_checkbox_does_not_block_strict_gate(self) -> None:
        text = "- [x] <!-- required:rights --> confirmed\n- [ ] optional DOI\n"
        found, incomplete = required_checklist_status(text)
        self.assertEqual(found, {"rights"})
        self.assertEqual(incomplete, set())

    def test_unchecked_required_checkbox_is_reported(self) -> None:
        text = "- [ ] <!-- required:rights --> pending\n"
        found, incomplete = required_checklist_status(text)
        self.assertEqual(found, {"rights"})
        self.assertEqual(incomplete, {"rights"})

    def test_model_catalog_matches_published_tables(self) -> None:
        self.assertEqual(validate_model_catalog(), 0)


if __name__ == "__main__":
    unittest.main()
