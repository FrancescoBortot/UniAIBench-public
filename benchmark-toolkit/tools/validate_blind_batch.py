#!/usr/bin/env python3
"""Validate a blind-batch manifest and, optionally, its private identity map."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from schema_validation import validate_json_schema


TOOLKIT_ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = TOOLKIT_ROOT / "schemas"


def fail(message: str) -> None:
    raise ValueError(message)


def load_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        fail(f"file not found: {path}")
    except json.JSONDecodeError as exc:
        fail(f"invalid JSON in {path}: {exc}")
    if not isinstance(payload, dict):
        fail(f"JSON root must be an object: {path}")
    return payload


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_schema(payload: dict[str, Any], schema_name: str) -> None:
    schema = load_json_object(SCHEMAS / schema_name)
    validate_json_schema(payload, schema)


def resolve_confined(base: Path, declared: str, label: str) -> Path:
    candidate = Path(declared)
    if candidate.is_absolute():
        fail(f"{label} must be relative: {declared}")
    resolved_base = base.resolve()
    resolved = (base / candidate).resolve()
    try:
        resolved.relative_to(resolved_base)
    except ValueError:
        fail(f"{label} escapes its declared base directory: {declared}")
    return resolved


def resolve_declared(base: Path, declared: str) -> Path:
    candidate = Path(declared)
    return candidate.resolve() if candidate.is_absolute() else (base / candidate).resolve()


def require_hash(path: Path, expected: str, label: str) -> None:
    if not path.is_file():
        fail(f"{label} is not a file: {path}")
    actual = sha256_file(path)
    if actual != expected:
        fail(f"SHA-256 mismatch for {label}: expected {expected}, found {actual}")


def require_unique(values: list[str], label: str) -> None:
    if len(values) != len(set(values)):
        fail(f"{label} must be unique")


def validate_manifest(
    manifest_path: Path,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    manifest_path = manifest_path.resolve()
    manifest = payload if payload is not None else load_json_object(manifest_path)
    validate_schema(manifest, "blind-batch-manifest.schema.json")
    base = manifest_path.parent

    contract = manifest["judging_contract"]
    reserved_paths: set[Path] = {manifest_path}
    for path_field, hash_field, label in (
        ("judge_prompt_path", "judge_prompt_sha256", "judge prompt"),
        ("judgment_schema_path", "judgment_schema_sha256", "judgment schema"),
        ("validator_path", "validator_sha256", "judgment validator"),
        (
            "validator_support_path",
            "validator_support_sha256",
            "judgment-validator support module",
        ),
    ):
        artifact = resolve_confined(base, str(contract[path_field]), label)
        require_hash(artifact, str(contract[hash_field]), label)
        reserved_paths.add(artifact)

    item_artifacts = manifest["item_artifacts"]
    responses = manifest["responses"]
    item_ids = [str(item["item_id"]) for item in item_artifacts]
    require_unique(item_ids, "item_artifacts.item_id")
    artifacts_by_item = {str(item["item_id"]): item for item in item_artifacts}

    for item in item_artifacts:
        item_id = str(item["item_id"])
        item_text = resolve_confined(base, str(item["item_path"]), f"item path for {item_id}")
        require_hash(item_text, str(item["item_sha256"]), f"item text for {item_id}")
        reserved_paths.add(item_text)
        rubric = resolve_confined(base, str(item["rubric_path"]), f"rubric path for {item_id}")
        require_hash(rubric, str(item["rubric_sha256"]), f"rubric for {item_id}")
        reserved_paths.add(rubric)
        has_reference_path = bool(item.get("reference_path"))
        has_reference_hash = bool(item.get("reference_sha256"))
        if has_reference_path != has_reference_hash:
            fail(f"reference path and hash must be declared together for {item_id}")
        if has_reference_path:
            reference = resolve_confined(
                base, str(item["reference_path"]), f"reference path for {item_id}"
            )
            require_hash(reference, str(item["reference_sha256"]), f"reference for {item_id}")
            reserved_paths.add(reference)

    anonymous_ids = [str(item["anonymous_response_id"]) for item in responses]
    blind_paths = [str(item["blind_input_path"]) for item in responses]
    judgment_paths = [str(item["planned_judgment_path"]) for item in responses]
    require_unique(anonymous_ids, "responses.anonymous_response_id")
    require_unique(blind_paths, "responses.blind_input_path")
    require_unique(judgment_paths, "responses.planned_judgment_path")

    blind_inputs: dict[str, Path] = {}
    for response in responses:
        response_id = str(response["anonymous_response_id"])
        blind_input = resolve_confined(
            base, str(response["blind_input_path"]), f"blind input for {response_id}"
        )
        blind_inputs[response_id] = blind_input
        reserved_paths.add(blind_input)

    judgments_root = (base / "judgments").resolve()
    resolved_judgment_paths: set[Path] = set()

    for response in responses:
        response_id = str(response["anonymous_response_id"])
        item_id = str(response["item_id"])
        if item_id not in artifacts_by_item:
            fail(f"response {response_id} refers to unknown item {item_id}")
        blind_input = blind_inputs[response_id]
        require_hash(blind_input, str(response["blind_input_sha256"]), f"blind input {response_id}")
        if response["response_sha256"] != response["blind_input_sha256"]:
            fail(f"source and blind-input hashes differ for {response_id}")
        planned_judgment = resolve_confined(
            base,
            str(response["planned_judgment_path"]),
            f"planned judgment for {response_id}",
        )
        try:
            relative_judgment = planned_judgment.relative_to(judgments_root)
        except ValueError:
            fail(
                f"planned judgment for {response_id} must be stored under "
                "the blind-batch judgments directory"
            )
        if relative_judgment == Path("."):
            fail(f"planned judgment for {response_id} must name a file")
        if planned_judgment in reserved_paths:
            fail(f"planned judgment for {response_id} collides with a frozen batch artifact")
        if planned_judgment in resolved_judgment_paths:
            fail("resolved responses.planned_judgment_path values must be unique")
        resolved_judgment_paths.add(planned_judgment)

    return manifest


def validate_identity_map(
    manifest_path: Path,
    manifest: dict[str, Any],
    identity_map_path: Path,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    manifest_path = manifest_path.resolve()
    identity_map_path = identity_map_path.resolve()
    identity = payload if payload is not None else load_json_object(identity_map_path)
    validate_schema(identity, "identity-map.schema.json")

    if identity["campaign_id"] != manifest["campaign_id"]:
        fail("identity map and blind manifest have different campaign_id values")
    if identity["batch_id"] != manifest["batch_id"]:
        fail("identity map and blind manifest have different batch_id values")
    try:
        identity_map_path.relative_to(manifest_path.parent)
    except ValueError:
        pass
    else:
        fail("private identity map must not be stored inside the blind-batch directory")

    source_manifest_path = resolve_declared(
        identity_map_path.parent, str(identity["source_manifest_path"])
    )
    require_hash(
        source_manifest_path,
        str(identity["source_manifest_sha256"]),
        "source manifest",
    )
    source_manifest = load_json_object(source_manifest_path)
    if source_manifest.get("campaign_id") != manifest["campaign_id"]:
        fail("source manifest and blind manifest have different campaign_id values")
    if source_manifest.get("batch_id") != manifest["batch_id"]:
        fail("source manifest and blind manifest have different batch_id values")
    source_responses = source_manifest.get("responses")
    if not isinstance(source_responses, list) or not source_responses:
        fail("source manifest responses must be a non-empty array")
    if any(not isinstance(item, dict) for item in source_responses):
        fail("every source-manifest response must be an object")
    source_by_id = {str(item.get("source_run_id")): item for item in source_responses}
    if len(source_by_id) != len(source_responses) or "None" in source_by_id:
        fail("source-manifest source_run_id values must be present and unique")
    declared_manifest = resolve_declared(
        identity_map_path.parent, str(identity["blind_batch_manifest_path"])
    )
    if declared_manifest != manifest_path:
        fail("identity map points to a different blind-batch manifest")
    require_hash(
        manifest_path,
        str(identity["blind_batch_manifest_sha256"]),
        "blind-batch manifest",
    )

    entries = identity["entries"]
    entry_ids = [str(entry["anonymous_response_id"]) for entry in entries]
    source_ids = [str(entry["source_run_id"]) for entry in entries]
    source_paths = [str(entry["source_response_path"]) for entry in entries]
    require_unique(entry_ids, "identity entries anonymous_response_id")
    require_unique(source_ids, "identity entries source_run_id")
    require_unique(source_paths, "identity entries source_response_path")

    responses = {
        str(response["anonymous_response_id"]): response
        for response in manifest["responses"]
    }
    if set(entry_ids) != set(responses):
        missing = sorted(set(responses) - set(entry_ids))
        extra = sorted(set(entry_ids) - set(responses))
        fail(f"identity-map bijection mismatch; missing={missing}, extra={extra}")
    if set(source_ids) != set(source_by_id):
        missing = sorted(set(source_by_id) - set(source_ids))
        extra = sorted(set(source_ids) - set(source_by_id))
        fail(f"source-manifest bijection mismatch; missing={missing}, extra={extra}")

    manifest_base = manifest_path.parent
    artifacts_by_item = {
        str(item["item_id"]): item for item in manifest["item_artifacts"]
    }
    for entry in entries:
        response_id = str(entry["anonymous_response_id"])
        response = responses[response_id]
        for field in (
            "item_id",
            "response_sha256",
            "blind_input_path",
            "blind_input_sha256",
            "planned_judgment_path",
        ):
            if entry[field] != response[field]:
                fail(f"identity entry {response_id} disagrees with manifest field {field}")
        source_record = source_by_id[str(entry["source_run_id"])]
        for identity_field, source_field in (
            ("item_id", "item_id"),
            ("system_id", "system_id"),
            ("repetition_id", "repetition_id"),
            ("model_identity", "model_identity"),
        ):
            source_value = source_record.get(source_field)
            expected_value = source_value if source_field == "model_identity" else str(source_value)
            if entry[identity_field] != expected_value:
                fail(
                    f"identity entry {response_id} disagrees with source manifest field "
                    f"{source_field}"
                )
        source = resolve_confined(
            source_manifest_path.parent,
            str(entry["source_response_path"]),
            f"source response for {response_id}",
        )
        declared_source = resolve_confined(
            source_manifest_path.parent,
            str(source_record.get("response_path", "")),
            f"source-manifest response for {response_id}",
        )
        if source != declared_source:
            fail(f"identity entry {response_id} points to a different source response")
        require_hash(source, str(entry["source_response_sha256"]), f"source response {response_id}")
        if entry["source_response_sha256"] != response["response_sha256"]:
            fail(f"source-response hash disagrees with manifest for {response_id}")
        blind = resolve_confined(
            manifest_base, str(entry["blind_input_path"]), f"blind input for {response_id}"
        )
        require_hash(blind, str(entry["blind_input_sha256"]), f"blind input {response_id}")

        artifact = artifacts_by_item[str(entry["item_id"])]
        for source_field, path_field, hash_field, label in (
            ("item_path", "item_path", "item_sha256", "item text"),
            ("rubric_path", "rubric_path", "rubric_sha256", "rubric"),
        ):
            source_artifact = resolve_confined(
                source_manifest_path.parent,
                str(source_record.get(source_field, "")),
                f"source {label} for {response_id}",
            )
            require_hash(
                source_artifact,
                str(artifact[hash_field]),
                f"source {label} for {response_id}",
            )
        source_reference = source_record.get("reference_path")
        if source_reference not in (None, ""):
            if not artifact.get("reference_path") or not artifact.get("reference_sha256"):
                fail(f"source reference is missing from blind item artifacts for {response_id}")
            reference = resolve_confined(
                source_manifest_path.parent,
                str(source_reference),
                f"source reference for {response_id}",
            )
            require_hash(
                reference,
                str(artifact["reference_sha256"]),
                f"source reference for {response_id}",
            )
        elif artifact.get("reference_path") or artifact.get("reference_sha256"):
            fail(f"blind item artifact has an undeclared source reference for {response_id}")

    return identity


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--identity-map", type=Path)
    args = parser.parse_args()

    manifest = validate_manifest(args.manifest)
    if args.identity_map is not None:
        validate_identity_map(args.manifest, manifest, args.identity_map)
    suffix = " with a complete private identity-map bijection" if args.identity_map else ""
    print(f"OK: blind batch {manifest['batch_id']} is valid{suffix}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
