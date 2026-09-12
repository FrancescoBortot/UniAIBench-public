#!/usr/bin/env python3
"""Cross-check the UniAIBench study manifest against its public evidence."""

from __future__ import annotations

import csv
import json
from pathlib import Path


STUDY_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = STUDY_ROOT / "STUDY_MANIFEST.json"
SCORES_PATH = STUDY_ROOT / "analysis/data/model_item_scores.csv"
RESOURCES_PATH = STUDY_ROOT / "analysis/data/model_item_resources.csv"


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def integer(value: object, label: str, errors: list[str]) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        errors.append(f"{label} must be an integer")
        return None
    return value


def main() -> int:
    errors: list[str] = []
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    scope = manifest.get("scope", {})
    public_evidence = manifest.get("public_evidence", {})

    scores = read_rows(SCORES_PATH)
    resources = read_rows(RESOURCES_PATH)

    score_cells = {
        (row["model_display_name"], row["item_key"])
        for row in scores
    }
    resource_cells = {(row["model"], row["item_key"]) for row in resources}
    models = {model for model, _ in score_cells}
    items = {item for _, item in score_cells}
    subject_items: dict[str, set[str]] = {}
    for row in scores:
        subject_items.setdefault(row["subject"], set()).add(row["item_key"])

    expected_cells = integer(
        scope.get("matched_model_item_cells"),
        "scope.matched_model_item_cells",
        errors,
    )
    expected_models = integer(
        scope.get("model_mode_configurations"),
        "scope.model_mode_configurations",
        errors,
    )
    expected_items = integer(scope.get("common_items"), "scope.common_items", errors)
    expected_responses = integer(
        scope.get("retained_responses"), "scope.retained_responses", errors
    )

    if len(scores) != len(score_cells):
        errors.append("score panel contains duplicate model--item cells")
    if len(resources) != len(resource_cells):
        errors.append("resource panel contains duplicate model--item cells")
    if score_cells != resource_cells:
        errors.append("score and resource panels do not contain the same model--item cells")
    if expected_cells is not None and len(score_cells) != expected_cells:
        errors.append(
            f"manifest declares {expected_cells} cells but score panel contains {len(score_cells)}"
        )
    if expected_models is not None and len(models) != expected_models:
        errors.append(
            f"manifest declares {expected_models} configurations but score panel contains {len(models)}"
        )
    if expected_items is not None and len(items) != expected_items:
        errors.append(
            f"manifest declares {expected_items} items but score panel contains {len(items)}"
        )

    response_total = sum(int(row["n_responses"]) for row in scores)
    if expected_responses is not None and response_total != expected_responses:
        errors.append(
            f"manifest declares {expected_responses} retained responses but score panel summarizes {response_total}"
        )

    manifest_subjects = {
        entry.get("name"): entry.get("item_count")
        for entry in scope.get("subjects", [])
        if isinstance(entry, dict)
    }
    panel_subjects = {
        "Mathematical Analysis III": len(subject_items.get("analysis_3", set())),
        "General Physics II": len(subject_items.get("physics_2", set())),
    }
    if manifest_subjects != panel_subjects:
        errors.append(
            f"manifest subject counts {manifest_subjects!r} do not match panel {panel_subjects!r}"
        )

    for label, declared in public_evidence.items():
        if not isinstance(declared, str) or not declared:
            errors.append(f"public_evidence.{label} must be a non-empty relative path")
            continue
        candidate = (STUDY_ROOT / declared).resolve()
        try:
            candidate.relative_to(STUDY_ROOT.resolve())
        except ValueError:
            errors.append(f"public_evidence.{label} escapes the study directory")
            continue
        if not candidate.exists():
            errors.append(f"public_evidence.{label} does not exist: {declared}")

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(
        "OK: UniAIBench study manifest matches "
        f"{len(models)} configurations, {len(items)} items, "
        f"{len(score_cells)} cells, and {response_total} retained responses"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
