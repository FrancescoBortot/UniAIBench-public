from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "uniaibench" / "analysis" / "tools"))

from check_dependency_direction import python_dependency_reasons  # noqa: E402
from validate_model_catalog import main as validate_model_catalog  # noqa: E402
from validate_public_repository import (  # noqa: E402
    approved_blank_template,
    git_history_text_blobs,
    looks_like_completed_rubric,
    looks_like_final_adjudication,
    looks_like_identity_map,
    looks_like_individual_judgment,
    looks_like_source_manifest,
    looks_like_unblinded_results,
    private_path_reason,
    private_json_artifact_kind,
    required_checklist_status,
)


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

    def test_forbidden_directories_are_case_insensitive(self) -> None:
        for candidate in (
            "Router/file.txt",
            "router/file.txt",
            "nested/ReSuLtS/file.csv",
            "benchmark-workspace/private/identity-map.json",
            "benchmark-toolkit/local_data/item.txt",
        ):
            with self.subTest(candidate=candidate):
                self.assertEqual(
                    private_path_reason(candidate),
                    "contains a private-artifact directory",
                )

    def test_model_catalog_matches_published_tables(self) -> None:
        self.assertEqual(validate_model_catalog(), 0)

    def test_compiled_identity_map_shape_is_rejected(self) -> None:
        payload = {
            "campaign_id": "campaign",
            "batch_id": "batch",
            "blind_batch_manifest_path": "blind/manifest.json",
            "entries": [],
        }
        self.assertTrue(looks_like_identity_map(payload))

    def test_completed_rubric_shape_is_rejected(self) -> None:
        payload = {
            "rubric_version": "1.0",
            "item_id": "item-1",
            "atomic_criteria": [{"criterion_id": "C1"}],
            "dimension_point_budget": {"T1": 100},
            "human_approval": {"approved": True},
            "frozen": True,
        }
        self.assertTrue(looks_like_completed_rubric(payload))
        self.assertEqual(private_json_artifact_kind(payload), "item-specific rubric")

    def test_individual_judgment_shape_is_rejected(self) -> None:
        payload = {
            "judgment_version": "1.0",
            "item_id": "item-1",
            "response_id": "anonymous-1",
            "criterion_assessment": [{"criterion_id": "C1"}],
            "dimensions": {},
            "technical_score": {"final_score": 80},
        }
        self.assertTrue(looks_like_individual_judgment(payload))
        self.assertEqual(private_json_artifact_kind(payload), "individual judgment")

    def test_source_manifest_shape_is_rejected(self) -> None:
        payload = {
            "schema_version": "1.0",
            "campaign_id": "campaign",
            "batch_id": "batch",
            "judging_contract": {},
            "responses": [{
                "source_run_id": "run-1",
                "system_id": "system-1",
                "response_path": "responses/run-1.txt",
                "model_identity": {"provider": "provider"},
            }],
        }
        self.assertTrue(looks_like_source_manifest(payload))
        self.assertEqual(private_json_artifact_kind(payload), "private source manifest")

    def test_operational_blind_batch_shape_is_rejected(self) -> None:
        payload = {
            "$schema": "../schemas/blind-batch-manifest.schema.json",
            "schema_version": "1.0",
            "campaign_id": "campaign",
            "batch_id": "batch",
            "judging_contract": {},
            "item_artifacts": [{"item_id": "item-1"}],
            "responses": [{"anonymous_response_id": "anonymous-1"}],
        }
        self.assertEqual(
            private_json_artifact_kind(payload), "operational blind-batch manifest"
        )

    def test_final_adjudication_shape_is_rejected(self) -> None:
        payload = {
            "adjudication_id": "decision-1",
            "decision_status": "final",
            "reviewer": {"human_confirmed": True},
            "decision": {"outcome": "uphold"},
            "impact": {},
            "affected_response_ids": ["anonymous-1"],
            "reevaluation": {"required": False},
        }
        self.assertTrue(looks_like_final_adjudication(payload))
        self.assertEqual(private_json_artifact_kind(payload), "adjudication record")

    def test_unblinded_result_shape_is_rejected(self) -> None:
        payload = {
            "campaign_id": "campaign",
            "batch_id": "batch",
            "blind_batch_manifest_path": "blind/manifest.json",
            "identity_map_path": "private/identity-map.json",
            "identity_map_sha256": "a" * 64,
            "records": [],
        }
        self.assertTrue(looks_like_unblinded_results(payload))
        self.assertEqual(private_json_artifact_kind(payload), "private unblinded results")

    def test_only_canonical_blank_private_artifact_templates_are_allowed(self) -> None:
        template_paths = (
            "benchmark-toolkit/templates/adjudication.template.json",
            "benchmark-toolkit/templates/blind-batch-manifest.template.json",
            "benchmark-toolkit/templates/identity-map.template.json",
            "benchmark-toolkit/templates/judgment.template.json",
            "benchmark-toolkit/templates/rubric.template.json",
        )
        for relative_path in template_paths:
            with self.subTest(relative_path=relative_path):
                payload = json.loads((ROOT / relative_path).read_text(encoding="utf-8"))
                kind = private_json_artifact_kind(payload)
                self.assertIsNotNone(kind)
                assert kind is not None
                self.assertTrue(approved_blank_template(relative_path, kind, payload))
                self.assertFalse(
                    approved_blank_template(f"copies/{Path(relative_path).name}", kind, payload)
                )

    def test_filled_canonical_template_is_not_approved(self) -> None:
        relative_path = "benchmark-toolkit/templates/rubric.template.json"
        payload = json.loads((ROOT / relative_path).read_text(encoding="utf-8"))
        payload = copy.deepcopy(payload)
        payload["frozen"] = True
        payload["human_approval"]["approved"] = True
        kind = private_json_artifact_kind(payload)
        assert kind is not None
        self.assertFalse(approved_blank_template(relative_path, kind, payload))

    def test_private_environment_variants_are_rejected_by_path(self) -> None:
        self.assertEqual(
            private_path_reason("nested/.env.local"),
            "contains a forbidden environment filename",
        )
        self.assertEqual(
            private_path_reason("nested/.env"),
            "contains a forbidden artifact filename",
        )
        self.assertIsNone(private_path_reason("benchmark-toolkit/.env.example"))

    def test_history_scanner_finds_deleted_private_json(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary)
            subprocess.run(["git", "init", "-q"], cwd=repository, check=True)
            subprocess.run(
                ["git", "config", "user.email", "test@example.invalid"],
                cwd=repository,
                check=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Publication Gate Test"],
                cwd=repository,
                check=True,
            )
            historical = repository / "archived.json"
            historical.write_text(
                json.dumps({
                    "schema_version": "1.0",
                    "campaign_id": "campaign",
                    "batch_id": "batch",
                    "judging_contract": {},
                    "responses": [{
                        "source_run_id": "run-1",
                        "system_id": "system-1",
                        "response_path": "response.txt",
                        "model_identity": {},
                    }],
                }),
                encoding="utf-8",
            )
            subprocess.run(["git", "add", "archived.json"], cwd=repository, check=True)
            subprocess.run(
                ["git", "commit", "-qm", "historical artifact"],
                cwd=repository,
                check=True,
            )
            historical.unlink()
            subprocess.run(["git", "add", "-u"], cwd=repository, check=True)
            subprocess.run(
                ["git", "commit", "-qm", "remove artifact"],
                cwd=repository,
                check=True,
            )

            blobs = list(git_history_text_blobs(repository))
            archived_payload = next(
                json.loads(text) for _, path, text in blobs if path == "archived.json"
            )
            self.assertEqual(
                private_json_artifact_kind(archived_payload), "private source manifest"
            )


class DependencyDirectionTests(unittest.TestCase):
    def test_study_import_is_rejected(self) -> None:
        reasons = python_dependency_reasons("import uniaibench.analysis\n")
        self.assertTrue(reasons)

    def test_study_path_is_rejected(self) -> None:
        reasons = python_dependency_reasons('SOURCE = "../uniaibench/analysis/data"\n')
        self.assertTrue(reasons)

    def test_descriptive_project_name_is_allowed(self) -> None:
        reasons = python_dependency_reasons('TITLE = "UniAIBench methodology"\n')
        self.assertEqual(reasons, [])


if __name__ == "__main__":
    unittest.main()
