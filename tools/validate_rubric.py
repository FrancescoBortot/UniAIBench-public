#!/usr/bin/env python3
"""Validate UniAIBench rubric invariants without third-party packages."""

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


def contains_placeholder(value: Any) -> bool:
    if isinstance(value, str):
        return "<" in value and ">" in value
    if isinstance(value, list):
        return any(contains_placeholder(item) for item in value)
    if isinstance(value, dict):
        return any(contains_placeholder(item) for item in value.values())
    return False


def validate(payload: dict[str, Any], template: bool = False) -> None:
    schema_path = Path(__file__).resolve().parents[1] / "schemas" / "rubric.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validate_json_schema(payload, schema)
    required = {
        "rubric_version", "judge_spec_version", "item_id", "subject",
        "domain_profile", "created_without_model_answers", "frozen",
        "reference_status", "subproblems", "atomic_criteria",
        "dimension_applicability", "dimension_point_budget",
        "rubric_specific_caps", "human_review_triggers", "human_approval",
    }
    missing = sorted(required - payload.keys())
    if missing:
        fail(f"missing fields: {', '.join(missing)}")
    if payload["created_without_model_answers"] is not True:
        fail("created_without_model_answers must be true")

    applicability = payload["dimension_applicability"]
    budgets = payload["dimension_point_budget"]
    if set(applicability) != set(DIMENSIONS) or set(budgets) != set(DIMENSIONS):
        fail("dimension maps must contain exactly T1 through T8")
    if not math.isclose(sum(float(budgets[d]) for d in DIMENSIONS), 100.0, abs_tol=1e-8):
        fail("dimension_point_budget must sum to 100")

    subproblems = payload["subproblems"]
    if not isinstance(subproblems, list) or not subproblems:
        fail("at least one subproblem is required")
    subproblem_ids = [item.get("id") for item in subproblems]
    if len(subproblem_ids) != len(set(subproblem_ids)):
        fail("subproblem IDs must be unique")
    if not math.isclose(sum(float(item["weight"]) for item in subproblems), 1.0, abs_tol=1e-8):
        fail("subproblem weights must sum to 1")

    criteria = payload["atomic_criteria"]
    if template:
        if payload["frozen"] or payload["human_approval"].get("approved"):
            fail("a blank template cannot be frozen or approved")
        return
    if contains_placeholder(payload):
        fail("unresolved template placeholders remain")
    if not criteria:
        fail("a completed rubric must contain atomic criteria")

    criterion_ids = [item.get("criterion_id") for item in criteria]
    if len(criterion_ids) != len(set(criterion_ids)):
        fail("criterion IDs must be unique")
    points_by_dimension = {dimension: 0.0 for dimension in DIMENSIONS}
    points_by_subproblem = {subproblem_id: 0.0 for subproblem_id in subproblem_ids}
    for criterion in criteria:
        if criterion.get("subproblem_id") not in subproblem_ids:
            fail(f"unknown subproblem in criterion {criterion.get('criterion_id')}")
        dimension = criterion.get("primary_dimension")
        if dimension not in DIMENSIONS:
            fail(f"invalid primary dimension in criterion {criterion.get('criterion_id')}")
        points = float(criterion.get("max_points", 0))
        if points <= 0:
            fail(f"max_points must be positive in criterion {criterion.get('criterion_id')}")
        points_by_dimension[dimension] += points
        points_by_subproblem[criterion["subproblem_id"]] += points
        for rule in criterion.get("partial_credit_rules", []):
            fraction = float(rule.get("credit_fraction", -1))
            if not 0 <= fraction <= 1:
                fail(f"partial-credit fraction outside [0,1] in {criterion.get('criterion_id')}")

    for dimension in DIMENSIONS:
        applicable = applicability[dimension] == "applicable"
        expected = float(budgets[dimension]) if applicable else 0.0
        if not math.isclose(points_by_dimension[dimension], expected, abs_tol=1e-8):
            fail(
                f"{dimension} criteria total {points_by_dimension[dimension]}, "
                f"expected {expected}"
            )
    applicable_total = sum(points_by_dimension.values())
    if applicable_total <= 0:
        fail("completed rubric has no applicable point budget")
    for subproblem in subproblems:
        observed_weight = points_by_subproblem[subproblem["id"]] / applicable_total
        if not math.isclose(observed_weight, float(subproblem["weight"]), abs_tol=1e-8):
            fail(
                f"subproblem {subproblem['id']} weight {subproblem['weight']} does not match "
                f"its criterion allocation ({observed_weight:.8f})"
            )
    approval = payload["human_approval"]
    if payload["frozen"] and not (
        approval.get("approved") and approval.get("reviewer") and approval.get("date")
    ):
        fail("a frozen rubric requires dated human approval")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    parser.add_argument("--template", action="store_true")
    args = parser.parse_args()
    payload = json.loads(args.path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        fail("rubric root must be an object")
    validate(payload, template=args.template)
    print(f"OK: {args.path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
