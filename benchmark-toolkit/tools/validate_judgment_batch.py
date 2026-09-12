#!/usr/bin/env python3
"""Validate all planned judgments in a blind batch and report unblinding readiness."""

from __future__ import annotations

import argparse
import math
from pathlib import Path
from typing import Any

from record_adjudication import (
    validate_outcome_semantics,
    validate_supersession_lineage,
)
from schema_validation import validate_json_schema
from validate_blind_batch import (
    load_json_object,
    require_hash,
    resolve_confined,
    resolve_declared,
    sha256_file,
    validate_identity_map,
    validate_manifest,
)
from validate_judgment import validate as validate_judgment
from validate_rubric import validate as validate_rubric


TOOLKIT_ROOT = Path(__file__).resolve().parents[1]
ADJUDICATION_SCHEMA = TOOLKIT_ROOT / "schemas" / "adjudication.schema.json"
CURRENT_JUDGMENT_SCHEMA = TOOLKIT_ROOT / "schemas" / "judgment.schema.json"
CURRENT_JUDGMENT_VALIDATOR = TOOLKIT_ROOT / "tools" / "validate_judgment.py"
CURRENT_VALIDATOR_SUPPORT = TOOLKIT_ROOT / "tools" / "schema_validation.py"


def fail(message: str) -> None:
    raise ValueError(message)


def require_matching_frozen_validator(manifest: dict[str, Any]) -> None:
    """Ensure in-process validation is byte-identical to the frozen contract."""

    contract = manifest["judging_contract"]
    for current_path, hash_field, label in (
        (CURRENT_JUDGMENT_SCHEMA, "judgment_schema_sha256", "judgment schema"),
        (CURRENT_JUDGMENT_VALIDATOR, "validator_sha256", "judgment validator"),
        (
            CURRENT_VALIDATOR_SUPPORT,
            "validator_support_sha256",
            "judgment-validator support module",
        ),
    ):
        current_hash = sha256_file(current_path)
        if current_hash != contract[hash_field]:
            fail(
                f"active {label} does not match the frozen judging contract; "
                "use the toolkit revision that prepared this blind batch"
            )


def validate_against_rubric(
    judgment: dict[str, Any], rubric: dict[str, Any], response_id: str
) -> None:
    if judgment["item_id"] != rubric["item_id"]:
        fail(f"judgment {response_id} item_id does not match its rubric")
    if judgment["rubric_version"] != rubric["rubric_version"]:
        fail(f"judgment {response_id} rubric_version does not match its rubric")

    expected = {item["criterion_id"]: item for item in rubric["atomic_criteria"]}
    observed = {item["criterion_id"]: item for item in judgment["criterion_assessment"]}
    if set(expected) != set(observed):
        missing = sorted(set(expected) - set(observed))
        extra = sorted(set(observed) - set(expected))
        fail(f"judgment {response_id} criterion coverage mismatch; missing={missing}, extra={extra}")
    for criterion_id, specification in expected.items():
        assessment = observed[criterion_id]
        if assessment["primary_dimension"] != specification["primary_dimension"]:
            fail(f"judgment {response_id} changes the dimension of {criterion_id}")
        if not math.isclose(
            float(assessment["max_points"]), float(specification["max_points"]), abs_tol=1e-8
        ):
            fail(f"judgment {response_id} changes max_points for {criterion_id}")

    applicability = rubric["dimension_applicability"]
    for dimension, status in applicability.items():
        expected_status = "scored" if status == "applicable" else "not_applicable"
        if judgment["dimensions"][dimension]["status"] != expected_status:
            fail(f"judgment {response_id} has wrong applicability for {dimension}")


def load_adjudication_directives(
    directory: Path | None,
    manifest: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], set[Path]]:
    if directory is None:
        return {}, set()
    directory = directory.resolve()
    if not directory.is_dir():
        fail(f"adjudications directory is not a directory: {directory}")
    schema = load_json_object(ADJUDICATION_SCHEMA)
    records: dict[str, tuple[Path, dict[str, Any]]] = {}
    verified_source_artifacts: dict[str, set[Path]] = {}
    resolved_replacements: dict[str, list[Path]] = {}
    for path in sorted(directory.rglob("*.json")):
        payload = load_json_object(path)
        validate_json_schema(payload, schema)
        if payload["decision_status"] != "final" or payload["reviewer"]["human_confirmed"] is not True:
            fail(f"adjudication is not final and human-confirmed: {path}")
        if payload["campaign_id"] != manifest["campaign_id"] or payload["batch_id"] != manifest["batch_id"]:
            fail(f"adjudication belongs to a different campaign or batch: {path}")
        identifier = str(payload["adjudication_id"])
        if identifier in records:
            fail(f"duplicate adjudication_id: {identifier}")
        validate_outcome_semantics(payload)
        verified_sources: set[Path] = set()
        for collection in ("source_artifacts", "superseded_artifacts"):
            for index, artifact in enumerate(payload[collection]):
                artifact_path = resolve_declared(path.parent, str(artifact["path"]))
                require_hash(
                    artifact_path,
                    str(artifact["sha256"]),
                    f"{collection}[{index}] in adjudication {identifier}",
                )
                if collection == "source_artifacts":
                    verified_sources.add(artifact_path)
        replacements = [
            resolve_declared(path.parent, str(value))
            for value in payload["reevaluation"]["replacement_artifact_paths"]
        ]
        if payload["decision"]["outcome"] == "replace_judgment":
            unverified = set(replacements) - verified_sources
            if unverified:
                fail(
                    f"replacement judgment {sorted(str(value) for value in unverified)[0]} "
                    f"is not a hash-verified source_artifact of adjudication {identifier}"
                )
        records[identifier] = (path.resolve(), payload)
        verified_source_artifacts[identifier] = verified_sources
        resolved_replacements[identifier] = replacements

    superseded_ids: set[str] = set()
    successor_by_previous: dict[str, str] = {}
    for identifier, (path, payload) in records.items():
        previous_id = payload.get("supersedes_adjudication_id")
        previous_hash = payload.get("supersedes_adjudication_sha256")
        if bool(previous_id) != bool(previous_hash):
            fail(f"adjudication {identifier} has an incomplete supersession link")
        if previous_id:
            if previous_id not in records:
                fail(f"adjudication {identifier} supersedes an unknown decision: {previous_id}")
            previous_path, previous_payload = records[previous_id]
            require_hash(previous_path, str(previous_hash), f"superseded adjudication {previous_id}")
            if int(payload["adjudication_version"]) != int(previous_payload["adjudication_version"]) + 1:
                fail(f"adjudication {identifier} has a non-consecutive version")
            previous_id = str(previous_id)
            validate_supersession_lineage(identifier, payload, previous_id, previous_payload)
            if previous_id in successor_by_previous:
                fail(
                    f"adjudication lineage forks at {previous_id}: "
                    f"{successor_by_previous[previous_id]} and {identifier}"
                )
            successor_by_previous[previous_id] = identifier
            superseded_ids.add(previous_id)
        elif int(payload["adjudication_version"]) != 1:
            fail(f"initial adjudication {identifier} must have version 1")

    known_response_ids = {
        str(response["anonymous_response_id"]) for response in manifest["responses"]
    }
    directives: dict[str, dict[str, Any]] = {}
    replacement_paths: set[Path] = set()
    for identifier, (path, payload) in records.items():
        if identifier in superseded_ids:
            continue
        affected = {str(value) for value in payload["affected_response_ids"]}
        unknown = affected - known_response_ids
        if unknown:
            fail(f"adjudication {identifier} names unknown responses: {sorted(unknown)}")
        overlap = affected & directives.keys()
        if overlap:
            fail(f"multiple active adjudications govern responses: {sorted(overlap)}")
        outcome = str(payload["decision"]["outcome"])
        if payload["classification"] != "response_only":
            fail(
                f"adjudication {identifier} has classification {payload['classification']!r}; "
                "prepare a new blind batch for rubric, reference, or campaign-level changes"
            )
        replacements = resolved_replacements[identifier]
        if outcome == "replace_judgment":
            replacement_by_response: dict[str, Path] = {}
            for replacement_path in replacements:
                replacement = load_json_object(replacement_path)
                response_id = str(replacement.get("response_id", ""))
                if response_id in replacement_by_response:
                    fail(f"adjudication {identifier} has duplicate replacements for {response_id}")
                replacement_by_response[response_id] = replacement_path
                replacement_paths.add(replacement_path)
            if set(replacement_by_response) != affected:
                fail(
                    f"adjudication {identifier} replacement coverage differs from affected responses"
                )
            for response_id in affected:
                directives[response_id] = {
                    "kind": "replace",
                    "path": replacement_by_response[response_id],
                    "adjudication_id": identifier,
                    "adjudication_path": path,
                    "adjudication_sha256": sha256_file(path),
                }
        elif outcome == "uphold":
            for response_id in affected:
                directives[response_id] = {
                    "kind": "uphold",
                    "adjudication_id": identifier,
                    "adjudication_path": path,
                    "adjudication_sha256": sha256_file(path),
                    "verified_source_artifact_paths": verified_source_artifacts[identifier],
                }
        elif outcome == "no_action":
            for response_id in affected:
                directives[response_id] = {
                    "kind": "no_action",
                    "adjudication_id": identifier,
                    "adjudication_path": path,
                    "adjudication_sha256": sha256_file(path),
                }
        elif outcome == "exclude_response":
            for response_id in affected:
                directives[response_id] = {
                    "kind": "exclude",
                    "adjudication_id": identifier,
                    "adjudication_path": path,
                    "adjudication_sha256": sha256_file(path),
                    "reason": payload["decision"]["summary"],
                }
        else:
            fail(
                f"active adjudication outcome {outcome!r} requires a new batch or campaign and "
                "cannot be applied automatically"
            )
    return directives, replacement_paths


def validate_batch(
    manifest_path: Path,
    *,
    identity_map_path: Path | None = None,
    adjudications_dir: Path | None = None,
    require_complete: bool = True,
) -> dict[str, Any]:
    manifest_path = manifest_path.resolve()
    manifest = validate_manifest(manifest_path)
    require_matching_frozen_validator(manifest)
    if identity_map_path is not None:
        validate_identity_map(manifest_path, manifest, identity_map_path)

    base = manifest_path.parent
    rubrics: dict[str, dict[str, Any]] = {}
    for artifact in manifest["item_artifacts"]:
        item_id = str(artifact["item_id"])
        rubric_path = resolve_confined(base, str(artifact["rubric_path"]), f"rubric for {item_id}")
        rubric = load_json_object(rubric_path)
        validate_rubric(rubric)
        if rubric["item_id"] != item_id:
            fail(f"item artifact {item_id} contains a rubric for {rubric['item_id']}")
        if rubric["frozen"] is not True:
            fail(f"rubric for {item_id} is not frozen")
        if rubric["judge_spec_version"] != manifest["judging_contract"]["judge_spec_version"]:
            fail(f"rubric for {item_id} does not match the frozen judge specification")
        rubrics[item_id] = rubric

    directives, replacement_paths = load_adjudication_directives(adjudications_dir, manifest)
    missing: list[str] = []
    judgments: list[dict[str, Any]] = []
    expected_paths: set[Path] = set()
    unresolved: list[str] = []
    exclusions: list[dict[str, str]] = []
    for response in manifest["responses"]:
        response_id = str(response["anonymous_response_id"])
        planned_path = resolve_confined(
            base,
            str(response["planned_judgment_path"]),
            f"planned judgment for {response_id}",
        )
        expected_paths.add(planned_path)
        directive = directives.get(response_id)
        if directive and directive["kind"] == "exclude":
            exclusions.append(
                {
                    "anonymous_response_id": response_id,
                    "item_id": str(response["item_id"]),
                    "adjudication_id": str(directive["adjudication_id"]),
                    "adjudication_path": str(directive["adjudication_path"]),
                    "adjudication_sha256": str(directive["adjudication_sha256"]),
                    "reason": str(directive["reason"]),
                }
            )
            continue
        judgment_path = (
            Path(directive["path"]).resolve()
            if directive and directive["kind"] == "replace"
            else planned_path
        )
        if not judgment_path.is_file():
            missing.append(response_id)
            continue
        judgment = load_json_object(judgment_path)
        validate_judgment(judgment)
        if judgment["response_id"] != response_id:
            fail(f"judgment path for {response_id} contains response_id {judgment['response_id']}")
        if judgment["item_id"] != response["item_id"]:
            fail(f"judgment {response_id} contains the wrong item_id")
        validate_against_rubric(judgment, rubrics[str(response["item_id"])], response_id)
        if (
            directive
            and directive["kind"] == "uphold"
            and judgment_path not in directive["verified_source_artifact_paths"]
        ):
            fail(
                f"uphold adjudication {directive['adjudication_id']} does not cite the "
                f"original judgment for {response_id} as a hash-verified source artifact"
            )
        is_unresolved = (
            judgment["requires_human_review"]
            or judgment["result_status"] != "complete"
            or judgment["run_validity"] != "valid"
        )
        if directive and directive["kind"] == "uphold":
            # A final human-confirmed uphold is the explicit disposition of a
            # review flag. It keeps the original judgment and score unchanged,
            # but cannot repair an operationally invalid/uncertain run or an
            # otherwise incomplete judgment.
            is_unresolved = (
                judgment["result_status"] not in {"complete", "requires_human_review"}
                or judgment["run_validity"] != "valid"
            )
        if is_unresolved:
            unresolved.append(response_id)
        judgments.append(
            {
                "anonymous_response_id": response_id,
                "path": judgment_path,
                "sha256": sha256_file(judgment_path),
                "payload": judgment,
                "authority": (
                    {
                        "kind": "adjudication",
                        "adjudication_id": directive["adjudication_id"],
                        "adjudication_path": str(directive["adjudication_path"]),
                        "adjudication_sha256": directive["adjudication_sha256"],
                    }
                    if directive
                    else {"kind": "planned_judgment"}
                ),
            }
        )

    judgments_root = base / "judgments"
    if judgments_root.is_dir():
        actual_paths = {path.resolve() for path in judgments_root.rglob("*.json") if path.is_file()}
        allowed_paths = expected_paths | replacement_paths
        extra_paths = sorted(str(path.relative_to(base)) for path in actual_paths - allowed_paths)
        if extra_paths:
            fail(f"unplanned judgment files are present: {extra_paths}")

    if missing and require_complete:
        fail(f"missing judgments for anonymous responses: {sorted(missing)}")
    return {
        "manifest": manifest,
        "judgments": judgments,
        "exclusions": exclusions,
        "missing_response_ids": sorted(missing),
        "unresolved_response_ids": sorted(unresolved),
        "complete": not missing,
        "ready_for_unblinding": not missing and not unresolved,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--identity-map", type=Path)
    parser.add_argument(
        "--adjudications-dir",
        type=Path,
        help="directory of immutable final adjudications governing replacements or exclusions",
    )
    parser.add_argument(
        "--allow-incomplete",
        action="store_true",
        help="report missing judgments without treating them as a validation failure",
    )
    args = parser.parse_args()
    result = validate_batch(
        args.manifest,
        identity_map_path=args.identity_map,
        adjudications_dir=args.adjudications_dir,
        require_complete=not args.allow_incomplete,
    )
    if result["missing_response_ids"]:
        print(
            "PENDING: structurally valid batch with missing responses: "
            + ", ".join(result["missing_response_ids"])
        )
    elif result["unresolved_response_ids"]:
        print(
            "VALID BUT NOT READY FOR UNBLINDING: unresolved human review or validity: "
            + ", ".join(result["unresolved_response_ids"])
        )
    else:
        print(
            f"OK: {len(result['judgments'])} judgments and {len(result['exclusions'])} "
            "formal exclusions are ready for unblinding"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
