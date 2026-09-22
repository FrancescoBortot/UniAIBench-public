#!/usr/bin/env python3
"""Generate the website's public 17x60 chart data from sanitized CSVs.

The generator reads only the aggregate artifacts distributed in
``uniaibench/analysis/`` and writes TypeScript data modules to
``uniaibench/analysis/site_exports/``. A website
deployment may copy those modules into its own source tree.  The script never
reads source exercises, solutions, responses, judgments, identity maps, or
provider credentials.
"""

from __future__ import annotations

import csv
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path


ANALYSIS_DIR = Path(__file__).resolve().parents[1]
WEBSITE_APP = ANALYSIS_DIR / "site_exports"

CORRECTNESS_TABLES = {
    "overall": ANALYSIS_DIR / "tables" / "main_ranking_overall.csv",
    "analysis": ANALYSIS_DIR / "tables" / "main_ranking_analysis_iii.csv",
    "physics": ANALYSIS_DIR / "tables" / "main_ranking_physics_ii.csv",
}
TOKEN_SUMMARY = ANALYSIS_DIR / "tables" / "model_token_costs_17x60.csv"
MODEL_ITEMS = ANALYSIS_DIR / "data" / "model_item_resources.csv"
CORRECTNESS_ITEMS = ANALYSIS_DIR / "data" / "model_item_scores.csv"
MODEL_CATALOG = ANALYSIS_DIR / "data" / "model_catalog.json"
TIME_SUMMARY = ANALYSIS_DIR / "grafici_tempo_risposta_focus" / "tables" / "tempi_modelli_17x60.csv"
NORMALIZED_TIMES = ANALYSIS_DIR / "grafici_tempo_risposta_focus" / "tables" / "tempi_normalizzati_modello_esercizio_17x60.csv"

PROVIDERS = {
    "openai": "OpenAI",
    "anthropic": "Anthropic",
    "google": "Google",
    "deepseek": "DeepSeek",
    "xai": "xAI",
    "mistral": "Mistral",
}
SUBJECTS = {"analysis_3": "Analysis III", "physics_2": "Physics II"}
SUBJECT_ORDER = {"analysis_3": 0, "physics_2": 1}
SESSION_ORDER = {
    "primoapp": 10,
    "primoapp_tema_a": 10,
    "primoapp_tema_b": 11,
    "secondoapp": 20,
    "secondoapp_tema_a": 20,
    "secondoapp_tema_b": 21,
    "terzoapp": 30,
    "quartoapp": 40,
    "quintoapp": 50,
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def number(row: dict[str, str], key: str, default: float = 0.0) -> float:
    value = row.get(key, "")
    return float(value) if value not in (None, "") else default


def integer(value: float) -> int:
    return int(round(value))


def item_sort(row: dict[str, str]) -> tuple[int, int, int, str, int]:
    return (
        SUBJECT_ORDER[row["subject"]],
        int(row["year"]),
        SESSION_ORDER.get(row["session"], 999),
        row["session"],
        int(float(row["exercise"])),
    )


def average_ranks(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=values.__getitem__)
    ranks = [0.0] * len(values)
    start = 0
    while start < len(order):
        end = start + 1
        while end < len(order) and values[order[end]] == values[order[start]]:
            end += 1
        rank = (start + 1 + end) / 2.0
        for index in order[start:end]:
            ranks[index] = rank
        start = end
    return ranks


def pearson(xs: list[float], ys: list[float]) -> float:
    mean_x = statistics.mean(xs)
    mean_y = statistics.mean(ys)
    numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    denominator = math.sqrt(sum((x - mean_x) ** 2 for x in xs) * sum((y - mean_y) ** 2 for y in ys))
    return numerator / denominator


def correlation_diagnostics(rows: list[dict[str, float | str]]) -> dict[str, float]:
    times = [float(row["median"]) for row in rows]
    accuracies = [float(row["accuracy"]) for row in rows]
    minimum = min(times)
    deficits = [100.0 - value for value in accuracies]
    best: tuple[float, float, float] | None = None
    for index in range(20001):
        exponent = 0.01 + index * (5.0 - 0.01) / 20000
        weights = [(value / minimum) ** (-exponent) for value in times]
        amplitude = sum(w * d for w, d in zip(weights, deficits)) / sum(w * w for w in weights)
        predictions = [100.0 - amplitude * weight for weight in weights]
        sse = sum((actual - predicted) ** 2 for actual, predicted in zip(accuracies, predictions))
        if best is None or sse < best[0]:
            best = (sse, amplitude, exponent)
    assert best is not None
    sse, amplitude, exponent = best
    total_variation = sum((value - statistics.mean(accuracies)) ** 2 for value in accuracies)
    return {
        "amplitude": amplitude,
        "exponent": exponent,
        "minimumTime": minimum,
        "pearson": pearson([math.log10(value) for value in times], accuracies),
        "spearman": pearson(average_ranks(times), average_ranks(accuracies)),
        "rSquared": 1.0 - sse / total_variation,
    }


def ts_export(name: str, value: object, annotation: str | None = None) -> str:
    suffix = f" as {annotation}" if annotation else ""
    return f"export const {name} = {json.dumps(value, ensure_ascii=False, indent=2)}{suffix};\n"


def build() -> None:
    WEBSITE_APP.mkdir(parents=True, exist_ok=True)
    correctness = {scope: read_csv(path) for scope, path in CORRECTNESS_TABLES.items()}
    model_items = read_csv(MODEL_ITEMS)
    correctness_items = read_csv(CORRECTNESS_ITEMS)
    token_summary = read_csv(TOKEN_SUMMARY)
    time_summary = read_csv(TIME_SUMMARY)
    normalized_times = read_csv(NORMALIZED_TIMES)
    model_catalog = json.loads(MODEL_CATALOG.read_text(encoding="utf-8"))
    catalog_models = model_catalog["models"]

    if any(len(rows) != 17 for rows in correctness.values()):
        raise ValueError("Expected 17 models in every correctness scope")
    if len(model_items) != 1020 or len(correctness_items) != 1020 or len(normalized_times) != 1020:
        raise ValueError("Expected exactly 1020 balanced model-item cells")

    cell_groups: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in model_items:
        cell_groups[(row["model"], row["subject"])].append(row)

    correctness_by_scope = {
        scope: {row["model"]: row for row in rows}
        for scope, rows in correctness.items()
    }
    model_order = [row["model"] for row in correctness["overall"]]
    if {row["model"] for row in catalog_models} != set(model_order):
        raise ValueError("Canonical model catalog does not match the benchmark model panel")
    models = []
    for model in model_order:
        overall_row = correctness_by_scope["overall"][model]
        metrics = {}
        for scope, subject in (("overall", None), ("analysis", "analysis_3"), ("physics", "physics_2")):
            ranking = correctness_by_scope[scope][model]
            cells = model_items if subject is None else cell_groups[(model, subject)]
            if subject is None:
                cells = [row for row in model_items if row["model"] == model]
            metrics[scope] = {
                "accuracy": number(ranking, "accuracy_mean"),
                "reliability": number(ranking, "success_item_rate") * 100.0,
                "sample": integer(number(ranking, "n_items")),
                "ciLow": number(ranking, "accuracy_ci95_low"),
                "ciHigh": number(ranking, "accuracy_ci95_high"),
                "cost": statistics.mean(number(row, "cost_selected_usd") for row in cells),
                "latency": statistics.median(number(row, "elapsed_seconds") for row in cells),
            }
        models.append(
            {
                "name": model,
                "provider": PROVIDERS[overall_row["provider"]],
                "metrics": metrics,
            }
        )

    dimension_profiles = {
        model: [number(correctness_by_scope["overall"][model], f"dimension_T{index}") for index in range(1, 9)]
        for model in model_order
    }

    resource_profiles = {}
    for row in token_summary:
        resource_profiles[row["model"]] = {
            "costLow": number(row, "cost_mean_ci95_low_usd"),
            "costHigh": number(row, "cost_mean_ci95_high_usd"),
            "costTotal": number(row, "cost_total_usd"),
            "input": integer(number(row, "input_tokens_total")),
            "visible": integer(number(row, "visible_output_tokens_total")),
            "reasoning": integer(number(row, "reasoning_tokens_total")),
            "unseparated": integer(number(row, "combined_output_unseparated_tokens_total")),
            "total": integer(number(row, "analytical_total_tokens_total")),
        }

    time_profiles = {}
    diagnostics_rows = []
    for row in time_summary:
        model = row["model"]
        profile = {
            "mean": number(row, "mean_seconds"),
            "q1": number(row, "q1_seconds"),
            "q3": number(row, "q3_seconds"),
            "p90": number(row, "p90_seconds"),
            "total": number(row, "total_seconds"),
            "tokens": number(row, "analytical_tokens_mean"),
            "intensity": number(row, "effective_seconds_per_1k_tokens"),
        }
        time_profiles[model] = profile
        diagnostics_rows.append({"model": model, "median": number(row, "median_seconds"), "accuracy": number(row, "accuracy_mean")})
    correlation = correlation_diagnostics(diagnostics_rows)

    unique_items = {}
    for row in normalized_times:
        unique_items[row["item_key"]] = row
    item_rows = sorted(unique_items.values(), key=item_sort)
    item_keys = [row["item_key"] for row in item_rows]
    item_index = {key: index for index, key in enumerate(item_keys)}
    time_items = [
        {
            "id": row["item_key"],
            "label": row["item_label"],
            "exercise": f"E{int(float(row['exercise']))}",
            "subject": row["subject"],
            "subjectLabel": SUBJECTS[row["subject"]],
            "group": row["item_label"].rsplit("-", 1)[0],
        }
        for row in item_rows
    ]

    time_groups = []
    for subject in ("analysis_3", "physics_2"):
        subject_items = [item for item in time_items if item["subject"] == subject]
        start = 0
        while start < len(subject_items):
            group = subject_items[start]["group"]
            end = start + 1
            while end < len(subject_items) and subject_items[end]["group"] == group:
                end += 1
            time_groups.append({"subject": subject, "label": group.replace("-", " "), "start": start, "span": end - start})
            start = end

    ratio_lookup = {(row["model"], row["item_key"]): number(row, "time_ratio_to_item_median") for row in normalized_times}
    retry_cells = []
    time_ratios = {}
    for model in model_order:
        time_ratios[model] = [ratio_lookup[(model, key)] for key in item_keys]
        for row in normalized_times:
            if row["model"] == model and number(row, "retry_count") > 0:
                retry_cells.append(f"{model}-{item_index[row['item_key']]}")

    score_lookup = {(row["model_display_name"], row["item_key"]): number(row, "item_accuracy") for row in correctness_items}
    cell_lookup = {(row["model"], row["item_key"]): row for row in model_items}
    exercise_profiles = {}
    for model in model_order:
        exercises = []
        for item in time_items:
            row = cell_lookup[(model, item["id"])]
            exercises.append(
                {
                    "id": item["id"],
                    "label": item["label"],
                    "subject": item["subjectLabel"],
                    "accuracy": score_lookup[(model, item["id"])],
                    "latency": number(row, "elapsed_seconds"),
                    "cost": number(row, "cost_selected_usd"),
                    "tokens": integer(number(row, "analytical_total_tokens")),
                    "retries": integer(number(row, "retry_count")),
                }
            )
        exercise_profiles[model] = exercises

    data_lines = [
        "// Generated by uniaibench/analysis/scripts/build_website_benchmark_data.py.\n",
        "// Do not edit numerical values by hand.\n\n",
        'export type Provider = "OpenAI" | "Anthropic" | "Google" | "DeepSeek" | "xAI" | "Mistral";\n',
        'export type SubjectKey = "overall" | "analysis" | "physics";\n',
        "export type ModelMetrics = { accuracy: number; cost: number; latency: number; reliability: number; sample: number; ciLow: number; ciHigh: number };\n",
        "export type Model = { name: string; provider: Provider; metrics: Record<SubjectKey, ModelMetrics> };\n",
        'export type ActiveModel = Omit<Model, "metrics"> & ModelMetrics;\n',
        "export type ResourceProfile = { costLow: number; costHigh: number; costTotal: number; input: number; visible: number; reasoning: number; unseparated: number; total: number };\n",
        "export type TimeProfile = { mean: number; q1: number; q3: number; p90: number; total: number; tokens: number; intensity: number };\n\n",
        ts_export("benchmarkSnapshot", {"date": "16 September 2026", "models": 17, "exercises": 60, "analysisExercises": 33, "physicsExercises": 27, "cells": 1020}),
        ts_export("models", models, "Model[]"),
        ts_export("dimensionProfiles", dimension_profiles, "Record<string, number[]>"),
        ts_export("resourceProfiles", resource_profiles, "Record<string, ResourceProfile>"),
        ts_export("timeProfiles", time_profiles, "Record<string, TimeProfile>"),
        ts_export("timeItems", time_items),
        ts_export("timeGroups", time_groups),
        ts_export("timeRatios", time_ratios, "Record<string, number[]>"),
        ts_export("retryCellIds", sorted(set(retry_cells)), "string[]"),
        ts_export("correlationDiagnostics", correlation),
    ]
    (WEBSITE_APP / "benchmarkData.ts").write_text("".join(data_lines), encoding="utf-8")

    profile_source = (
        "// Generated by uniaibench/analysis/scripts/build_website_benchmark_data.py.\n"
        "export type ExercisePerformance = { id: string; label: string; subject: string; accuracy: number; latency: number; cost: number; tokens: number; retries: number };\n"
        + ts_export("exerciseProfiles", exercise_profiles, "Record<string, ExercisePerformance[]>")
    )
    (WEBSITE_APP / "exerciseProfiles.ts").write_text(profile_source, encoding="utf-8")

    catalog_source = (
        "// Generated by uniaibench/analysis/scripts/build_website_benchmark_data.py.\n"
        "// Canonical source: uniaibench/analysis/data/model_catalog.json.\n"
        + ts_export("modelCatalog", model_catalog)
    )
    (WEBSITE_APP / "modelCatalog.ts").write_text(catalog_source, encoding="utf-8")

    print(json.dumps({
        "models": len(models),
        "items": len(time_items),
        "cells": len(model_items),
        "exercise_profile_rows": sum(len(rows) for rows in exercise_profiles.values()),
        "retry_cells": len(set(retry_cells)),
        "correlation": correlation,
    }))


if __name__ == "__main__":
    build()
