#!/usr/bin/env python3
"""Validate UniAIBench judgment arithmetic and structural invariants."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

from schema_validation import validate_json_schema


DIMENSIONS = tuple(f"T{number}" for number in range(1, 9))


def fail(message: str) -> None:
    raise ValueError(message)


def validate(payload: dict[str, Any], template: bool = False) -> None:
    schema_path = Path(__file__).resolve().parents[1] / "schemas" / "judgment.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validate_json_schema(payload, schema)
    required = {
        "judgment_version", "item_id", "response_id", "rubric_version",
        "criterion_assessment", "dimensions", "technical_score",
        "atomic_errors", "extra_penalties", "cap", "result_status",
        "technical_summary", "judge_confidence", "review_flags",
        "requires_human_review", "human_review_reason", "run_validity",
    }
    missing = sorted(required - payload.keys())
    if missing:
        fail(f"missing fields: {', '.join(missing)}")
    dimensions = payload["dimensions"]
    if set(dimensions) != set(DIMENSIONS):
        fail("dimensions must contain exactly T1 through T8")

    for dimension, result in dimensions.items():
        score = float(result["score"])
        maximum = float(result["max_score"])
        if score < 0 or score > maximum:
            fail(f"{dimension} score is outside its valid range")
        if result["status"] == "not_applicable" and (score != 0 or maximum != 0):
            fail(f"{dimension} marked not_applicable must have score=max_score=0")

    if template:
        if payload["criterion_assessment"]:
            fail("blank judgment template must not contain criterion assessments")
        return

    criteria = payload["criterion_assessment"]
    if not criteria:
        fail("a completed judgment requires criterion assessments")
    criterion_ids = [item["criterion_id"] for item in criteria]
    if len(criterion_ids) != len(set(criterion_ids)):
        fail("criterion assessments must be unique")

    awards_by_dimension = {dimension: 0.0 for dimension in DIMENSIONS}
    maxima_by_dimension = {dimension: 0.0 for dimension in DIMENSIONS}
    for item in criteria:
        maximum = float(item["max_points"])
        fraction = float(item["credit_fraction"])
        award = float(item["awarded_points"])
        if not 0 <= fraction <= 1:
            fail(f"credit fraction outside [0,1] for {item['criterion_id']}")
        if not math.isclose(award, maximum * fraction, abs_tol=1e-6):
            fail(f"award arithmetic mismatch for {item['criterion_id']}")
        awards_by_dimension[item["primary_dimension"]] += award
        maxima_by_dimension[item["primary_dimension"]] += maximum

    for dimension in DIMENSIONS:
        if not math.isclose(
            awards_by_dimension[dimension], float(dimensions[dimension]["score"]), abs_tol=1e-6
        ):
            fail(f"{dimension} does not equal its criterion awards")
        if not math.isclose(
            maxima_by_dimension[dimension], float(dimensions[dimension]["max_score"]), abs_tol=1e-6
        ):
            fail(f"{dimension} max_score does not equal its criterion maxima")

    technical = payload["technical_score"]
    raw = sum(awards_by_dimension.values())
    applicable_max = sum(
        float(dimensions[d]["max_score"])
        for d in DIMENSIONS
        if dimensions[d]["status"] == "scored"
    )
    if not math.isclose(raw, float(technical["raw_score"]), abs_tol=1e-6):
        fail("raw_score does not equal summed criterion awards")
    if not math.isclose(applicable_max, float(technical["applicable_max_score"]), abs_tol=1e-6):
        fail("applicable_max_score does not equal applicable dimension maxima")
    normalized = 100 * raw / applicable_max
    if not math.isclose(normalized, float(technical["normalized_score_before_penalties"]), abs_tol=1e-5):
        fail("normalized score arithmetic mismatch")
    penalties = sum(float(item["points"]) for item in payload["extra_penalties"])
    if not math.isclose(penalties, float(technical["extra_penalty_total"]), abs_tol=1e-6):
        fail("extra_penalty_total mismatch")
    after_penalties = max(0.0, normalized - penalties)
    if not math.isclose(after_penalties, float(technical["score_after_penalties"]), abs_tol=1e-5):
        fail("score_after_penalties arithmetic mismatch")
    cap = payload["cap"]
    applied_cap = technical["applied_cap"]
    if cap["applied"] and (cap["value"] is None or applied_cap != cap["value"]):
        fail("technical_score.applied_cap must equal the applied cap value")
    if not cap["applied"] and applied_cap is not None:
        fail("technical_score.applied_cap must be null when no cap is applied")
    expected_final = min(after_penalties, float(cap["value"])) if cap["applied"] else after_penalties
    if not math.isclose(expected_final, float(technical["final_score"]), abs_tol=1e-5):
        fail("final_score does not reflect penalties and cap")
    if payload["requires_human_review"] and not payload["human_review_reason"].strip():
        fail("human-review escalation requires a reason")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    parser.add_argument("--template", action="store_true")
    args = parser.parse_args()
    payload = json.loads(args.path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        fail("judgment root must be an object")
    validate(payload, template=args.template)
    print(f"OK: {args.path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
