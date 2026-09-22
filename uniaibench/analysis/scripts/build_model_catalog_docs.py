#!/usr/bin/env python3
"""Generate the public model and pricing catalog from its canonical JSON."""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / "analysis" / "data" / "model_catalog.json"
OUTPUT = ROOT / "profile" / "evaluated-models.md"
MONTHS = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)


def display_date(value: str) -> str:
    parsed = date.fromisoformat(value)
    return f"{parsed.day} {MONTHS[parsed.month - 1]} {parsed.year}"


def table_row(values: list[object]) -> str:
    return "| " + " | ".join(str(value) for value in values) + " |"


def build(*, write: bool = True) -> str:
    payload = json.loads(CATALOG.read_text(encoding="utf-8"))
    models = payload["models"]
    latest_date = display_date(payload["latest_price_verification_date"])
    benchmark_date = display_date(payload["benchmark_snapshot_date"])

    lines = [
        "# Evaluated models and pricing", "",
        "This catalog is generated from the versioned",
        "[`analysis/data/model_catalog.json`](../analysis/data/model_catalog.json)",
        "record used by the paper appendix and website export. It identifies the",
        "**17 model--mode configurations** in the matched 60-item panel and separates two price concepts:", "",
        f"- **latest verified API rate:** the standard first-party rate manually checked on **{latest_date}**;",
        f"- **benchmark rate:** the frozen rate used to estimate study costs on **{benchmark_date}**.", "",
        "Prices are in USD per one million tokens and show input before output. They",
        "are not live prices. Cached input, batch, regional, tax, tool, and",
        "priority-processing charges are omitted unless the exception materially changes the comparison.", "",
        "Frozen-rate provenance is normalized in the public",
        "[`benchmark_pricing_manifest.json`](../analysis/data/benchmark_pricing_manifest.json).",
        "Rates taken from withheld operational configurations are bound to those exact",
        "snapshots by SHA-256, without publishing their filenames, paths, or contents.",
        "Each record also keeps an official provider page as a public reference.", "",
        "## Identity and benchmark setup", "",
        "| Model | Provider | Exact API identifier / configuration | Public release | Open weights | Benchmark reasoning mode |",
        "|---|---|---|---|:---:|---|",
    ]
    for model in models:
        lines.append(table_row([
            f"[{model['model']}]({model['model_url']})", model["provider_display"],
            f"[`{model['api_display']}`]({model['api_url']})", model["public_release_display"],
            model["open_weights_display"], model["benchmark_reasoning_display"],
        ]))

    lines.extend(["", "The two DeepSeek V4 Flash rows are distinct benchmark configurations of the same model weights.", "",
        "## Technical specifications", "",
        "| Model | Parameters | Architecture / model class | Context | Maximum output | Knowledge / training cutoff |",
        "|---|---|---|---:|---:|---|",
    ])
    for model in models:
        lines.append(table_row([
            model["model"], model["parameters"], model["architecture"],
            model["context"], model["output"], model["cutoff"],
        ]))

    lines.extend(["", "## Pricing", "",
        "| Model | Latest verified standard API rate | Benchmark rate | Official pricing source |",
        "|---|---|---|---|",
    ])
    for model in models:
        lines.append(table_row([
            model["model"], model["latest_verified_rate"], model["benchmark_rate"],
            f"[{model['pricing_source_label']}]({model['pricing_source_url']})",
        ]))

    lines.extend(["",
        "For DeepSeek, the current-rate pairs are cache-miss input / output and vary by time of day.",
        "Gemma's zero benchmark rate was explicitly configured for the campaign and is not a universal market price.",
        "Benchmark requests to Gemini 3.1 Pro Preview used the standard context tier.", "",
        "The canonical frozen-rate records are in",
        "[`analysis/data/benchmark_pricing_manifest.json`](../analysis/data/benchmark_pricing_manifest.json).",
        "The same values are exposed as a flat analysis input in",
        "[`analysis/tables/token_cost_rates.csv`](../analysis/tables/token_cost_rates.csv),",
        "while per-model observed token and cost summaries are in",
        "[`analysis/tables/model_token_costs_17x60.csv`](../analysis/tables/model_token_costs_17x60.csv).", "",
    ])
    content = "\n".join(lines)
    if write:
        OUTPUT.write_text(content, encoding="utf-8")
    return content


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail if the generated document is stale")
    args = parser.parse_args()
    expected = build(write=not args.check)
    if args.check:
        actual = OUTPUT.read_text(encoding="utf-8")
        if actual != expected:
            raise SystemExit(f"{OUTPUT} is stale; regenerate it with {Path(__file__).name}")
        print(f"OK: {OUTPUT} matches the canonical model catalog")
    else:
        print(OUTPUT)
