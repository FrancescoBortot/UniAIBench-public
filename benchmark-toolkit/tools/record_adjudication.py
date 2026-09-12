#!/usr/bin/env python3
"""Validate and immutably record a human adjudication decision offline."""

from __future__ import annotations

import argparse
import copy
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from schema_validation import validate_json_schema
from validate_blind_batch import load_json_object, require_hash


TOOLKIT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = TOOLKIT_ROOT / "schemas" / "adjudication.schema.json"


def fail(message: str) -> None:
    raise ValueError(message)


def require_iso_datetime(value: Any, label: str) -> None:
    if not isinstance(value, str):
        fail(f"{label} must be an ISO-8601 datetime")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        fail(f"{label} must be an ISO-8601 datetime")
    if parsed.tzinfo is None:
        fail(f"{label} must include a timezone")


def resolve_artifact(root: Path, declared: str, label: str) -> Path:
    candidate = Path(declared)
    if candidate.is_absolute():
        fail(f"{label} must be relative to --artifact-root")
    resolved_root = root.resolve()
    resolved = (root / candidate).resolve()
    try:
        resolved.relative_to(resolved_root)
    except ValueError:
        fail(f"{label} escapes --artifact-root: {declared}")
    return resolved


def relative_path(target: Path, base: Path) -> str:
    return Path(os.path.relpath(target.resolve(), base.resolve())).as_posix()


def prior_records(directory: Path, excluded: set[Path]) -> dict[str, tuple[Path, dict[str, Any]]]:
    records: dict[str, tuple[Path, dict[str, Any]]] = {}
    if not directory.is_dir():
        return records
    for path in directory.glob("*.json"):
        resolved = path.resolve()
        if resolved in excluded:
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict) or not isinstance(payload.get("adjudication_id"), str):
            continue
        identifier = payload["adjudication_id"]
        if identifier in records:
            fail(f"duplicate existing adjudication_id {identifier} in {directory}")
        records[identifier] = (resolved, payload)
    return records


def impact_is_unchanged(impact: dict[str, Any]) -> bool:
    """Return whether a decision leaves every governed artifact unchanged."""

    return not (
        impact["reference"]["changed"]
        or impact["rubric"]["changed"]
        or impact["response_validity"]["changed"]
        or impact["response_validity"]["new_status"] is not None
        or impact["scores"]["changed"]
        or impact["scores"]["requires_recomputation"]
    )


def validate_outcome_semantics(payload: dict[str, Any]) -> None:
    """Enforce fail-closed relationships that are awkward to express in JSON Schema."""

    reevaluation = payload["reevaluation"]
    replacements = reevaluation["replacement_artifact_paths"]
    outcome = payload["decision"]["outcome"]
    impact = payload["impact"]

    if reevaluation["required"]:
        if reevaluation["scope"] == "none" or not str(reevaluation["reason"]).strip():
            fail("required reevaluation needs a non-'none' scope and a reason")
    else:
        if reevaluation["scope"] != "none":
            fail("reevaluation scope must be 'none' when reevaluation is not required")
        if replacements:
            fail("replacement artifacts require reevaluation.required=true")

    if outcome != "replace_judgment" and replacements:
        fail("only replace_judgment may declare replacement judgment artifacts")

    if outcome in {"uphold", "no_action", "exclude_response"} and reevaluation["required"]:
        fail(f"{outcome} cannot leave reevaluation pending")

    if outcome in {"uphold", "no_action"} and not impact_is_unchanged(impact):
        fail(
            f"{outcome} must retain the original reference, rubric, response "
            "validity, and score"
        )

    if outcome == "exclude_response":
        if (
            impact["reference"]["changed"]
            or impact["rubric"]["changed"]
            or not impact["response_validity"]["changed"]
            or impact["response_validity"]["new_status"] != "invalid"
            or impact["scores"]["changed"]
            or impact["scores"]["requires_recomputation"]
        ):
            fail(
                "exclude_response must mark response validity invalid without "
                "changing the reference, rubric, or score"
            )

    if outcome == "replace_judgment":
        if not reevaluation["required"] or not replacements:
            fail("replace_judgment requires reevaluation and replacement artifacts")
        if reevaluation["scope"] != "response_subset":
            fail("replace_judgment reevaluation scope must be 'response_subset'")
        if (
            impact["reference"]["changed"]
            or impact["rubric"]["changed"]
            or impact["response_validity"]["changed"]
            or impact["response_validity"]["new_status"] is not None
            or not impact["scores"]["requires_recomputation"]
        ):
            fail(
                "replace_judgment must retain reference, rubric, and response "
                "validity while requiring score recomputation"
            )


def validate_supersession_lineage(
    identifier: str,
    payload: dict[str, Any],
    previous_id: str,
    previous_payload: dict[str, Any],
) -> None:
    """Ensure a correction stays on the exact decision lineage it replaces."""

    for field in ("campaign_id", "batch_id", "classification"):
        if payload[field] != previous_payload[field]:
            fail(
                f"adjudication {identifier} changes {field} from superseded "
                f"decision {previous_id}"
            )
    affected = {str(value) for value in payload["affected_response_ids"]}
    previous_affected = {
        str(value) for value in previous_payload["affected_response_ids"]
    }
    if affected != previous_affected:
        fail(
            f"adjudication {identifier} changes affected_response_ids from "
            f"superseded decision {previous_id}"
        )


def record(draft_path: Path, output_path: Path, artifact_root: Path | None = None) -> None:
    draft_path = draft_path.resolve()
    output_path = output_path.resolve()
    if output_path.exists():
        fail(f"refusing to overwrite existing adjudication: {output_path}")
    if draft_path == output_path:
        fail("draft and immutable output paths must be different")

    payload = load_json_object(draft_path)
    schema = load_json_object(SCHEMA_PATH)
    validate_json_schema(payload, schema)
    if payload["decision_status"] != "final":
        fail("only decision_status='final' may be recorded as an immutable adjudication")
    if payload["reviewer"]["human_confirmed"] is not True:
        fail("a final adjudication requires reviewer.human_confirmed=true")
    require_iso_datetime(payload["recorded_at"], "recorded_at")
    root = (artifact_root or draft_path.parent).resolve()
    if not root.is_dir():
        fail(f"artifact root is not a directory: {root}")

    normalized = copy.deepcopy(payload)
    for collection_name in ("source_artifacts", "superseded_artifacts"):
        for index, artifact in enumerate(normalized.get(collection_name, [])):
            path = resolve_artifact(
                root, str(artifact["path"]), f"{collection_name}[{index}].path"
            )
            require_hash(path, str(artifact["sha256"]), f"{collection_name}[{index}]")
            artifact["path"] = relative_path(path, output_path.parent)
    normalized_replacements: list[str] = []
    for index, declared in enumerate(normalized["reevaluation"]["replacement_artifact_paths"]):
        path = resolve_artifact(root, str(declared), f"replacement_artifact_paths[{index}]")
        normalized_replacements.append(relative_path(path, output_path.parent))
    normalized["reevaluation"]["replacement_artifact_paths"] = normalized_replacements
    validate_json_schema(normalized, schema)
    validate_outcome_semantics(normalized)
    if normalized["decision"]["outcome"] == "replace_judgment":
        verified_sources = {
            str(artifact["path"]) for artifact in normalized["source_artifacts"]
        }
        if not normalized_replacements or not set(normalized_replacements) <= verified_sources:
            fail("every replacement judgment must be a hash-verified source_artifact")

    affected = [str(value) for value in payload.get("affected_response_ids", [])]
    if len(affected) != len(set(affected)):
        fail("affected_response_ids must be unique")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    existing = prior_records(output_path.parent, {draft_path, output_path})
    identifier = str(payload["adjudication_id"])
    if identifier in existing:
        fail(f"adjudication_id already recorded at {existing[identifier][0]}")
    supersedes = payload.get("supersedes_adjudication_id")
    supersedes_hash = payload.get("supersedes_adjudication_sha256")
    if bool(supersedes) != bool(supersedes_hash):
        fail("supersedes_adjudication_id and supersedes_adjudication_sha256 must be set together")
    if supersedes:
        if supersedes == identifier:
            fail("an adjudication cannot supersede itself")
        if supersedes not in existing:
            fail(f"superseded adjudication_id is not present in output directory: {supersedes}")
        previous_path, previous_payload = existing[supersedes]
        require_hash(previous_path, str(supersedes_hash), "superseded adjudication")
        expected_version = int(previous_payload.get("adjudication_version", 0)) + 1
        if int(payload["adjudication_version"]) != expected_version:
            fail(f"superseding adjudication_version must be {expected_version}")
        validate_supersession_lineage(identifier, payload, str(supersedes), previous_payload)
    elif int(payload["adjudication_version"]) != 1:
        fail("an adjudication without a supersession link must have adjudication_version=1")

    successors: dict[str, str] = {}
    for existing_id, (_, existing_payload) in existing.items():
        previous_id = existing_payload.get("supersedes_adjudication_id")
        if not previous_id:
            continue
        previous_id = str(previous_id)
        if previous_id in successors:
            fail(
                f"existing adjudication lineage forks at {previous_id}: "
                f"{successors[previous_id]} and {existing_id}"
            )
        successors[previous_id] = existing_id
    if supersedes and str(supersedes) in successors:
        fail(
            f"adjudication {supersedes} already has successor "
            f"{successors[str(supersedes)]}; refusing a fork"
        )

    descriptor = os.open(output_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(normalized, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
    except Exception:
        try:
            output_path.unlink()
        except FileNotFoundError:
            pass
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--draft", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--artifact-root", type=Path)
    args = parser.parse_args()
    record(args.draft, args.output, args.artifact_root)
    print(f"OK: immutable adjudication recorded at {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
