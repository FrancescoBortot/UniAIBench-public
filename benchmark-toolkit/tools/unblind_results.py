#!/usr/bin/env python3
"""Join a complete validated blind batch with its private identity map."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from validate_blind_batch import load_json_object, sha256_file, validate_identity_map
from validate_judgment_batch import validate_batch


def fail(message: str) -> None:
    raise ValueError(message)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def relative_path(target: Path, base: Path) -> str:
    return Path(os.path.relpath(target.resolve(), base.resolve())).as_posix()


def write_private_json_exclusive(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
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


def unblind(
    manifest_path: Path,
    identity_map_path: Path,
    output_path: Path,
    adjudications_dir: Path | None = None,
) -> dict[str, Any]:
    manifest_path = manifest_path.resolve()
    identity_map_path = identity_map_path.resolve()
    output_path = output_path.resolve()
    if output_path.exists():
        fail(f"refusing to overwrite existing unblinded output: {output_path}")
    blind_root = manifest_path.parent.resolve()
    for private_path, label in (
        (identity_map_path, "private identity map"),
        (output_path, "unblinded output"),
    ):
        try:
            private_path.relative_to(blind_root)
        except ValueError:
            continue
        fail(f"{label} must not be stored inside the blind-batch directory")

    validation = validate_batch(
        manifest_path,
        identity_map_path=identity_map_path,
        adjudications_dir=adjudications_dir,
        require_complete=True,
    )
    if not validation["ready_for_unblinding"]:
        unresolved = validation["unresolved_response_ids"]
        fail(f"batch is not ready for unblinding; unresolved responses: {unresolved}")
    manifest = validation["manifest"]
    identity = load_json_object(identity_map_path)
    validate_identity_map(manifest_path, manifest, identity_map_path, identity)

    identities = {
        str(entry["anonymous_response_id"]): entry for entry in identity["entries"]
    }
    judgments = {
        str(entry["anonymous_response_id"]): entry for entry in validation["judgments"]
    }
    exclusions = {
        str(entry["anonymous_response_id"]): entry for entry in validation["exclusions"]
    }
    records: list[dict[str, Any]] = []
    excluded_records: list[dict[str, Any]] = []
    for response in manifest["responses"]:
        response_id = str(response["anonymous_response_id"])
        mapping = identities[response_id]
        if response_id in exclusions:
            exclusion = exclusions[response_id]
            adjudication_path = Path(exclusion["adjudication_path"])
            excluded_records.append(
                {
                    "anonymous_response_id": response_id,
                    "source_run_id": mapping["source_run_id"],
                    "system_id": mapping["system_id"],
                    "item_id": mapping["item_id"],
                    "repetition_id": mapping["repetition_id"],
                    "model_identity": mapping["model_identity"],
                    "source_response_sha256": mapping["source_response_sha256"],
                    "adjudication_id": exclusion["adjudication_id"],
                    "adjudication_path": relative_path(adjudication_path, output_path.parent),
                    "adjudication_sha256": exclusion["adjudication_sha256"],
                    "reason": exclusion["reason"],
                }
            )
            continue
        judgment_record = judgments[response_id]
        judgment = judgment_record["payload"]
        authority = dict(judgment_record["authority"])
        if authority.get("adjudication_path"):
            authority["adjudication_path"] = relative_path(
                Path(authority["adjudication_path"]), output_path.parent
            )
        records.append(
            {
                "anonymous_response_id": response_id,
                "source_run_id": mapping["source_run_id"],
                "system_id": mapping["system_id"],
                "item_id": mapping["item_id"],
                "repetition_id": mapping["repetition_id"],
                "model_identity": mapping["model_identity"],
                "source_response_sha256": mapping["source_response_sha256"],
                "blind_input_sha256": mapping["blind_input_sha256"],
                "planned_judgment_path": str(response["planned_judgment_path"]),
                "judgment_path": relative_path(judgment_record["path"], output_path.parent),
                "judgment_sha256": judgment_record["sha256"],
                "authority": authority,
                "final_score": judgment["technical_score"]["final_score"],
                "dimensions": judgment["dimensions"],
                "judgment": judgment,
            }
        )

    output = {
        "schema_version": "1.0",
        "campaign_id": manifest["campaign_id"],
        "batch_id": manifest["batch_id"],
        "created_at": utc_now(),
        "blind_batch_manifest_path": relative_path(manifest_path, output_path.parent),
        "blind_batch_manifest_sha256": sha256_file(manifest_path),
        "identity_map_path": relative_path(identity_map_path, output_path.parent),
        "identity_map_sha256": sha256_file(identity_map_path),
        "record_count": len(records),
        "excluded_count": len(excluded_records),
        "records": records,
        "exclusions": excluded_records,
    }
    write_private_json_exclusive(output_path, output)
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--identity-map", required=True, type=Path)
    parser.add_argument(
        "--adjudications-dir",
        type=Path,
        help="directory of immutable final adjudications governing replacements or exclusions",
    )
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    output = unblind(
        args.manifest,
        args.identity_map,
        args.output,
        adjudications_dir=args.adjudications_dir,
    )
    print(
        f"OK: wrote {output['record_count']} unblinded records and "
        f"{output['excluded_count']} exclusions to {args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
