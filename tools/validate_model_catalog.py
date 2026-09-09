#!/usr/bin/env python3
"""Validate canonical model metadata against the published analysis tables."""

from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "analysis" / "data" / "model_catalog.json"
RANKING = ROOT / "analysis" / "tables" / "classifica_principale_complessiva.csv"
RATES = ROOT / "analysis" / "tables" / "tariffe_token_costi.csv"
REQUIRED_FIELDS = {
    "provider", "model", "id", "release", "release_note", "parameters",
    "weights", "architecture", "reasoning", "context", "output", "modalities",
    "cutoff", "model_url", "provider_display", "api_display", "api_url",
    "public_release_display", "open_weights_display", "benchmark_reasoning_display",
    "latest_verified_rate", "benchmark_rate", "pricing_source_label",
    "pricing_source_url", "benchmark_input_usd_per_million",
    "benchmark_output_usd_per_million", "benchmark_price_source_kind",
    "benchmark_price_source",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def main() -> int:
    payload = json.loads(CATALOG.read_text(encoding="utf-8"))
    models = payload.get("models")
    if not isinstance(models, list) or len(models) != 14:
        raise ValueError("model_catalog.json must contain exactly 14 configurations")

    names = [model.get("model") for model in models]
    if len(set(names)) != len(names):
        raise ValueError("model_catalog.json contains duplicate model names")
    for model in models:
        missing = REQUIRED_FIELDS - model.keys()
        if missing:
            raise ValueError(f"{model.get('model', '<unknown>')}: missing fields {sorted(missing)}")
        for field in ("model_url", "api_url", "pricing_source_url"):
            if not str(model[field]).startswith("https://"):
                raise ValueError(f"{model['model']}: {field} must use HTTPS")

    ranking_names = {row["model"] for row in read_csv(RANKING)}
    if set(names) != ranking_names:
        raise ValueError("model catalog and overall ranking contain different model sets")

    rates = {row["model"]: row for row in read_csv(RATES)}
    if set(names) != set(rates):
        raise ValueError("model catalog and frozen-rate table contain different model sets")
    for model in models:
        rate = rates[model["model"]]
        expected = (float(rate["input_usd_per_million"]), float(rate["output_usd_per_million"]))
        actual = (
            float(model["benchmark_input_usd_per_million"]),
            float(model["benchmark_output_usd_per_million"]),
        )
        if actual != expected:
            raise ValueError(f"{model['model']}: frozen price differs from analysis table")

    print("OK: 14 canonical model records match ranking and frozen pricing tables")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
