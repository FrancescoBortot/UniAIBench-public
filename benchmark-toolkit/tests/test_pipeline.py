from __future__ import annotations

import json
import io
import stat
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch


TOOLKIT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLKIT_ROOT / "tools"))
sys.path.insert(0, str(TOOLKIT_ROOT / "harness"))

import benchmark_harness  # noqa: E402
import google_benchmark_harness  # noqa: E402
import aggregate_results  # noqa: E402
import validate_config as validate_config_cli  # noqa: E402
from aggregate_results import aggregate  # noqa: E402
from prepare_blind_batch import prepare  # noqa: E402
from record_adjudication import record  # noqa: E402
from unblind_results import unblind  # noqa: E402
from validate_blind_batch import (  # noqa: E402
    load_json_object,
    sha256_file,
    validate_identity_map,
    validate_manifest,
)
from validate_judgment_batch import load_adjudication_directives, validate_batch  # noqa: E402
from schema_validation import validate_json_schema  # noqa: E402


DIMENSION_BUDGETS = {
    "T1": 20,
    "T2": 15,
    "T3": 20,
    "T4": 15,
    "T5": 10,
    "T6": 8,
    "T7": 7,
    "T8": 5,
}


def dump(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def make_rubric(item_id: str) -> dict[str, object]:
    criteria = []
    for dimension, points in DIMENSION_BUDGETS.items():
        criteria.append(
            {
                "criterion_id": f"criterion-{dimension.lower()}",
                "subproblem_id": "part-1",
                "primary_dimension": dimension,
                "max_points": points,
                "description": f"Observable evidence for {dimension}",
                "full_credit_evidence": ["complete evidence"],
                "partial_credit_rules": [
                    {"credit_fraction": 0.5, "anchor": "partial evidence"}
                ],
                "zero_credit_conditions": ["no evidence"],
                "accepted_equivalences": [],
                "accepted_alternative_methods": [],
                "propagated_error_policy": "Do not double-count one upstream error.",
            }
        )
    return {
        "rubric_version": "1.0",
        "judge_spec_version": "1.0",
        "item_id": item_id,
        "subject": "temporary-test-domain",
        "domain_profile": {
            "discipline": "temporary-test-domain",
            "topic": "temporary-test-topic",
            "task_type": "open-response",
            "domain_specific_fields": {},
        },
        "created_without_model_answers": True,
        "frozen": True,
        "reference_status": "verified",
        "reference_notes": "Checked for the temporary test.",
        "subproblems": [
            {
                "id": "part-1",
                "weight": 1.0,
                "request": "Complete the temporary task.",
                "expected_results": ["temporary result"],
                "required_conditions": [],
                "accepted_equivalences": [],
                "accepted_alternative_methods": [],
            }
        ],
        "atomic_criteria": criteria,
        "dimension_applicability": {dimension: "applicable" for dimension in DIMENSION_BUDGETS},
        "dimension_point_budget": DIMENSION_BUDGETS,
        "rubric_specific_caps": [],
        "human_review_triggers": [],
        "human_approval": {
            "approved": True,
            "reviewer": "temporary-reviewer",
            "date": "2026-01-01",
        },
    }


def make_judgment(response_id: str, item_id: str, score: float) -> dict[str, object]:
    fraction = score / 100.0
    criteria = [
        {
            "criterion_id": f"criterion-{dimension.lower()}",
            "primary_dimension": dimension,
            "max_points": points,
            "credit_fraction": fraction,
            "awarded_points": points * fraction,
            "evidence": "Temporary test evidence.",
            "justification": "Temporary test justification.",
        }
        for dimension, points in DIMENSION_BUDGETS.items()
    ]
    dimensions = {
        dimension: {
            "score": points * fraction,
            "max_score": points,
            "status": "scored",
            "summary": "Temporary test score.",
        }
        for dimension, points in DIMENSION_BUDGETS.items()
    }
    return {
        "judgment_version": "1.0",
        "item_id": item_id,
        "response_id": response_id,
        "rubric_version": "1.0",
        "criterion_assessment": criteria,
        "dimensions": dimensions,
        "technical_score": {
            "raw_score": score,
            "applicable_max_score": 100,
            "normalized_score_before_penalties": score,
            "extra_penalty_total": 0,
            "score_after_penalties": score,
            "applied_cap": None,
            "final_score": score,
        },
        "atomic_errors": [],
        "extra_penalties": [],
        "cap": {"applied": False, "value": None, "reason": ""},
        "result_status": "complete",
        "technical_summary": "Temporary complete judgment.",
        "judge_confidence": "high",
        "review_flags": [],
        "requires_human_review": False,
        "human_review_reason": "",
        "run_validity": "valid",
    }


def make_review_adjudication(
    root: Path,
    response_id: str,
    judgment_path: Path,
    outcome: str,
) -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "adjudication_id": f"temporary-{outcome}",
        "adjudication_version": 1,
        "decision_status": "final",
        "supersedes_adjudication_id": None,
        "supersedes_adjudication_sha256": None,
        "campaign_id": "temporary-campaign",
        "batch_id": "temporary-batch",
        "recorded_at": "2026-01-01T00:00:00Z",
        "reviewer": {
            "reviewer_id": "temporary-reviewer",
            "role": "human-reviewer",
            "human_confirmed": True,
        },
        "trigger": {
            "type": "requires_human_review",
            "summary": "The judgment requested human review.",
            "evidence": "The frozen judgment contains an explicit review flag.",
        },
        "source_artifacts": [
            {
                "artifact_type": "judgment",
                "artifact_id": response_id,
                "path": judgment_path.relative_to(root).as_posix(),
                "sha256": sha256_file(judgment_path),
            }
        ],
        "classification": "response_only",
        "decision": {
            "outcome": outcome,
            "summary": f"Record the {outcome} disposition.",
            "technical_rationale": "The human reviewer inspected the cited judgment.",
        },
        "impact": {
            "reference": {
                "changed": False,
                "previous_version": None,
                "replacement_version": None,
            },
            "rubric": {
                "changed": False,
                "previous_version": None,
                "replacement_version": None,
            },
            "response_validity": {"changed": False, "new_status": None},
            "scores": {"changed": False, "requires_recomputation": False},
        },
        "affected_response_ids": [response_id],
        "reevaluation": {
            "required": False,
            "scope": "none",
            "reason": "",
            "replacement_artifact_paths": [],
        },
        "superseded_artifacts": [],
        "notes": "",
    }
class TemporaryPipeline:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.item_id = "temporary-item-1"
        (root / "items").mkdir()
        (root / "responses").mkdir()
        (root / "rubrics").mkdir()
        (root / "references").mkdir()
        (root / "contract").mkdir()
        (root / "items/item-1.txt").write_text("Temporary task text.\n", encoding="utf-8")
        (root / "references/item-1.txt").write_text("Temporary checked reference.\n", encoding="utf-8")
        dump(root / "rubrics/item-1.json", make_rubric(self.item_id))
        for source, destination in (
            (TOOLKIT_ROOT / "prompts/judge-prompt.md", root / "contract/judge-prompt.md"),
            (TOOLKIT_ROOT / "schemas/judgment.schema.json", root / "contract/judgment.schema.json"),
            (TOOLKIT_ROOT / "tools/validate_judgment.py", root / "contract/validate_judgment.py"),
            (TOOLKIT_ROOT / "tools/schema_validation.py", root / "contract/schema_validation.py"),
        ):
            destination.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

        response_specs = [
            ("system-a", "1", 100.0),
            ("system-a", "2", 80.0),
            ("system-b", "1", 60.0),
            ("system-b", "2", 40.0),
        ]
        self.scores: dict[tuple[str, str], float] = {}
        responses = []
        for system_id, repetition_id, score in response_specs:
            source_run_id = f"{system_id}-run-{repetition_id}"
            response_path = f"responses/{source_run_id}.txt"
            (root / response_path).write_text(
                f"Temporary response from {source_run_id}.\n", encoding="utf-8"
            )
            self.scores[(system_id, repetition_id)] = score
            responses.append(
                {
                    "source_run_id": source_run_id,
                    "system_id": system_id,
                    "repetition_id": repetition_id,
                    "item_id": self.item_id,
                    "response_path": response_path,
                    "item_path": "items/item-1.txt",
                    "rubric_path": "rubrics/item-1.json",
                    "reference_path": "references/item-1.txt",
                    "model_identity": {"display_name": system_id},
                }
            )
        self.source_manifest = root / "source-manifest.json"
        dump(
            self.source_manifest,
            {
                "schema_version": "1.0",
                "campaign_id": "temporary-campaign",
                "batch_id": "temporary-batch",
                "judging_contract": {
                    "judge_spec_version": "1.0",
                    "judge_prompt_path": "contract/judge-prompt.md",
                    "judgment_schema_path": "contract/judgment.schema.json",
                    "validator_path": "contract/validate_judgment.py",
                    "validator_support_path": "contract/schema_validation.py",
                    "validator_version": "1.0",
                },
                "responses": responses,
            },
        )
        self.blind_dir = root / "blind/temporary-batch"
        self.identity_map = root / "private/identity-map.json"
        self.manifest = self.blind_dir / "blind-batch-manifest.json"

    def prepare(self) -> None:
        prepare(self.source_manifest, self.blind_dir, self.identity_map)

    def write_judgments(self) -> None:
        identity = load_json_object(self.identity_map)
        for entry in identity["entries"]:
            score = self.scores[(entry["system_id"], entry["repetition_id"])]
            path = self.blind_dir / entry["planned_judgment_path"]
            dump(path, make_judgment(entry["anonymous_response_id"], entry["item_id"], score))


def make_aggregation_config(
    unblinded_path: Path,
    *,
    declared_input_path: str | None = None,
    missing_policy: str = "fail",
    output_directory: str = "reports/temporary-aggregation",
    system_table_csv: str = "systems.csv",
    cell_table_csv: str = "cells.csv",
    summary_json: str = "summary.json",
) -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "aggregation_id": "temporary-aggregation",
        "status": "frozen",
        "input": {
            "unblinded_results_path": declared_input_path or unblinded_path.name,
            "unblinded_results_sha256": sha256_file(unblinded_path),
        },
        "fields": {
            "system_field": "system_id",
            "item_field": "item_id",
            "repetition_field": "repetition_id",
            "score_field": "final_score",
        },
        "eligibility": {
            "field": "judgment.run_validity",
            "accepted_values": ["valid"],
        },
        "repetition_aggregation": {
            "method": "mean",
            "expected_repetitions_per_cell": 2,
        },
        "missing_data": {"policy": missing_policy},
        "item_aggregation": {"method": "mean", "weights": {}},
        "bootstrap": {
            "enabled": False,
            "method": "percentile",
            "samples": 1,
            "confidence_level": 0.95,
            "seed": 17,
            "resampling_unit": "item",
        },
        "outputs": {
            "directory": output_directory,
            "system_table_csv": system_table_csv,
            "cell_table_csv": cell_table_csv,
            "summary_json": summary_json,
        },
    }


class PipelineTests(unittest.TestCase):
    def test_google_wrapper_preserves_equals_style_config_argument(self) -> None:
        arguments = ["google_benchmark_harness.py", "plan", "--config=/tmp/custom.json"]
        with patch.object(sys, "argv", arguments):
            with patch.object(
                google_benchmark_harness.benchmark_harness, "main", return_value=0
            ) as harness_main:
                self.assertEqual(google_benchmark_harness.main(), 0)
        harness_main.assert_called_once_with()
        self.assertEqual(arguments.count("--config"), 0)

    def test_external_config_display_and_relative_resolution(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            external_config = root / "campaign.json"
            template = load_json_object(
                TOOLKIT_ROOT / "configs" / "benchmark_config.template.json"
            )
            dump(external_config, template)
            output = io.StringIO()
            with patch.object(sys, "argv", ["validate_config.py", str(external_config)]):
                with redirect_stdout(output):
                    self.assertEqual(validate_config_cli.main(), 0)
            self.assertIn(str(external_config), output.getvalue())

            config = {
                "_runtime_config_directory": str(root),
                "prompt_file": "prompts/solver.md",
            }
            self.assertEqual(
                benchmark_harness.resolve_config_path(config, "prompt_file"),
                root / "prompts/solver.md",
            )

    def test_harness_rejects_unsafe_or_colliding_output_paths(self) -> None:
        template = load_json_object(
            TOOLKIT_ROOT / "configs" / "benchmark_config.template.json"
        )

        unsafe_session = json.loads(json.dumps(template))
        unsafe_session["sessions"] = ["../escape"]
        with self.assertRaisesRegex(ValueError, "safe path component"):
            benchmark_harness.validate_config(unsafe_session)

        unsafe_glob = json.loads(json.dumps(template))
        unsafe_glob["item_filename_glob"] = "../*.txt"
        with self.assertRaisesRegex(ValueError, "filename pattern"):
            benchmark_harness.validate_config(unsafe_glob)

        duplicate_destination = json.loads(json.dumps(template))
        duplicate_destination["models"].append(
            json.loads(json.dumps(duplicate_destination["models"][0]))
        )
        with self.assertRaisesRegex(ValueError, "unique .*output destinations"):
            benchmark_harness.validate_config(duplicate_destination)

        with self.assertRaisesRegex(ValueError, "unresolved .*PLACEHOLDER"):
            benchmark_harness.validate_config(template)

        unsupported_bundle = json.loads(json.dumps(template))
        unsupported_bundle["task_unit"] = "session"
        with self.assertRaises(ValueError):
            benchmark_harness.validate_config(unsupported_bundle)

    def test_session_directory_template_cannot_escape_dataset_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            dataset_root = Path(temporary) / "dataset"
            dataset_root.mkdir()
            config = {"session_directory_template": "../{session}"}
            with self.assertRaisesRegex(ValueError, "escapes dataset_root"):
                benchmark_harness.session_directory(
                    config, dataset_root, 2026, "session-1"
                )

    def test_discovered_item_symlink_cannot_escape_dataset_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            dataset_root = root / "dataset"
            session_dir = dataset_root / "sessions" / "session-1"
            session_dir.mkdir(parents=True)
            outside = root / "outside.txt"
            outside.write_text("private source\n", encoding="utf-8")
            (session_dir / "item_1.txt").symlink_to(outside)
            config = {
                "_runtime_config_directory": str(root),
                "dataset_root": "dataset",
                "assessment_metadata": {"year": 2026},
                "sessions": ["session-1"],
                "session_directory_template": "sessions/{session}",
                "item_filename_glob": "item_*.txt",
                "item_filename_regex": r"item_(\d+)\.txt",
                "expected_items_per_session": 1,
            }
            with self.assertRaisesRegex(ValueError, "escapes dataset_root"):
                benchmark_harness.discover_items(config)

    def test_workflow_templates_validate_against_their_schemas(self) -> None:
        names = (
            "blind-batch-manifest",
            "identity-map",
            "adjudication",
            "aggregation-config",
        )
        for name in names:
            with self.subTest(contract=name):
                template = load_json_object(TOOLKIT_ROOT / "templates" / f"{name}.template.json")
                schema = load_json_object(TOOLKIT_ROOT / "schemas" / f"{name}.schema.json")
                validate_json_schema(template, schema)

    def test_complete_pipeline_and_refuse_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = TemporaryPipeline(Path(temporary))
            workspace.prepare()
            manifest = validate_manifest(workspace.manifest)
            identity = validate_identity_map(
                workspace.manifest, manifest, workspace.identity_map
            )
            self.assertEqual(len(manifest["responses"]), 4)
            self.assertEqual(len(identity["entries"]), 4)
            self.assertNotIn("system-a", workspace.manifest.read_text(encoding="utf-8"))
            with self.assertRaisesRegex(ValueError, "refusing to overwrite"):
                workspace.prepare()

            workspace.write_judgments()
            first_judgment = workspace.blind_dir / manifest["responses"][0]["planned_judgment_path"]
            frozen_validator = workspace.blind_dir / manifest["judging_contract"]["validator_path"]
            subprocess.run(
                [sys.executable, str(frozen_validator), str(first_judgment)],
                check=True,
                capture_output=True,
                text=True,
            )
            batch = validate_batch(
                workspace.manifest,
                identity_map_path=workspace.identity_map,
            )
            self.assertTrue(batch["ready_for_unblinding"])

            unblinded_path = workspace.root / "private/unblinded.json"
            result = unblind(workspace.manifest, workspace.identity_map, unblinded_path)
            self.assertEqual(result["record_count"], 4)
            with self.assertRaisesRegex(ValueError, "refusing to overwrite"):
                unblind(workspace.manifest, workspace.identity_map, unblinded_path)

            config_path = workspace.root / "aggregation.json"
            dump(
                config_path,
                {
                    "schema_version": "1.0",
                    "aggregation_id": "temporary-aggregation",
                    "status": "frozen",
                    "input": {
                        "unblinded_results_path": "private/unblinded.json",
                        "unblinded_results_sha256": sha256_file(unblinded_path),
                    },
                    "fields": {
                        "system_field": "system_id",
                        "item_field": "item_id",
                        "repetition_field": "repetition_id",
                        "score_field": "final_score",
                    },
                    "eligibility": {
                        "field": "judgment.run_validity",
                        "accepted_values": ["valid"],
                    },
                    "repetition_aggregation": {
                        "method": "mean",
                        "expected_repetitions_per_cell": 2,
                    },
                    "missing_data": {"policy": "fail"},
                    "item_aggregation": {"method": "mean", "weights": {}},
                    "bootstrap": {
                        "enabled": True,
                        "method": "percentile",
                        "samples": 100,
                        "confidence_level": 0.95,
                        "seed": 17,
                        "resampling_unit": "item",
                    },
                    "outputs": {
                        "directory": "reports/temporary-aggregation",
                        "system_table_csv": "systems.csv",
                        "cell_table_csv": "cells.csv",
                        "summary_json": "summary.json",
                    },
                },
            )
            summary = aggregate(config_path)
            means = {row["system_id"]: row["mean_score"] for row in summary["systems"]}
            self.assertEqual(means, {"system-a": 90.0, "system-b": 50.0})
            self.assertEqual(
                summary["software"],
                {"name": "benchmark-toolkit.aggregate_results", "version": "1.0"},
            )
            self.assertEqual(summary["fields"]["score_field"], "final_score")
            with self.assertRaisesRegex(ValueError, "refusing to overwrite"):
                aggregate(config_path)

    def test_tampering_and_non_bijective_map_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = TemporaryPipeline(Path(temporary))
            workspace.prepare()
            manifest = load_json_object(workspace.manifest)
            blind_path = workspace.blind_dir / manifest["responses"][0]["blind_input_path"]
            original = blind_path.read_text(encoding="utf-8")
            blind_path.write_text(original + "tampered\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                validate_manifest(workspace.manifest)
            blind_path.write_text(original, encoding="utf-8")

            identity = load_json_object(workspace.identity_map)
            identity["entries"].pop()
            dump(workspace.identity_map, identity)
            with self.assertRaisesRegex(ValueError, "bijection mismatch"):
                validate_identity_map(workspace.manifest, manifest, workspace.identity_map)

    def test_rubric_and_judging_contract_versions_must_match(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = TemporaryPipeline(Path(temporary))
            source = load_json_object(workspace.source_manifest)
            source["judging_contract"]["judge_spec_version"] = "different-version"
            dump(workspace.source_manifest, source)
            with self.assertRaisesRegex(ValueError, "judge_spec_version"):
                workspace.prepare()

    def test_aggregation_fail_policy_rejects_top_level_exclusions(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = TemporaryPipeline(Path(temporary))
            workspace.prepare()
            workspace.write_judgments()
            unblinded_path = workspace.root / "unblinded.json"
            unblind(workspace.manifest, workspace.identity_map, unblinded_path)
            payload = load_json_object(unblinded_path)
            removed = payload["records"].pop()
            payload["exclusions"].append(
                {
                    "system_id": removed["system_id"],
                    "item_id": removed["item_id"],
                    "repetition_id": removed["repetition_id"],
                    "reason": "temporary upstream exclusion",
                }
            )
            dump(unblinded_path, payload)
            config_path = workspace.root / "aggregation.json"
            dump(config_path, make_aggregation_config(unblinded_path))

            with self.assertRaisesRegex(ValueError, "input contains exclusions"):
                aggregate(config_path)

    def test_aggregation_coverage_includes_top_level_excluded_items(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = TemporaryPipeline(Path(temporary))
            workspace.prepare()
            workspace.write_judgments()
            unblinded_path = workspace.root / "unblinded.json"
            unblind(workspace.manifest, workspace.identity_map, unblinded_path)
            payload = load_json_object(unblinded_path)
            payload["exclusions"] = [
                {
                    "system_id": system_id,
                    "item_id": "temporary-item-2",
                    "repetition_id": "1",
                    "reason": "temporary upstream exclusion",
                }
                for system_id in ("system-a", "system-b")
            ]
            dump(unblinded_path, payload)
            config_path = workspace.root / "aggregation.json"
            dump(
                config_path,
                make_aggregation_config(
                    unblinded_path, missing_policy="available_case"
                ),
            )

            summary = aggregate(config_path)
            self.assertEqual(summary["counts"]["input_exclusions"], 2)
            self.assertEqual(summary["counts"]["items"], 2)
            self.assertEqual(
                {row["system_id"]: row["coverage"] for row in summary["systems"]},
                {"system-a": 0.5, "system-b": 0.5},
            )

    def test_aggregation_rejects_output_collisions_before_creating_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = TemporaryPipeline(Path(temporary))
            workspace.prepare()
            workspace.write_judgments()
            unblinded_path = workspace.root / "unblinded.json"
            unblind(workspace.manifest, workspace.identity_map, unblinded_path)
            config_path = workspace.root / "aggregation.json"
            dump(
                config_path,
                make_aggregation_config(
                    unblinded_path,
                    system_table_csv="duplicate.csv",
                    cell_table_csv="duplicate.csv",
                ),
            )

            with self.assertRaisesRegex(ValueError, "filenames must be distinct"):
                aggregate(config_path)
            self.assertFalse((workspace.root / "reports/temporary-aggregation").exists())

    def test_aggregation_confines_configured_paths_to_operational_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = TemporaryPipeline(Path(temporary))
            workspace.prepare()
            workspace.write_judgments()
            unblinded_path = workspace.root / "unblinded.json"
            unblind(workspace.manifest, workspace.identity_map, unblinded_path)
            configs_dir = workspace.root / "configs"
            configs_dir.mkdir()
            config_path = configs_dir / "aggregation.json"
            dump(
                config_path,
                make_aggregation_config(
                    unblinded_path, declared_input_path="../unblinded.json"
                ),
            )

            with self.assertRaisesRegex(ValueError, "escapes the aggregation operational root"):
                aggregate(config_path)

    def test_aggregation_cleans_staging_directory_after_write_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = TemporaryPipeline(Path(temporary))
            workspace.prepare()
            workspace.write_judgments()
            unblinded_path = workspace.root / "unblinded.json"
            unblind(workspace.manifest, workspace.identity_map, unblinded_path)
            config_path = workspace.root / "aggregation.json"
            dump(config_path, make_aggregation_config(unblinded_path))
            original_write_csv = aggregate_results.write_csv
            calls = 0

            def fail_second_write(*args: object, **kwargs: object) -> None:
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise OSError("temporary write failure")
                original_write_csv(*args, **kwargs)

            with patch.object(aggregate_results, "write_csv", side_effect=fail_second_write):
                with self.assertRaisesRegex(OSError, "temporary write failure"):
                    aggregate(config_path)
            self.assertFalse((workspace.root / "reports/temporary-aggregation").exists())
            self.assertEqual(list((workspace.root / "reports").glob(".*.staging-*")), [])

    def test_planned_judgments_are_confined_and_disjoint_from_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = TemporaryPipeline(Path(temporary))
            workspace.prepare()
            manifest = load_json_object(workspace.manifest)
            response = manifest["responses"][0]

            response["planned_judgment_path"] = response["blind_input_path"]
            with self.assertRaisesRegex(ValueError, "judgments directory|collides"):
                validate_manifest(workspace.manifest, manifest)

            response["planned_judgment_path"] = "other-output/judgment.json"
            with self.assertRaisesRegex(ValueError, "judgments directory"):
                validate_manifest(workspace.manifest, manifest)

    def test_adjudication_is_final_human_confirmed_and_append_only(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            evidence = root / "evidence/judgment.json"
            dump(evidence, {"temporary": "evidence"})
            draft = root / "drafts/adjudication.json"
            decision = {
                "schema_version": "1.0",
                "adjudication_id": "temporary-adjudication-1",
                "adjudication_version": 1,
                "decision_status": "final",
                "supersedes_adjudication_id": None,
                "supersedes_adjudication_sha256": None,
                "campaign_id": "temporary-campaign",
                "batch_id": "temporary-batch",
                "recorded_at": "2026-01-01T00:00:00Z",
                "reviewer": {
                    "reviewer_id": "temporary-reviewer",
                    "role": "human-reviewer",
                    "human_confirmed": True,
                },
                "trigger": {
                    "type": "judge_error",
                    "summary": "Temporary review trigger.",
                    "evidence": "Temporary observable evidence.",
                },
                "source_artifacts": [
                    {
                        "artifact_type": "judgment",
                        "artifact_id": "temporary-judgment",
                        "path": "evidence/judgment.json",
                        "sha256": sha256_file(evidence),
                    }
                ],
                "classification": "response_only",
                "decision": {
                    "outcome": "uphold",
                    "summary": "Temporary decision.",
                    "technical_rationale": "Temporary technical rationale.",
                },
                "impact": {
                    "reference": {"changed": False, "previous_version": None, "replacement_version": None},
                    "rubric": {"changed": False, "previous_version": None, "replacement_version": None},
                    "response_validity": {"changed": False, "new_status": None},
                    "scores": {"changed": False, "requires_recomputation": False},
                },
                "affected_response_ids": ["temporary-response"],
                "reevaluation": {
                    "required": False,
                    "scope": "none",
                    "reason": "",
                    "replacement_artifact_paths": [],
                },
                "superseded_artifacts": [],
                "notes": "",
            }
            dump(draft, decision)
            output = root / "adjudications/adjudication-1.json"
            record(draft, output, root)
            self.assertTrue(output.is_file())
            self.assertEqual(stat.S_IMODE(output.stat().st_mode), 0o600)
            with self.assertRaisesRegex(ValueError, "refusing to overwrite"):
                record(draft, output, root)

            unsafe_uphold = json.loads(json.dumps(decision))
            unsafe_uphold["adjudication_id"] = "unsafe-uphold"
            unsafe_uphold["impact"]["scores"]["changed"] = True
            dump(root / "drafts/unsafe-uphold.json", unsafe_uphold)
            with self.assertRaisesRegex(ValueError, "uphold must retain"):
                record(
                    root / "drafts/unsafe-uphold.json",
                    root / "adjudications/unsafe-uphold.json",
                    root,
                )

            unsafe_no_action = json.loads(json.dumps(decision))
            unsafe_no_action["adjudication_id"] = "unsafe-no-action"
            unsafe_no_action["decision"]["outcome"] = "no_action"
            unsafe_no_action["impact"]["scores"]["changed"] = True
            dump(root / "drafts/unsafe-no-action.json", unsafe_no_action)
            with self.assertRaisesRegex(ValueError, "no_action must retain"):
                record(
                    root / "drafts/unsafe-no-action.json",
                    root / "adjudications/unsafe-no-action.json",
                    root,
                )

            unsafe_exclusion = json.loads(json.dumps(decision))
            unsafe_exclusion["adjudication_id"] = "unsafe-exclusion"
            unsafe_exclusion["decision"]["outcome"] = "exclude_response"
            dump(root / "drafts/unsafe-exclusion.json", unsafe_exclusion)
            with self.assertRaisesRegex(ValueError, "mark response validity invalid"):
                record(
                    root / "drafts/unsafe-exclusion.json",
                    root / "adjudications/unsafe-exclusion.json",
                    root,
                )

            decision["decision_status"] = "draft"
            dump(root / "drafts/not-final.json", decision)
            with self.assertRaisesRegex(ValueError, "decision_status='final'"):
                record(root / "drafts/not-final.json", root / "adjudications/not-final.json", root)

    def test_adjudication_supersession_is_linear_and_scope_preserving(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            evidence = root / "evidence/judgment.json"
            dump(evidence, {"temporary": "evidence"})
            first = make_review_adjudication(
                root, "temporary-response", evidence, "no_action"
            )
            first["adjudication_id"] = "decision-1"
            first_draft = root / "drafts/decision-1.json"
            first_output = root / "adjudications/decision-1.json"
            dump(first_draft, first)
            record(first_draft, first_output, root)

            correction = json.loads(json.dumps(first))
            correction.update(
                {
                    "adjudication_id": "decision-2",
                    "adjudication_version": 2,
                    "supersedes_adjudication_id": "decision-1",
                    "supersedes_adjudication_sha256": sha256_file(first_output),
                }
            )
            for field, changed_value in (
                ("campaign_id", "different-campaign"),
                ("batch_id", "different-batch"),
                ("classification", "rubric_level"),
            ):
                mismatched_field = json.loads(json.dumps(correction))
                mismatched_field["adjudication_id"] = f"mismatched-{field}"
                mismatched_field[field] = changed_value
                mismatch_field_draft = root / "drafts" / f"mismatched-{field}.json"
                dump(mismatch_field_draft, mismatched_field)
                with self.assertRaisesRegex(ValueError, f"changes {field}"):
                    record(
                        mismatch_field_draft,
                        root / "adjudications" / f"mismatched-{field}.json",
                        root,
                    )
            mismatched = json.loads(json.dumps(correction))
            mismatched["adjudication_id"] = "mismatched-decision"
            mismatched["affected_response_ids"] = ["different-response"]
            mismatch_draft = root / "drafts/mismatched.json"
            dump(mismatch_draft, mismatched)
            with self.assertRaisesRegex(ValueError, "changes affected_response_ids"):
                record(
                    mismatch_draft,
                    root / "adjudications/mismatched.json",
                    root,
                )

            correction_draft = root / "drafts/decision-2.json"
            correction_output = root / "adjudications/decision-2.json"
            dump(correction_draft, correction)
            record(correction_draft, correction_output, root)

            fork = json.loads(json.dumps(correction))
            fork["adjudication_id"] = "decision-2-fork"
            fork_draft = root / "drafts/decision-2-fork.json"
            dump(fork_draft, fork)
            with self.assertRaisesRegex(ValueError, "already has successor"):
                record(
                    fork_draft,
                    root / "adjudications/decision-2-fork.json",
                    root,
                )

    def test_handwritten_adjudications_fail_closed(self) -> None:
        manifest = {
            "campaign_id": "temporary-campaign",
            "batch_id": "temporary-batch",
            "responses": [
                {"anonymous_response_id": "temporary-response"},
                {"anonymous_response_id": "different-response"},
            ],
        }

        with self.subTest("terminal outcome cannot leave reevaluation pending"):
            with tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                evidence = root / "evidence/judgment.json"
                dump(evidence, {"temporary": "evidence"})
                draft = root / "drafts/no-action.json"
                output = root / "adjudications/no-action.json"
                decision = make_review_adjudication(
                    root, "temporary-response", evidence, "no_action"
                )
                dump(draft, decision)
                record(draft, output, root)
                handwritten = load_json_object(output)
                handwritten["reevaluation"].update(
                    {
                        "required": True,
                        "scope": "response_subset",
                        "reason": "Incorrectly pending.",
                    }
                )
                dump(output, handwritten)
                with self.assertRaisesRegex(ValueError, "no_action cannot leave"):
                    load_adjudication_directives(output.parent, manifest)

        with self.subTest("supersession cannot change governed responses"):
            with tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                evidence = root / "evidence/judgment.json"
                dump(evidence, {"temporary": "evidence"})
                draft = root / "drafts/decision-1.json"
                output = root / "adjudications/decision-1.json"
                first = make_review_adjudication(
                    root, "temporary-response", evidence, "no_action"
                )
                first["adjudication_id"] = "decision-1"
                dump(draft, first)
                record(draft, output, root)
                successor = load_json_object(output)
                successor.update(
                    {
                        "adjudication_id": "decision-2",
                        "adjudication_version": 2,
                        "supersedes_adjudication_id": "decision-1",
                        "supersedes_adjudication_sha256": sha256_file(output),
                        "affected_response_ids": ["different-response"],
                    }
                )
                dump(output.parent / "decision-2.json", successor)
                with self.assertRaisesRegex(ValueError, "changes affected_response_ids"):
                    load_adjudication_directives(output.parent, manifest)

        with self.subTest("supersession cannot fork"):
            with tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                evidence = root / "evidence/judgment.json"
                dump(evidence, {"temporary": "evidence"})
                draft = root / "drafts/decision-1.json"
                output = root / "adjudications/decision-1.json"
                first = make_review_adjudication(
                    root, "temporary-response", evidence, "no_action"
                )
                first["adjudication_id"] = "decision-1"
                dump(draft, first)
                record(draft, output, root)
                for identifier in ("decision-2a", "decision-2b"):
                    successor = load_json_object(output)
                    successor.update(
                        {
                            "adjudication_id": identifier,
                            "adjudication_version": 2,
                            "supersedes_adjudication_id": "decision-1",
                            "supersedes_adjudication_sha256": sha256_file(output),
                        }
                    )
                    dump(output.parent / f"{identifier}.json", successor)
                with self.assertRaisesRegex(ValueError, "lineage forks"):
                    load_adjudication_directives(output.parent, manifest)

        with self.subTest("replacement must be hash verified"):
            with tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                evidence = root / "evidence/judgment.json"
                replacement = root / "replacement.json"
                dump(evidence, {"temporary": "evidence"})
                dump(replacement, {"temporary": "unverified replacement"})
                draft = root / "drafts/no-action.json"
                output = root / "adjudications/no-action.json"
                decision = make_review_adjudication(
                    root, "temporary-response", evidence, "no_action"
                )
                dump(draft, decision)
                record(draft, output, root)
                handwritten = load_json_object(output)
                handwritten["decision"]["outcome"] = "replace_judgment"
                handwritten["impact"]["scores"]["changed"] = True
                handwritten["impact"]["scores"]["requires_recomputation"] = True
                handwritten["reevaluation"] = {
                    "required": True,
                    "scope": "response_subset",
                    "reason": "Replace the disputed judgment.",
                    "replacement_artifact_paths": ["../replacement.json"],
                }
                dump(output, handwritten)
                with self.assertRaisesRegex(ValueError, "not a hash-verified source_artifact"):
                    load_adjudication_directives(output.parent, manifest)

    def test_only_uphold_resolves_a_valid_judgment_review_flag(self) -> None:
        cases = (
            ("uphold", "valid", True),
            ("no_action", "valid", False),
            ("uphold", "uncertain", False),
        )
        for outcome, run_validity, expected_ready in cases:
            with self.subTest(outcome=outcome, run_validity=run_validity):
                with tempfile.TemporaryDirectory() as temporary:
                    workspace = TemporaryPipeline(Path(temporary))
                    workspace.prepare()
                    workspace.write_judgments()
                    entry = load_json_object(workspace.identity_map)["entries"][0]
                    response_id = entry["anonymous_response_id"]
                    judgment_path = workspace.blind_dir / entry["planned_judgment_path"]
                    judgment = load_json_object(judgment_path)
                    original_score = judgment["technical_score"]["final_score"]
                    judgment["result_status"] = "requires_human_review"
                    judgment["requires_human_review"] = True
                    judgment["human_review_reason"] = "Temporary review request."
                    judgment["run_validity"] = run_validity
                    dump(judgment_path, judgment)

                    draft_path = workspace.root / "drafts" / f"{outcome}.json"
                    dump(
                        draft_path,
                        make_review_adjudication(
                            workspace.root, response_id, judgment_path, outcome
                        ),
                    )
                    adjudications_dir = workspace.root / "adjudications"
                    record(
                        draft_path,
                        adjudications_dir / f"{outcome}.json",
                        workspace.root,
                    )

                    validated = validate_batch(
                        workspace.manifest,
                        identity_map_path=workspace.identity_map,
                        adjudications_dir=adjudications_dir,
                    )
                    self.assertEqual(validated["ready_for_unblinding"], expected_ready)
                    if expected_ready:
                        self.assertNotIn(response_id, validated["unresolved_response_ids"])
                        record_for_response = next(
                            row
                            for row in validated["judgments"]
                            if row["anonymous_response_id"] == response_id
                        )
                        self.assertEqual(
                            record_for_response["payload"]["technical_score"]["final_score"],
                            original_score,
                        )
                        self.assertEqual(
                            record_for_response["authority"]["kind"], "adjudication"
                        )
                    else:
                        self.assertIn(response_id, validated["unresolved_response_ids"])

    def test_adjudication_can_select_replacement_and_formal_exclusion(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = TemporaryPipeline(Path(temporary))
            workspace.prepare()
            workspace.write_judgments()
            identity = load_json_object(workspace.identity_map)
            replace_entry = identity["entries"][0]
            exclude_entry = identity["entries"][1]

            original_path = workspace.blind_dir / replace_entry["planned_judgment_path"]
            original = load_json_object(original_path)
            original["result_status"] = "requires_human_review"
            original["requires_human_review"] = True
            original["human_review_reason"] = "Temporary disputed judgment."
            dump(original_path, original)
            self.assertFalse(validate_batch(workspace.manifest)["ready_for_unblinding"])

            replacement_path = workspace.root / "replacements/replacement.json"
            dump(
                replacement_path,
                make_judgment(replace_entry["anonymous_response_id"], replace_entry["item_id"], 70.0),
            )
            adjudications_dir = workspace.root / "adjudications"
            replace_draft = workspace.root / "drafts/replace.json"
            replace_artifact = {
                "artifact_type": "judgment",
                "artifact_id": replace_entry["anonymous_response_id"],
                "path": original_path.relative_to(workspace.root).as_posix(),
                "sha256": sha256_file(original_path),
            }
            replacement_artifact = {
                "artifact_type": "replacement_judgment",
                "artifact_id": replace_entry["anonymous_response_id"],
                "path": replacement_path.relative_to(workspace.root).as_posix(),
                "sha256": sha256_file(replacement_path),
            }
            replacement_decision = {
                "schema_version": "1.0",
                "adjudication_id": "temporary-replacement",
                "adjudication_version": 1,
                "decision_status": "final",
                "supersedes_adjudication_id": None,
                "supersedes_adjudication_sha256": None,
                "campaign_id": "temporary-campaign",
                "batch_id": "temporary-batch",
                "recorded_at": "2026-01-01T00:00:00Z",
                "reviewer": {
                    "reviewer_id": "temporary-reviewer",
                    "role": "human-reviewer",
                    "human_confirmed": True,
                },
                "trigger": {
                    "type": "judge_error",
                    "summary": "Temporary replacement trigger.",
                    "evidence": "The original judgment was disputed.",
                },
                "source_artifacts": [replace_artifact, replacement_artifact],
                "classification": "response_only",
                "decision": {
                    "outcome": "replace_judgment",
                    "summary": "Use the new blind judgment.",
                    "technical_rationale": "The replacement corrects the temporary judge error.",
                },
                "impact": {
                    "reference": {"changed": False, "previous_version": None, "replacement_version": None},
                    "rubric": {"changed": False, "previous_version": None, "replacement_version": None},
                    "response_validity": {"changed": False, "new_status": None},
                    "scores": {"changed": True, "requires_recomputation": True},
                },
                "affected_response_ids": [replace_entry["anonymous_response_id"]],
                "reevaluation": {
                    "required": True,
                    "scope": "response_subset",
                    "reason": "Replace the disputed judgment.",
                    "replacement_artifact_paths": [
                        replacement_path.relative_to(workspace.root).as_posix()
                    ],
                },
                "superseded_artifacts": [replace_artifact],
                "notes": "",
            }
            dump(replace_draft, replacement_decision)
            record(
                replace_draft,
                adjudications_dir / "temporary-replacement.json",
                workspace.root,
            )

            excluded_path = workspace.blind_dir / exclude_entry["planned_judgment_path"]
            exclusion_draft = workspace.root / "drafts/exclude.json"
            excluded_artifact = {
                "artifact_type": "judgment",
                "artifact_id": exclude_entry["anonymous_response_id"],
                "path": excluded_path.relative_to(workspace.root).as_posix(),
                "sha256": sha256_file(excluded_path),
            }
            exclusion_decision = json.loads(json.dumps(replacement_decision))
            exclusion_decision.update(
                {
                    "adjudication_id": "temporary-exclusion",
                    "trigger": {
                        "type": "operational_invalidity",
                        "summary": "Temporary exclusion trigger.",
                        "evidence": "The response was declared ineligible.",
                    },
                    "source_artifacts": [excluded_artifact],
                    "decision": {
                        "outcome": "exclude_response",
                        "summary": "Exclude this response.",
                        "technical_rationale": "The temporary response is operationally invalid.",
                    },
                    "affected_response_ids": [exclude_entry["anonymous_response_id"]],
                    "reevaluation": {
                        "required": False,
                        "scope": "none",
                        "reason": "",
                        "replacement_artifact_paths": [],
                    },
                    "superseded_artifacts": [],
                    "impact": {
                        "reference": {
                            "changed": False,
                            "previous_version": None,
                            "replacement_version": None,
                        },
                        "rubric": {
                            "changed": False,
                            "previous_version": None,
                            "replacement_version": None,
                        },
                        "response_validity": {
                            "changed": True,
                            "new_status": "invalid",
                        },
                        "scores": {
                            "changed": False,
                            "requires_recomputation": False,
                        },
                    },
                }
            )
            dump(exclusion_draft, exclusion_decision)
            record(
                exclusion_draft,
                adjudications_dir / "temporary-exclusion.json",
                workspace.root,
            )

            validated = validate_batch(
                workspace.manifest,
                identity_map_path=workspace.identity_map,
                adjudications_dir=adjudications_dir,
            )
            self.assertTrue(validated["ready_for_unblinding"])
            self.assertEqual(len(validated["exclusions"]), 1)
            output_path = workspace.root / "private/adjudicated-unblinded.json"
            output = unblind(
                workspace.manifest,
                workspace.identity_map,
                output_path,
                adjudications_dir=adjudications_dir,
            )
            self.assertEqual(output["record_count"], 3)
            self.assertEqual(output["excluded_count"], 1)
            replacement_record = next(
                row
                for row in output["records"]
                if row["anonymous_response_id"] == replace_entry["anonymous_response_id"]
            )
            self.assertEqual(replacement_record["final_score"], 70.0)
            self.assertEqual(replacement_record["authority"]["kind"], "adjudication")


if __name__ == "__main__":
    unittest.main()
