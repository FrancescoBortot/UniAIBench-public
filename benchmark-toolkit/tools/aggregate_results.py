#!/usr/bin/env python3
"""Aggregate unblinded benchmark records using a frozen, hashed configuration."""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
import shutil
import statistics
import tempfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from schema_validation import validate_json_schema
from validate_blind_batch import load_json_object, require_hash, sha256_file


TOOLKIT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = TOOLKIT_ROOT / "schemas" / "aggregation-config.schema.json"
SOFTWARE_NAME = "benchmark-toolkit.aggregate_results"
SOFTWARE_VERSION = "1.0"


def fail(message: str) -> None:
    raise ValueError(message)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def resolve_config_path(config_path: Path, declared: str, label: str) -> Path:
    candidate = Path(declared)
    if candidate.is_absolute():
        fail(f"{label} must be relative to the aggregation config")
    operational_root = config_path.parent.resolve()
    resolved = (operational_root / candidate).resolve()
    try:
        resolved.relative_to(operational_root)
    except ValueError:
        fail(f"{label} escapes the aggregation operational root: {resolved}")
    return resolved


def field_value(record: dict[str, Any], dotted_path: str) -> Any:
    value: Any = record
    for component in dotted_path.split("."):
        if not isinstance(value, dict) or component not in value:
            raise KeyError(dotted_path)
        value = value[component]
    return value


def finite_number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        fail(f"{label} must be numeric")
    number = float(value)
    if not math.isfinite(number):
        fail(f"{label} must be finite")
    return number


def reducer(name: str) -> Callable[[list[float]], float]:
    if name == "mean":
        return statistics.fmean
    if name == "median":
        return statistics.median
    if name == "first_authoritative":
        return lambda values: values[0]
    fail(f"unsupported aggregation reducer: {name}")


def percentile(values: list[float], probability: float) -> float:
    if not values:
        fail("cannot calculate a percentile of an empty sample")
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def bootstrap_interval(
    item_scores: dict[str, float],
    *,
    samples: int,
    confidence_level: float,
    seed: int,
    weights: dict[str, float],
) -> tuple[float, float]:
    item_ids = sorted(item_scores)
    if not item_ids:
        fail("cannot bootstrap a system with no eligible items")
    rng = random.Random(seed)
    estimates: list[float] = []
    for _ in range(samples):
        drawn = [rng.choice(item_ids) for _ in item_ids]
        numerator = sum(item_scores[item_id] * weights.get(item_id, 1.0) for item_id in drawn)
        denominator = sum(weights.get(item_id, 1.0) for item_id in drawn)
        estimates.append(numerator / denominator)
    alpha = 1.0 - confidence_level
    return percentile(estimates, alpha / 2), percentile(estimates, 1 - alpha / 2)


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    with path.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    with path.open("x", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")


def aggregate(config_path: Path) -> dict[str, Any]:
    config_path = config_path.resolve()
    config = load_json_object(config_path)
    schema = load_json_object(SCHEMA_PATH)
    validate_json_schema(config, schema)
    if config["status"] != "frozen":
        fail("aggregation config must have status='frozen'")

    input_config = config["input"]
    input_path = resolve_config_path(
        config_path, str(input_config["unblinded_results_path"]), "unblinded results path"
    )
    require_hash(
        input_path,
        str(input_config["unblinded_results_sha256"]),
        "unblinded results",
    )
    unblinded = load_json_object(input_path)
    records = unblinded.get("records")
    if not isinstance(records, list):
        fail("unblinded results must contain a records array")
    upstream_exclusions = unblinded.get("exclusions", [])
    if not isinstance(upstream_exclusions, list):
        fail("unblinded results exclusions must be an array")
    if not records and not upstream_exclusions:
        fail("unblinded results must contain records or exclusions")

    fields = config["fields"]
    system_field = str(fields["system_field"])
    item_field = str(fields["item_field"])
    repetition_field = str(fields["repetition_field"])
    score_field = str(fields["score_field"])
    eligibility = config["eligibility"]
    eligible_field = eligibility.get("field")
    eligible_values = list(eligibility.get("accepted_values", []))

    observations: list[dict[str, Any]] = []
    excluded: list[dict[str, str]] = []
    seen_cells: set[tuple[str, str, str]] = set()
    planned_cells: set[tuple[str, str]] = set()
    cells_with_exclusions: set[tuple[str, str]] = set()

    for index, exclusion in enumerate(upstream_exclusions):
        if not isinstance(exclusion, dict):
            fail(f"exclusions[{index}] must be an object")
        try:
            system_id = str(exclusion["system_id"])
            item_id = str(exclusion["item_id"])
            repetition_id = str(exclusion["repetition_id"])
        except KeyError as exc:
            fail(f"exclusions[{index}] is missing required field {exc.args[0]}")
        if not system_id or not item_id or not repetition_id:
            fail(f"exclusions[{index}] has an empty grouping identifier")
        key = (system_id, item_id, repetition_id)
        if key in seen_cells:
            fail(f"duplicate system/item/repetition coordinate: {key}")
        seen_cells.add(key)
        planned_cells.add((system_id, item_id))
        cells_with_exclusions.add((system_id, item_id))
        excluded.append(
            {
                "system_id": system_id,
                "item_id": item_id,
                "repetition_id": repetition_id,
                "reason": str(exclusion.get("reason", "upstream exclusion")),
                "source": "unblinded_results.exclusions",
            }
        )

    for index, record in enumerate(records):
        if not isinstance(record, dict):
            fail(f"records[{index}] must be an object")
        try:
            system_id = str(field_value(record, system_field))
            item_id = str(field_value(record, item_field))
            repetition_id = str(field_value(record, repetition_field))
            score = finite_number(field_value(record, score_field), f"records[{index}] score")
        except KeyError as exc:
            fail(f"records[{index}] is missing configured field {exc.args[0]}")
        if not system_id or not item_id or not repetition_id:
            fail(f"records[{index}] has an empty grouping identifier")
        key = (system_id, item_id, repetition_id)
        if key in seen_cells:
            fail(f"duplicate system/item/repetition coordinate: {key}")
        seen_cells.add(key)
        planned_cells.add((system_id, item_id))
        if eligible_field:
            try:
                eligible_value = field_value(record, str(eligible_field))
            except KeyError:
                cells_with_exclusions.add((system_id, item_id))
                excluded.append({"system_id": system_id, "item_id": item_id, "repetition_id": repetition_id, "reason": "missing eligibility field", "source": "eligibility_filter"})
                continue
            if eligible_values and eligible_value not in eligible_values:
                cells_with_exclusions.add((system_id, item_id))
                excluded.append({"system_id": system_id, "item_id": item_id, "repetition_id": repetition_id, "reason": f"ineligible value {eligible_value!r}", "source": "eligibility_filter"})
                continue
        observations.append(
            {
                "system_id": system_id,
                "item_id": item_id,
                "repetition_id": repetition_id,
                "score": score,
                "record": record,
            }
        )
    repetition_policy = config["repetition_aggregation"]
    reduce_repetitions = reducer(str(repetition_policy["method"]))
    expected_repetitions = repetition_policy.get("expected_repetitions_per_cell")
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for observation in observations:
        grouped[(observation["system_id"], observation["item_id"])].append(observation)

    missing_policy = str(config["missing_data"]["policy"])
    incomplete_cells: set[tuple[str, str]] = set(cells_with_exclusions)
    if expected_repetitions is not None:
        expected_count = int(expected_repetitions)
        incomplete_cells.update(
            key for key in planned_cells if len(grouped.get(key, [])) != expected_count
        )
    if excluded and missing_policy == "fail":
        fail("missing-data policy is 'fail' but the input contains exclusions")
    if incomplete_cells and missing_policy == "fail":
        if expected_repetitions is not None:
            fail(f"cells do not have {int(expected_repetitions)} repetitions: {sorted(incomplete_cells)}")
        fail(f"incomplete cells are not allowed by missing-data policy 'fail': {sorted(incomplete_cells)}")

    cell_scores: dict[tuple[str, str], float] = {}
    cell_counts: dict[tuple[str, str], int] = {}
    for key, values in grouped.items():
        if key in incomplete_cells and missing_policy == "exclude_cell":
            if not any(
                entry["system_id"] == key[0]
                and entry["item_id"] == key[1]
                and entry["reason"] == "incomplete repetition cell"
                for entry in excluded
            ):
                excluded.append({"system_id": key[0], "item_id": key[1], "repetition_id": "", "reason": "incomplete repetition cell", "source": "aggregation"})
            continue
        ordered = sorted(values, key=lambda item: item["repetition_id"])
        cell_scores[key] = reduce_repetitions([item["score"] for item in ordered])
        cell_counts[key] = len(ordered)

    systems = sorted({system for system, _ in planned_cells})
    all_items = sorted({item for _, item in planned_cells})
    items_by_system = {
        system: {item for candidate, item in cell_scores if candidate == system}
        for system in systems
    }
    if not systems or not all_items:
        fail("no complete system-item cells remain")
    common_items = set.intersection(*(items_by_system[system] for system in systems))
    panel_complete = all(items_by_system[system] == set(all_items) for system in systems)
    if missing_policy == "fail" and not panel_complete:
        fail("missing-data policy is 'fail' but the system-item panel is not complete")
    if missing_policy == "exclude_cell":
        if not common_items:
            fail("no common item remains after excluding incomplete cells")
        analysis_items = {system: common_items for system in systems}
    elif missing_policy == "available_case":
        analysis_items = items_by_system
    elif missing_policy == "fail":
        analysis_items = {system: set(all_items) for system in systems}
    else:
        fail(f"unsupported missing-data policy: {missing_policy}")
    empty_systems = sorted(system for system, items in analysis_items.items() if not items)
    if empty_systems:
        fail(f"systems have no eligible items after missing-data handling: {empty_systems}")

    item_policy = config["item_aggregation"]
    item_method = str(item_policy["method"])
    if item_method not in {"mean", "weighted_mean"}:
        fail(f"unsupported item aggregation method: {item_method}")
    raw_weights = item_policy.get("weights", {})
    weights = {str(key): finite_number(value, f"weight for {key}") for key, value in raw_weights.items()}
    if any(value <= 0 for value in weights.values()):
        fail("item weights must be positive")
    observed_analysis_items = set().union(*analysis_items.values())
    if item_method == "mean" and weights:
        fail("item weights must be empty when item aggregation method is 'mean'")
    if item_method == "weighted_mean" and set(weights) != observed_analysis_items:
        missing_weights = sorted(observed_analysis_items - set(weights))
        extra_weights = sorted(set(weights) - observed_analysis_items)
        fail(
            "weighted_mean requires exactly one weight per analyzed item; "
            f"missing={missing_weights}, extra={extra_weights}"
        )

    bootstrap = config["bootstrap"]
    bootstrap_enabled = bool(bootstrap["enabled"])
    if bootstrap_enabled:
        if bootstrap["method"] != "percentile" or bootstrap["resampling_unit"] != "item":
            fail("only percentile item bootstrap is supported")
        samples = int(bootstrap["samples"])
        confidence_level = float(bootstrap["confidence_level"])
        seed = int(bootstrap["seed"])
        if samples < 1:
            fail("bootstrap.samples must be at least 1")
        if not 0 < confidence_level < 1:
            fail("bootstrap.confidence_level must be strictly between 0 and 1")
    else:
        samples = 0
        confidence_level = float(bootstrap.get("confidence_level", 0.95))
        seed = int(bootstrap.get("seed", 0))

    system_rows: list[dict[str, Any]] = []
    for system in systems:
        item_scores = {
            item: cell_scores[(system, item)] for item in sorted(analysis_items[system])
        }
        effective_weights = weights if item_method == "weighted_mean" else {}
        numerator = sum(score * effective_weights.get(item, 1.0) for item, score in item_scores.items())
        denominator = sum(effective_weights.get(item, 1.0) for item in item_scores)
        mean_score = numerator / denominator
        if bootstrap_enabled:
            lower, upper = bootstrap_interval(
                item_scores,
                samples=samples,
                confidence_level=confidence_level,
                seed=seed,
                weights=effective_weights,
            )
        else:
            lower, upper = None, None
        system_rows.append(
            {
                "system_id": system,
                "mean_score": mean_score,
                "ci_lower": lower,
                "ci_upper": upper,
                "eligible_items": len(item_scores),
                "total_items": len(all_items),
                "coverage": len(item_scores) / len(all_items),
                "retained_responses": sum(cell_counts[(system, item)] for item in item_scores),
            }
        )
    system_rows.sort(key=lambda row: (-float(row["mean_score"]), str(row["system_id"])))
    for rank, row in enumerate(system_rows, start=1):
        row["rank"] = rank

    cell_rows = [
        {
            "system_id": system,
            "item_id": item,
            "repetition_count": cell_counts[(system, item)],
            "cell_score": cell_scores[(system, item)],
            "included_in_system_score": item in analysis_items[system],
        }
        for system, item in sorted(cell_scores)
    ]

    outputs = config["outputs"]
    output_dir = resolve_config_path(config_path, str(outputs["directory"]), "output directory")
    if output_dir.exists():
        fail(f"refusing to overwrite existing aggregation output directory: {output_dir}")
    system_path = output_dir / str(outputs["system_table_csv"])
    cell_path = output_dir / str(outputs["cell_table_csv"])
    summary_path = output_dir / str(outputs["summary_json"])
    output_targets = (system_path, cell_path, summary_path)
    for target in output_targets:
        try:
            target.resolve().relative_to(output_dir.resolve())
        except ValueError:
            fail(f"output filename escapes output directory: {target}")
        if target.parent != output_dir:
            fail(f"output filenames must not contain directories: {target.name}")
    if len({target.resolve() for target in output_targets}) != len(output_targets):
        fail("aggregation output filenames must be distinct")

    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging_dir = Path(
        tempfile.mkdtemp(prefix=f".{output_dir.name}.staging-", dir=output_dir.parent)
    )
    staged_system_path = staging_dir / system_path.name
    staged_cell_path = staging_dir / cell_path.name
    staged_summary_path = staging_dir / summary_path.name
    try:
        write_csv(
            staged_system_path,
            ["rank", "system_id", "mean_score", "ci_lower", "ci_upper", "eligible_items", "total_items", "coverage", "retained_responses"],
            system_rows,
        )
        write_csv(
            staged_cell_path,
            ["system_id", "item_id", "repetition_count", "cell_score", "included_in_system_score"],
            cell_rows,
        )
        summary = {
            "schema_version": "1.0",
            "aggregation_id": config["aggregation_id"],
            "created_at": utc_now(),
            "campaign_id": unblinded.get("campaign_id"),
            "batch_id": unblinded.get("batch_id"),
            "input_path": str(input_config["unblinded_results_path"]),
            "input_sha256": sha256_file(input_path),
            "aggregation_config_path": config_path.name,
            "aggregation_config_sha256": sha256_file(config_path),
            "software": {
                "name": SOFTWARE_NAME,
                "version": SOFTWARE_VERSION,
            },
            "fields": fields,
            "policies": {
                "missing_data": missing_policy,
                "repetition_aggregation": repetition_policy,
                "item_aggregation": item_policy,
                "bootstrap": bootstrap,
            },
            "counts": {
                "input_records": len(records),
                "input_exclusions": len(upstream_exclusions),
                "eligible_records": len(observations),
                "excluded_records_or_cells": len(excluded),
                "system_item_cells": len(cell_rows),
                "systems": len(systems),
                "items": len(all_items),
                "common_items": len(common_items),
            },
            "excluded": excluded,
            "systems": system_rows,
            "outputs": {
                "system_table_csv": system_path.name,
                "system_table_sha256": sha256_file(staged_system_path),
                "cell_table_csv": cell_path.name,
                "cell_table_sha256": sha256_file(staged_cell_path),
            },
        }
        write_json(staged_summary_path, summary)
        if output_dir.exists():
            fail(f"refusing to overwrite existing aggregation output directory: {output_dir}")
        staging_dir.rename(output_dir)
    except Exception:
        shutil.rmtree(staging_dir, ignore_errors=True)
        raise
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    args = parser.parse_args()
    result = aggregate(args.config)
    print(
        f"OK: aggregated {result['counts']['eligible_records']} responses "
        f"for {result['counts']['systems']} systems"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
