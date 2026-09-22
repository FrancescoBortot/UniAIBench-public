#!/usr/bin/env python3
"""Rebuild every released UniAIBench table from sanitized public inputs.

The program reads only the two model--item panels, the public model catalog,
and the versioned analysis configuration. It never needs source exercises,
answers, judgments, rubrics, identity maps, or provider-native payloads.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import random
import shutil
import statistics
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd


ANALYSIS_ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = ANALYSIS_ROOT / "data"
CONFIG_PATH = ANALYSIS_ROOT / "config" / "public_analysis.json"
CATALOG_PATH = DATA_ROOT / "model_catalog.json"
PRICING_MANIFEST_PATH = DATA_ROOT / "benchmark_pricing_manifest.json"
SCORES_PATH = DATA_ROOT / "model_item_scores.csv"
RESOURCES_PATH = DATA_ROOT / "model_item_resources.csv"
TABLE_ROOT = ANALYSIS_ROOT / "tables"

SCOPE_DEFINITIONS = {
    "overall": {"subject": None, "ranking": "main_ranking_overall.csv", "profile": "t1_t8_profile_overall.csv"},
    "analysis_3": {"subject": "analysis_3", "ranking": "main_ranking_analysis_iii.csv", "profile": "t1_t8_profile_analysis_iii.csv"},
    "physics_2": {"subject": "physics_2", "ranking": "main_ranking_physics_ii.csv", "profile": "t1_t8_profile_physics_ii.csv"},
}

TOKEN_NUMERIC_FIELDS = {
    "year",
    "exercise",
    "input_tokens",
    "provider_output_tokens",
    "visible_output_tokens",
    "reasoning_tokens_reported",
    "reasoning_tokens_analysis",
    "combined_output_unseparated_tokens",
    "billed_output_tokens",
    "provider_total_tokens",
    "analytical_total_tokens",
    "input_cached_tokens",
    "input_cache_miss_tokens",
    "input_rate_usd_per_million",
    "output_rate_usd_per_million",
    "cost_input_estimated_usd",
    "cost_output_estimated_usd",
    "cost_reconstructed_usd",
    "cost_provider_reported_usd",
    "cost_selected_usd",
    "cost_provider_minus_reconstructed_usd",
    "elapsed_seconds",
    "attempt_count",
    "retry_count",
    "max_output_tokens",
    "n_responses",
}

EXPECTED_TABLES = {
    definition[key]
    for definition in SCOPE_DEFINITIONS.values()
    for key in ("ranking", "profile")
} | {
    "model_coverage.csv",
    "model_token_costs_17x60.csv",
    "quality_token_cost_17x60.csv",
    "token_cost_rates.csv",
    "deepseek_flash_thinking_vs_no_thinking.csv",
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    if not rows and not fieldnames:
        raise ValueError(f"No rows and no explicit schema for {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    headers = fieldnames or list(rows[0])
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=headers,
            extrasaction="ignore",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def require_exact_keys(actual: set[str], expected: set[str], label: str) -> None:
    if actual != expected:
        raise RuntimeError(
            f"{label} mismatch: missing={sorted(expected - actual)}; "
            f"unexpected={sorted(actual - expected)}"
        )


def read_and_validate_inputs() -> tuple[
    dict[str, Any],
    dict[str, dict[str, Any]],
    dict[str, dict[str, Any]],
    pd.DataFrame,
    list[dict[str, Any]],
]:
    config = load_json(CONFIG_PATH)
    catalog_payload = load_json(CATALOG_PATH)
    catalog = {entry["model"]: entry for entry in catalog_payload["models"]}
    pricing_payload = load_json(PRICING_MANIFEST_PATH)
    pricing = {entry["model"]: entry for entry in pricing_payload["rates"]}
    target_models = config["target_models"]
    require_exact_keys(set(catalog), set(target_models), "model catalog")
    require_exact_keys(set(pricing), set(target_models), "pricing manifest")
    if len(pricing_payload["rates"]) != len(pricing):
        raise RuntimeError("Pricing manifest contains duplicate model records")
    record_ids = [entry["record_id"] for entry in pricing_payload["rates"]]
    if len(record_ids) != len(set(record_ids)):
        raise RuntimeError("Pricing manifest contains duplicate record identifiers")

    scores = pd.read_csv(SCORES_PATH)
    score_cells = list(zip(scores["model_display_name"], scores["item_key"]))
    if len(score_cells) != len(set(score_cells)):
        raise RuntimeError("Score panel contains duplicate model--item cells")
    require_exact_keys(set(scores["model_display_name"]), set(target_models), "score-panel models")

    resources: list[dict[str, Any]] = read_csv_rows(RESOURCES_PATH)
    for row in resources:
        for field in TOKEN_NUMERIC_FIELDS:
            row[field] = None if row[field] == "" else float(row[field])
    resource_cells = [(row["model"], row["item_key"]) for row in resources]
    if len(resource_cells) != len(set(resource_cells)):
        raise RuntimeError("Resource panel contains duplicate model--item cells")
    if set(score_cells) != set(resource_cells):
        raise RuntimeError("Score and resource panels do not contain the same model--item cells")

    expected = config["expected_common_items"]
    subject_items = {
        subject: set(scores.loc[scores["subject"] == subject, "item_key"])
        for subject in ("analysis_3", "physics_2")
    }
    all_items = set(scores["item_key"])
    if len(all_items) != expected["overall"]:
        raise RuntimeError(f"Expected {expected['overall']} items, found {len(all_items)}")
    for subject in ("analysis_3", "physics_2"):
        if len(subject_items[subject]) != expected[subject]:
            raise RuntimeError(
                f"Expected {expected[subject]} {subject} items, found {len(subject_items[subject])}"
            )
    expected_cells = len(target_models) * expected["overall"]
    if len(score_cells) != expected_cells:
        raise RuntimeError(f"Expected {expected_cells} balanced cells, found {len(score_cells)}")

    for model in target_models:
        validate_pricing_record(catalog[model], pricing[model])
    for row in resources:
        validate_resource_row(row, catalog[row["model"]], pricing[row["model"]])
    return config, catalog, pricing, scores, resources


def close(left: float | None, right: float | None, tolerance: float = 1e-9) -> bool:
    if left is None or right is None:
        return left is right
    return math.isclose(float(left), float(right), rel_tol=tolerance, abs_tol=tolerance)


def validate_pricing_record(catalog: dict[str, Any], pricing: dict[str, Any]) -> None:
    model = catalog["model"]
    if catalog["id"] != pricing["model_id"]:
        raise RuntimeError(f"Pricing model-id mismatch for {model}")
    if not close(catalog["benchmark_input_usd_per_million"], pricing["input_usd_per_million"]):
        raise RuntimeError(f"Pricing input-rate mismatch for {model}")
    if not close(catalog["benchmark_output_usd_per_million"], pricing["output_usd_per_million"]):
        raise RuntimeError(f"Pricing output-rate mismatch for {model}")
    expected_pointer = (
        "uniaibench/analysis/data/benchmark_pricing_manifest.json#"
        f"{pricing['record_id']}"
    )
    if catalog["benchmark_price_source_kind"] != "public_pricing_manifest_record":
        raise RuntimeError(f"Catalog does not use the public pricing manifest for {model}")
    if catalog["benchmark_price_source"] != expected_pointer:
        raise RuntimeError(f"Catalog pricing pointer mismatch for {model}")


def validate_resource_row(
    row: dict[str, Any],
    catalog: dict[str, Any],
    pricing: dict[str, Any],
) -> None:
    model = row["model"]
    expected_input_rate = float(pricing["input_usd_per_million"])
    expected_output_rate = float(pricing["output_usd_per_million"])
    if not close(row["input_rate_usd_per_million"], expected_input_rate):
        raise RuntimeError(f"Input-rate mismatch for {model} / {row['item_key']}")
    if not close(row["output_rate_usd_per_million"], expected_output_rate):
        raise RuntimeError(f"Output-rate mismatch for {model} / {row['item_key']}")
    if row["price_source_kind"] != catalog["benchmark_price_source_kind"]:
        raise RuntimeError(f"Public price-source-kind mismatch for {model} / {row['item_key']}")
    if row["price_source"] != catalog["benchmark_price_source"]:
        raise RuntimeError(f"Public price-source mismatch for {model} / {row['item_key']}")
    origin = pricing["rate_origin_kind"]
    if origin == "official_provider_documentation":
        if pricing["configuration_snapshot_sha256"] is not None:
            raise RuntimeError(f"Official pricing record has a private fingerprint for {model}")
    elif origin == "private_campaign_configuration_snapshot":
        if not pricing["configuration_snapshot_sha256"]:
            raise RuntimeError(f"Missing private configuration fingerprint for {model}")
    else:
        raise RuntimeError(f"Unknown pricing origin for {model}: {origin!r}")

    input_tokens = row["input_tokens"]
    provider_output = row["provider_output_tokens"]
    reasoning = row["reasoning_tokens_analysis"]
    billed_output = row["billed_output_tokens"]
    provider_total = row["provider_total_tokens"]
    analytical_total = row["analytical_total_tokens"]
    visible = row["visible_output_tokens"]
    combined = row["combined_output_unseparated_tokens"]
    rule = row["token_semantic_rule"]

    if rule == "google_reasoning_separate_and_billed_as_output":
        if reasoning is None or not close(billed_output, provider_output + reasoning):
            raise RuntimeError(f"Invalid Google billable-output arithmetic for {model} / {row['item_key']}")
        if not close(provider_total, input_tokens + provider_output + reasoning):
            raise RuntimeError(f"Invalid Google provider-total arithmetic for {model} / {row['item_key']}")
        if not close(visible, provider_output):
            raise RuntimeError(f"Invalid Google visible-output arithmetic for {model} / {row['item_key']}")
    elif rule in {
        "anthropic_fable_output_includes_unseparated_hidden_thinking",
        "mistral_output_includes_unseparated_hidden_thinking",
    }:
        if visible is not None or not close(combined, provider_output) or not close(billed_output, provider_output):
            raise RuntimeError(f"Invalid unseparated-output arithmetic for {model} / {row['item_key']}")
        if not close(provider_total, input_tokens + provider_output):
            raise RuntimeError(f"Invalid provider-total arithmetic for {model} / {row['item_key']}")
    elif rule == "reasoning_is_subset_of_provider_output":
        if reasoning is None or not close(visible, provider_output - reasoning):
            raise RuntimeError(f"Invalid reasoning/output split for {model} / {row['item_key']}")
        if not close(billed_output, provider_output) or not close(provider_total, input_tokens + provider_output):
            raise RuntimeError(f"Invalid billable/provider total for {model} / {row['item_key']}")
    else:
        raise RuntimeError(f"Unknown token semantic rule: {rule!r}")
    if not close(analytical_total, input_tokens + billed_output):
        raise RuntimeError(f"Invalid analytical total for {model} / {row['item_key']}")

    reconstructed = (
        input_tokens * expected_input_rate + billed_output * expected_output_rate
    ) / 1_000_000
    if not close(row["cost_reconstructed_usd"], reconstructed):
        raise RuntimeError(f"Invalid reconstructed cost for {model} / {row['item_key']}")
    selected = row["cost_provider_reported_usd"]
    if selected is None:
        selected = reconstructed
    if not close(row["cost_selected_usd"], selected):
        raise RuntimeError(f"Invalid selected cost for {model} / {row['item_key']}")


def round_for_csv(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    numeric_columns = result.select_dtypes(include=["number"]).columns
    result[numeric_columns] = result[numeric_columns].round(8)
    return result


def scope_subset(scores: pd.DataFrame, scope: str) -> pd.DataFrame:
    subject = SCOPE_DEFINITIONS[scope]["subject"]
    return scores.copy() if subject is None else scores[scores["subject"] == subject].copy()


def bootstrap_ranking_ci(values: np.ndarray, config: dict[str, Any], seed_offset: int) -> tuple[float, float]:
    if len(values) == 0:
        return math.nan, math.nan
    if len(values) == 1:
        return float(values[0]), float(values[0])
    ranking = config["ranking"]
    rng = np.random.default_rng(ranking["bootstrap_seed"] + seed_offset)
    indices = rng.integers(0, len(values), size=(ranking["bootstrap_resamples"], len(values)))
    means = values[indices].mean(axis=1)
    alpha = (1.0 - ranking["confidence_level"]) / 2.0
    low, high = np.quantile(means, [alpha, 1.0 - alpha])
    return float(low), float(high)


def build_ranking(scores: pd.DataFrame, config: dict[str, Any], scope: str) -> pd.DataFrame:
    subset = scope_subset(scores, scope)
    inventory_items = subset["item_key"].nunique()
    records: list[dict[str, Any]] = []
    ranking_config = config["ranking"]
    dimensions = config["dimensions"]
    for model_index, model in enumerate(config["target_models"]):
        group = subset[subset["model_display_name"] == model].copy()
        if group.empty:
            raise RuntimeError(f"No score rows for model={model}, scope={scope}")
        values = group["item_accuracy"].astype(float).to_numpy()
        low, high = bootstrap_ranking_ci(
            values,
            config,
            seed_offset=1000 * list(SCOPE_DEFINITIONS).index(scope) + model_index,
        )
        repeated = group[group["n_responses"] >= 2]
        record: dict[str, Any] = {
            "model": model,
            "provider": group["provider"].iloc[0],
            "n_items": int(len(group)),
            "n_responses": int(group["n_responses"].sum()),
            "scope_inventory_items": int(inventory_items),
            "coverage_rate": float(len(group) / inventory_items),
            "accuracy_mean": float(np.mean(values)),
            "accuracy_ci95_low": low,
            "accuracy_ci95_high": high,
            "accuracy_median": float(np.median(values)),
            "accuracy_sd_items": float(np.std(values, ddof=1)) if len(values) > 1 else math.nan,
            "accuracy_iqr": float(np.quantile(values, 0.75) - np.quantile(values, 0.25)) if len(values) > 1 else 0.0,
            "accuracy_min": float(np.min(values)),
            "accuracy_max": float(np.max(values)),
            "perfect_item_rate": float(
                np.mean(
                    np.isclose(
                        values,
                        ranking_config["perfect_score_percent"],
                        atol=ranking_config["score_tolerance"],
                    )
                )
            ),
            "success_item_rate": float(np.mean(values >= ranking_config["success_threshold_percent"])),
            "repeated_cells": int(len(repeated)),
            "repeatability_sd_mean": float(repeated["response_sd"].mean()) if len(repeated) else math.nan,
            "repeatability_sd_median": float(repeated["response_sd"].median()) if len(repeated) else math.nan,
        }
        for dimension in dimensions:
            dimension_values = group[f"dimension_{dimension}"].astype(float).to_numpy()
            dimension_values = dimension_values[~np.isnan(dimension_values)]
            record[f"dimension_{dimension}"] = (
                float(np.mean(dimension_values)) if len(dimension_values) else math.nan
            )
        records.append(record)

    frame = pd.DataFrame.from_records(records).sort_values(
        ["accuracy_mean", "perfect_item_rate", "success_item_rate", "accuracy_sd_items", "model"],
        ascending=[False, False, False, True, True],
        kind="mergesort",
    ).reset_index(drop=True)
    ranks: list[int] = []
    previous_key: tuple[float, float, float, float] | None = None
    previous_rank = 0
    for index, row in frame.iterrows():
        key = (
            round(float(row["accuracy_mean"]), 10),
            round(float(row["perfect_item_rate"]), 10),
            round(float(row["success_item_rate"]), 10),
            round(float(row["accuracy_sd_items"]), 10),
        )
        if previous_key is not None and key == previous_key:
            ranks.append(previous_rank)
        else:
            previous_rank = index + 1
            ranks.append(previous_rank)
            previous_key = key
    frame.insert(0, "rank", ranks)
    frame.insert(1, "ranking_type", "matched_common_items")
    frame.insert(2, "scope", scope)
    return frame


def build_coverage(scores: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    for scope in SCOPE_DEFINITIONS:
        subset = scope_subset(scores, scope)
        inventory = subset["item_key"].nunique()
        for model in config["target_models"]:
            group = subset[subset["model_display_name"] == model]
            records.append(
                {
                    "scope": scope,
                    "model": model,
                    "available_items": int(group["item_key"].nunique()),
                    "inventory_items": int(inventory),
                    "coverage_rate": float(group["item_key"].nunique() / inventory),
                    "common_items_used_primary": int(inventory),
                    "responses": int(group["n_responses"].sum()),
                    "repeated_cells": int((group["n_responses"] >= 2).sum()),
                }
            )
    return pd.DataFrame.from_records(records)


def percentile(values: Iterable[float], probability: float) -> float:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        return math.nan
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def bootstrap_token_ci(values: list[float], seed: int, resamples: int) -> tuple[float, float]:
    rng = random.Random(seed)
    count = len(values)
    means = [
        sum(values[rng.randrange(count)] for _ in range(count)) / count
        for _ in range(resamples)
    ]
    return percentile(means, 0.025), percentile(means, 0.975)


def sum_if_complete(values: list[float | None]) -> float | None:
    return sum(float(value) for value in values if value is not None) if all(value is not None for value in values) else None


def build_token_summaries(resources: list[dict[str, Any]], config: dict[str, Any]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in resources:
        grouped[row["model"]].append(row)
    expected_items = config["expected_common_items"]["overall"]
    token_config = config["token_cost"]
    summaries: list[dict[str, Any]] = []
    for model_index, model in enumerate(config["target_models"]):
        rows = grouped[model]
        if len(rows) != expected_items:
            raise RuntimeError(f"Unexpected resource-row count for {model}: {len(rows)}")
        costs = [float(row["cost_selected_usd"]) for row in rows]
        totals = [float(row["analytical_total_tokens"]) for row in rows]
        billed_outputs = [float(row["billed_output_tokens"]) for row in rows]
        cost_ci = bootstrap_token_ci(costs, token_config["bootstrap_seed"] + model_index, token_config["bootstrap_resamples"])
        token_ci = bootstrap_token_ci(totals, token_config["bootstrap_seed"] + 1000 + model_index, token_config["bootstrap_resamples"])
        reasoning_values = [row["reasoning_tokens_analysis"] for row in rows]
        visible_values = [row["visible_output_tokens"] for row in rows]
        combined_values = [row["combined_output_unseparated_tokens"] for row in rows]
        reasoning_total = sum_if_complete(reasoning_values)
        provider = rows[0]["provider"]
        summary = {
            "model": model,
            "provider": provider,
            "mode": rows[0]["mode"],
            "n_exercises": len(rows),
            "input_tokens_total": sum(row["input_tokens"] for row in rows),
            "input_tokens_mean": statistics.fmean(row["input_tokens"] for row in rows),
            "input_tokens_median": statistics.median(row["input_tokens"] for row in rows),
            "visible_output_tokens_total": sum_if_complete(visible_values),
            "visible_output_tokens_mean": statistics.fmean(float(value) for value in visible_values if value is not None) if all(value is not None for value in visible_values) else None,
            "reasoning_tokens_total": reasoning_total,
            "reasoning_tokens_mean": statistics.fmean(float(value) for value in reasoning_values if value is not None) if reasoning_total is not None else None,
            "reasoning_coverage": sum(value is not None for value in reasoning_values),
            "combined_output_unseparated_tokens_total": sum(float(value) for value in combined_values if value is not None),
            "provider_output_tokens_total": sum(row["provider_output_tokens"] for row in rows),
            "billed_output_tokens_total": sum(row["billed_output_tokens"] for row in rows),
            "billed_output_tokens_mean": statistics.fmean(billed_outputs),
            "billed_output_tokens_median": statistics.median(billed_outputs),
            "analytical_total_tokens_total": sum(totals),
            "analytical_total_tokens_mean": statistics.fmean(totals),
            "analytical_total_tokens_median": statistics.median(totals),
            "analytical_total_tokens_ci95_low": token_ci[0],
            "analytical_total_tokens_ci95_high": token_ci[1],
            "reasoning_share_billed_output": reasoning_total / sum(row["billed_output_tokens"] for row in rows) if reasoning_total is not None and sum(row["billed_output_tokens"] for row in rows) else None,
            "cost_total_usd": sum(costs),
            "cost_mean_usd": statistics.fmean(costs),
            "cost_median_usd": statistics.median(costs),
            "cost_q1_usd": percentile(costs, 0.25),
            "cost_q3_usd": percentile(costs, 0.75),
            "cost_min_usd": min(costs),
            "cost_max_usd": max(costs),
            "cost_mean_ci95_low_usd": cost_ci[0],
            "cost_mean_ci95_high_usd": cost_ci[1],
            "provider_reported_cost_rows": sum(row["cost_source"] == "provider_reported" for row in rows),
            "reconstructed_cost_rows": sum(row["cost_source"] != "provider_reported" for row in rows),
            "retry_rows": sum(row["retry_count"] > 0 for row in rows),
            "elapsed_seconds_total": sum(float(row["elapsed_seconds"]) for row in rows),
            "elapsed_seconds_median": statistics.median(float(row["elapsed_seconds"]) for row in rows),
            "input_rate_usd_per_million": rows[0]["input_rate_usd_per_million"],
            "output_rate_usd_per_million": rows[0]["output_rate_usd_per_million"],
            "price_source_kind": rows[0]["price_source_kind"],
            "price_source": rows[0]["price_source"],
            "provider_color": token_config["provider_colors"][provider],
        }
        summaries.append(summary)
    for rank, row in enumerate(sorted(summaries, key=lambda value: (value["cost_total_usd"], value["model"])), start=1):
        row["cost_rank_low_to_high"] = rank
    for rank, row in enumerate(sorted(summaries, key=lambda value: (value["analytical_total_tokens_total"], value["model"])), start=1):
        row["token_rank_low_to_high"] = rank
    summaries.sort(key=lambda value: value["cost_rank_low_to_high"])
    return summaries


def build_quality(resources: list[dict[str, Any]], summaries: list[dict[str, Any]], config: dict[str, Any]) -> list[dict[str, Any]]:
    summary_by_model = {row["model"]: row for row in summaries}
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in resources:
        grouped[row["model"]].append(row)
    prompt_attestation = config["upstream_attestations"]["prompt_hash_consistent_within_each_item"]
    output: list[dict[str, Any]] = []
    for model in sorted(grouped):
        rows = grouped[model]
        output.append(
            {
                "model": model,
                "provider": rows[0]["provider"],
                "rows": len(rows),
                "input_complete": sum(row["input_tokens"] is not None for row in rows),
                "provider_output_complete": sum(row["provider_output_tokens"] is not None for row in rows),
                "visible_output_complete": sum(row["visible_output_tokens"] is not None for row in rows),
                "reasoning_reported_rows": sum(row["reasoning_tokens_reported"] is not None for row in rows),
                "reasoning_analysis_rows": sum(row["reasoning_tokens_analysis"] is not None for row in rows),
                "provider_total_complete": sum(row["provider_total_tokens"] is not None for row in rows),
                "provider_reported_cost_rows": summary_by_model[model]["provider_reported_cost_rows"],
                "reconstructed_cost_rows": summary_by_model[model]["reconstructed_cost_rows"],
                "retry_rows": summary_by_model[model]["retry_rows"],
                "prompt_hash_consistent": prompt_attestation,
                "token_arithmetic_valid": all(resource_arithmetic_valid(row) for row in rows),
                "price_source_kind": rows[0]["price_source_kind"],
                "cost_limitation": "provider output combines visible text and hidden thinking" if model == "Claude Fable 5" else "final response only for rows with retry" if any(row["retry_count"] for row in rows) else "none",
            }
        )
    return output


def resource_arithmetic_valid(row: dict[str, Any]) -> bool:
    try:
        # The catalog/rate checks have already run. Re-check the identities here
        # so this table field is computed from the public panel, not hard-coded.
        input_tokens = row["input_tokens"]
        billed = row["billed_output_tokens"]
        return close(row["analytical_total_tokens"], input_tokens + billed)
    except (TypeError, ValueError):
        return False


def build_price_rows(
    catalog: dict[str, dict[str, Any]],
    pricing: dict[str, dict[str, Any]],
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    return [
        {
            "model": model,
            "input_usd_per_million": catalog[model]["benchmark_input_usd_per_million"],
            "output_usd_per_million": catalog[model]["benchmark_output_usd_per_million"],
            "source_kind": catalog[model]["benchmark_price_source_kind"],
            "source": catalog[model]["benchmark_price_source"],
            "note": pricing[model]["note"],
        }
        for model in config["target_models"]
    ]


def build_deepseek_comparison(resources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_cell = {(row["model"], row["item_key"]): row for row in resources}
    output: list[dict[str, Any]] = []
    for key in sorted({row["item_key"] for row in resources}):
        thinking = by_cell[("DeepSeek V4 Flash", key)]
        no_thinking = by_cell[("DeepSeek V4 Flash (no thinking)", key)]
        output.append(
            {
                "item_key": key,
                "item_label": thinking["item_label"],
                "subject": thinking["subject"],
                "input_tokens_thinking": thinking["input_tokens"],
                "input_tokens_no_thinking": no_thinking["input_tokens"],
                "visible_output_tokens_thinking": thinking["visible_output_tokens"],
                "visible_output_tokens_no_thinking": no_thinking["visible_output_tokens"],
                "reasoning_tokens_thinking": thinking["reasoning_tokens_analysis"],
                "reasoning_tokens_no_thinking": no_thinking["reasoning_tokens_analysis"],
                "total_tokens_thinking": thinking["analytical_total_tokens"],
                "total_tokens_no_thinking": no_thinking["analytical_total_tokens"],
                "delta_total_tokens": thinking["analytical_total_tokens"] - no_thinking["analytical_total_tokens"],
                "cost_usd_thinking": thinking["cost_selected_usd"],
                "cost_usd_no_thinking": no_thinking["cost_selected_usd"],
                "delta_cost_usd": thinking["cost_selected_usd"] - no_thinking["cost_selected_usd"],
                "elapsed_seconds_thinking": thinking["elapsed_seconds"],
                "elapsed_seconds_no_thinking": no_thinking["elapsed_seconds"],
            }
        )
    return output


def generate_tables(destination: Path) -> None:
    config, catalog, pricing, scores, resources = read_and_validate_inputs()
    dimensions = config["dimensions"]
    for scope, definition in SCOPE_DEFINITIONS.items():
        ranking = round_for_csv(build_ranking(scores, config, scope))
        ranking.to_csv(destination / definition["ranking"], index=False)
        profile_columns = ["rank", "model", *[f"dimension_{dimension}" for dimension in dimensions]]
        ranking[profile_columns].to_csv(destination / definition["profile"], index=False)
    round_for_csv(build_coverage(scores, config)).to_csv(destination / "model_coverage.csv", index=False)

    summaries = build_token_summaries(resources, config)
    write_csv(destination / "model_token_costs_17x60.csv", summaries)
    write_csv(destination / "quality_token_cost_17x60.csv", build_quality(resources, summaries, config))
    pd.DataFrame.from_records(build_price_rows(catalog, pricing, config)).to_csv(
        destination / "token_cost_rates.csv", index=False
    )
    write_csv(destination / "deepseek_flash_thinking_vs_no_thinking.csv", build_deepseek_comparison(resources))


def compare_tables(generated: Path) -> list[str]:
    errors: list[str] = []
    tracked = {path.name for path in TABLE_ROOT.glob("*.csv")}
    if tracked != EXPECTED_TABLES:
        errors.append(
            f"tracked table set mismatch: missing={sorted(EXPECTED_TABLES - tracked)}; "
            f"unexpected={sorted(tracked - EXPECTED_TABLES)}"
        )
    for name in sorted(EXPECTED_TABLES):
        expected_path = TABLE_ROOT / name
        generated_path = generated / name
        if not expected_path.is_file():
            errors.append(f"missing tracked table: {name}")
        elif not generated_path.is_file():
            errors.append(f"generator did not produce: {name}")
        elif expected_path.read_bytes() != generated_path.read_bytes():
            errors.append(f"generated bytes differ: {name}")
    return errors


def install_tables(generated: Path) -> None:
    TABLE_ROOT.mkdir(parents=True, exist_ok=True)
    for name in sorted(EXPECTED_TABLES):
        source = generated / name
        temporary = TABLE_ROOT / f".{name}.tmp"
        shutil.copyfile(source, temporary)
        os.replace(temporary, TABLE_ROOT / name)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="compare regenerated tables byte-for-byte with the release (default)")
    mode.add_argument("--write", action="store_true", help="atomically replace the released tables with regenerated files")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    with tempfile.TemporaryDirectory(prefix="uniaibench-public-tables-") as temporary:
        generated = Path(temporary)
        generate_tables(generated)
        if args.write:
            install_tables(generated)
            print(f"OK: rebuilt {len(EXPECTED_TABLES)} public tables from sanitized inputs")
            return 0
        errors = compare_tables(generated)
        if errors:
            for error in errors:
                print(f"ERROR: {error}")
            return 1
        print(f"OK: all {len(EXPECTED_TABLES)} public tables are byte-for-byte reproducible")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
