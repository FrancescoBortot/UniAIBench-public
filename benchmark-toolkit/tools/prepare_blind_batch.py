#!/usr/bin/env python3
"""Prepare anonymous blind inputs and a separate private identity map offline."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from validate_blind_batch import sha256_file, validate_identity_map, validate_manifest
from validate_rubric import validate as validate_rubric


def fail(message: str) -> None:
    raise ValueError(message)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def nonempty_string(value: Any, label: str) -> str:
    if not isinstance(value, (str, int)) or not str(value).strip():
        fail(f"{label} must be a non-empty string")
    return str(value).strip()


def resolve_source(base: Path, declared: Any, label: str) -> tuple[Path, str]:
    value = nonempty_string(declared, label)
    candidate = Path(value)
    if candidate.is_absolute():
        fail(f"{label} must be relative to the source manifest")
    resolved_base = base.resolve()
    resolved = (base / candidate).resolve()
    try:
        relative = resolved.relative_to(resolved_base)
    except ValueError:
        fail(f"{label} escapes the source-manifest directory: {value}")
    if not resolved.is_file():
        fail(f"{label} is not a file: {resolved}")
    return resolved, relative.as_posix()


def write_json_exclusive(path: Path, payload: dict[str, Any], *, private: bool = False) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    mode = 0o600 if private else 0o644
    descriptor = os.open(path, flags, mode)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
    except Exception:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        raise


def relative_path(target: Path, base: Path) -> str:
    return Path(os.path.relpath(target.resolve(), base.resolve())).as_posix()


def validate_source_manifest(
    path: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    payload = load_json_object(path)
    required = {
        "schema_version", "campaign_id", "batch_id", "judging_contract", "responses"
    }
    missing = required - payload.keys()
    if missing:
        fail(f"source manifest missing fields: {', '.join(sorted(missing))}")
    for field in ("schema_version", "campaign_id", "batch_id"):
        nonempty_string(payload[field], field)
    responses = payload["responses"]
    if not isinstance(responses, list) or not responses:
        fail("source manifest responses must be a non-empty array")
    base = path.parent.resolve()

    raw_contract = payload["judging_contract"]
    if not isinstance(raw_contract, dict):
        fail("source manifest judging_contract must be an object")
    contract_fields = {
        "judge_spec_version",
        "judge_prompt_path",
        "judgment_schema_path",
        "validator_path",
        "validator_support_path",
        "validator_version",
    }
    missing_contract = contract_fields - raw_contract.keys()
    extra_contract = raw_contract.keys() - contract_fields
    if missing_contract:
        fail(f"judging_contract missing fields: {', '.join(sorted(missing_contract))}")
    if extra_contract:
        fail(f"judging_contract has unexpected fields: {', '.join(sorted(extra_contract))}")
    judging_contract: dict[str, Any] = {
        "judge_spec_version": nonempty_string(
            raw_contract["judge_spec_version"], "judging_contract.judge_spec_version"
        ),
        "validator_version": nonempty_string(
            raw_contract["validator_version"], "judging_contract.validator_version"
        ),
    }
    for field in (
        "judge_prompt_path",
        "judgment_schema_path",
        "validator_path",
        "validator_support_path",
    ):
        resolved, relative = resolve_source(base, raw_contract[field], f"judging_contract.{field}")
        judging_contract[field] = resolved
        judging_contract[field.replace("_path", "_relative")] = relative
    load_json_object(judging_contract["judgment_schema_path"])

    normalized: list[dict[str, Any]] = []
    source_ids: set[str] = set()
    source_paths: set[str] = set()
    cells: set[tuple[str, str, str]] = set()
    item_sources: dict[str, tuple[str, str, str | None]] = {}
    required_response_fields = {
        "source_run_id",
        "system_id",
        "repetition_id",
        "item_id",
        "response_path",
        "item_path",
        "rubric_path",
        "model_identity",
    }
    for index, raw in enumerate(responses):
        if not isinstance(raw, dict):
            fail(f"responses[{index}] must be an object")
        missing_fields = required_response_fields - raw.keys()
        if missing_fields:
            fail(f"responses[{index}] missing fields: {', '.join(sorted(missing_fields))}")
        source_run_id = nonempty_string(raw["source_run_id"], f"responses[{index}].source_run_id")
        system_id = nonempty_string(raw["system_id"], f"responses[{index}].system_id")
        repetition_id = nonempty_string(
            raw["repetition_id"], f"responses[{index}].repetition_id"
        )
        item_id = nonempty_string(raw["item_id"], f"responses[{index}].item_id")
        if not isinstance(raw["model_identity"], dict):
            fail(f"responses[{index}].model_identity must be an object")
        response_path, response_relative = resolve_source(
            base, raw["response_path"], f"responses[{index}].response_path"
        )
        item_path, item_relative = resolve_source(
            base, raw["item_path"], f"responses[{index}].item_path"
        )
        rubric_path, rubric_relative = resolve_source(
            base, raw["rubric_path"], f"responses[{index}].rubric_path"
        )
        reference_path: Path | None = None
        reference_relative: str | None = None
        if raw.get("reference_path") not in (None, ""):
            reference_path, reference_relative = resolve_source(
                base, raw["reference_path"], f"responses[{index}].reference_path"
            )

        try:
            response_text = response_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            fail(f"source response must be UTF-8 text: {response_relative}")
        if not response_text.strip():
            fail(f"source response is empty: {response_relative}")
        try:
            item_text = item_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            fail(f"source item must be UTF-8 text: {item_relative}")
        if not item_text.strip():
            fail(f"source item is empty: {item_relative}")

        rubric = load_json_object(rubric_path)
        validate_rubric(rubric)
        if rubric.get("item_id") != item_id:
            fail(f"rubric item_id does not match responses[{index}].item_id")
        if rubric.get("judge_spec_version") != judging_contract["judge_spec_version"]:
            fail(
                f"rubric judge_spec_version does not match the frozen judging contract "
                f"for responses[{index}]"
            )
        if rubric.get("frozen") is not True:
            fail(f"rubric must be frozen before blind preparation: {rubric_relative}")

        if source_run_id in source_ids:
            fail(f"duplicate source_run_id: {source_run_id}")
        if response_relative in source_paths:
            fail(f"one source response is listed more than once: {response_relative}")
        cell = (system_id, item_id, repetition_id)
        if cell in cells:
            fail(f"duplicate system/item/repetition cell: {cell}")
        source_ids.add(source_run_id)
        source_paths.add(response_relative)
        cells.add(cell)

        item_signature = (item_relative, rubric_relative, reference_relative)
        if item_id in item_sources and item_sources[item_id] != item_signature:
            fail(f"item {item_id} has inconsistent rubric or reference paths")
        item_sources[item_id] = item_signature

        normalized.append(
            {
                "source_run_id": source_run_id,
                "system_id": system_id,
                "repetition_id": repetition_id,
                "item_id": item_id,
                "response_path": response_path,
                "response_relative": response_relative,
                "item_path": item_path,
                "item_relative": item_relative,
                "rubric_path": rubric_path,
                "rubric_relative": rubric_relative,
                "reference_path": reference_path,
                "reference_relative": reference_relative,
                "model_identity": raw["model_identity"],
            }
        )
    return payload, normalized, judging_contract


def prepare(source_manifest_path: Path, output_dir: Path, identity_map_path: Path) -> None:
    source_manifest_path = source_manifest_path.resolve()
    output_dir = output_dir.resolve()
    identity_map_path = identity_map_path.resolve()
    if output_dir.exists():
        fail(f"refusing to overwrite existing output directory: {output_dir}")
    if identity_map_path.exists():
        fail(f"refusing to overwrite existing identity map: {identity_map_path}")
    try:
        identity_map_path.relative_to(output_dir)
    except ValueError:
        pass
    else:
        fail("private identity map must not be stored inside the blind-batch directory")

    source_manifest, sources, source_contract = validate_source_manifest(source_manifest_path)
    # Do not preserve a potentially identity-revealing source-manifest order.
    secrets.SystemRandom().shuffle(sources)
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    identity_map_path.parent.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir()
    (output_dir / "items").mkdir()
    (output_dir / "responses").mkdir()
    (output_dir / "judgments").mkdir()
    contract_dir = output_dir / "contract"
    contract_dir.mkdir()
    (contract_dir / "schemas").mkdir()
    (contract_dir / "tools").mkdir()

    contract_targets = {
        "judge_prompt_path": contract_dir / "judge-prompt.md",
        "judgment_schema_path": contract_dir / "schemas" / "judgment.schema.json",
        "validator_path": contract_dir / "tools" / "validate_judgment.py",
        "validator_support_path": contract_dir / "tools" / "schema_validation.py",
    }
    for field, target in contract_targets.items():
        shutil.copyfile(source_contract[field], target)
    judging_contract = {
        "judge_spec_version": source_contract["judge_spec_version"],
        "judge_prompt_path": contract_targets["judge_prompt_path"].relative_to(output_dir).as_posix(),
        "judge_prompt_sha256": sha256_file(contract_targets["judge_prompt_path"]),
        "judgment_schema_path": contract_targets["judgment_schema_path"].relative_to(output_dir).as_posix(),
        "judgment_schema_sha256": sha256_file(contract_targets["judgment_schema_path"]),
        "validator_path": contract_targets["validator_path"].relative_to(output_dir).as_posix(),
        "validator_sha256": sha256_file(contract_targets["validator_path"]),
        "validator_support_path": contract_targets["validator_support_path"].relative_to(output_dir).as_posix(),
        "validator_support_sha256": sha256_file(contract_targets["validator_support_path"]),
        "validator_version": source_contract["validator_version"],
    }

    created_at = utc_now()
    item_artifacts: list[dict[str, Any]] = []
    copied_items: dict[str, dict[str, Any]] = {}
    manifest_responses: list[dict[str, Any]] = []
    identity_entries: list[dict[str, Any]] = []
    anonymous_ids: set[str] = set()

    for source in sources:
        item_id = source["item_id"]
        if item_id not in copied_items:
            item_slug = hashlib_sha256_text(item_id)[:16]
            item_dir = output_dir / "items" / item_slug
            item_dir.mkdir()
            item_target = item_dir / "item.txt"
            shutil.copyfile(source["item_path"], item_target)
            rubric_target = item_dir / "rubric.json"
            shutil.copyfile(source["rubric_path"], rubric_target)
            artifact: dict[str, Any] = {
                "item_id": item_id,
                "item_path": item_target.relative_to(output_dir).as_posix(),
                "item_sha256": sha256_file(item_target),
                "rubric_path": rubric_target.relative_to(output_dir).as_posix(),
                "rubric_sha256": sha256_file(rubric_target),
            }
            reference_source = source["reference_path"]
            if reference_source is not None:
                suffix = reference_source.suffix.lower()
                reference_target = item_dir / f"reference{suffix}"
                shutil.copyfile(reference_source, reference_target)
                artifact["reference_path"] = reference_target.relative_to(output_dir).as_posix()
                artifact["reference_sha256"] = sha256_file(reference_target)
            copied_items[item_id] = artifact
            item_artifacts.append(artifact)

        anonymous_id = "R_" + secrets.token_hex(16)
        while anonymous_id in anonymous_ids:
            anonymous_id = "R_" + secrets.token_hex(16)
        anonymous_ids.add(anonymous_id)
        blind_relative = f"responses/{anonymous_id}.txt"
        judgment_relative = f"judgments/{anonymous_id}.json"
        blind_target = output_dir / blind_relative
        shutil.copyfile(source["response_path"], blind_target)
        source_hash = sha256_file(source["response_path"])
        blind_hash = sha256_file(blind_target)
        if source_hash != blind_hash:
            fail(f"copy verification failed for source run {source['source_run_id']}")

        public_entry = {
            "anonymous_response_id": anonymous_id,
            "item_id": item_id,
            "response_sha256": source_hash,
            "blind_input_path": blind_relative,
            "blind_input_sha256": blind_hash,
            "planned_judgment_path": judgment_relative,
        }
        manifest_responses.append(public_entry)
        identity_entries.append(
            {
                **public_entry,
                "source_run_id": source["source_run_id"],
                "system_id": source["system_id"],
                "repetition_id": source["repetition_id"],
                "source_response_path": source["response_relative"],
                "source_response_sha256": source_hash,
                "model_identity": source["model_identity"],
            }
        )

    manifest = {
        "schema_version": "1.0",
        "campaign_id": nonempty_string(source_manifest["campaign_id"], "campaign_id"),
        "batch_id": nonempty_string(source_manifest["batch_id"], "batch_id"),
        "created_at": created_at,
        "judging_contract": judging_contract,
        "item_artifacts": sorted(item_artifacts, key=lambda item: item["item_id"]),
        "responses": manifest_responses,
    }
    manifest_path = output_dir / "blind-batch-manifest.json"
    write_json_exclusive(manifest_path, manifest)
    validate_manifest(manifest_path, manifest)

    identity = {
        "schema_version": "1.0",
        "campaign_id": manifest["campaign_id"],
        "batch_id": manifest["batch_id"],
        "created_at": created_at,
        "source_manifest_path": relative_path(source_manifest_path, identity_map_path.parent),
        "source_manifest_sha256": sha256_file(source_manifest_path),
        "blind_batch_manifest_path": relative_path(manifest_path, identity_map_path.parent),
        "blind_batch_manifest_sha256": sha256_file(manifest_path),
        "entries": identity_entries,
    }
    write_json_exclusive(identity_map_path, identity, private=True)
    validate_identity_map(manifest_path, manifest, identity_map_path, identity)


def hashlib_sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-manifest", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--identity-map", required=True, type=Path)
    args = parser.parse_args()
    prepare(args.source_manifest, args.output_dir, args.identity_map)
    print(f"OK: created blind batch at {args.output_dir} and private identity map at {args.identity_map}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
