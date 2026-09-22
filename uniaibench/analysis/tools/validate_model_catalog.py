#!/usr/bin/env python3
"""Validate model metadata and frozen-rate provenance across public evidence."""

from __future__ import annotations

import csv
import json
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / "analysis" / "data" / "model_catalog.json"
PRICING_MANIFEST = ROOT / "analysis" / "data" / "benchmark_pricing_manifest.json"
RESOURCES = ROOT / "analysis" / "data" / "model_item_resources.csv"
RANKING = ROOT / "analysis" / "tables" / "main_ranking_overall.csv"
RATES = ROOT / "analysis" / "tables" / "token_cost_rates.csv"
MODEL_TOKEN_COSTS = ROOT / "analysis" / "tables" / "model_token_costs_17x60.csv"
QUALITY_TOKEN_COST = ROOT / "analysis" / "tables" / "quality_token_cost_17x60.csv"
MANIFEST_REPO_PATH = "uniaibench/analysis/data/benchmark_pricing_manifest.json"
PUBLIC_SOURCE_KIND = "public_pricing_manifest_record"
PRIVATE_SOURCE_KIND = "private_campaign_configuration_snapshot"
OFFICIAL_SOURCE_KIND = "official_provider_documentation"
EXPECTED_PRIVATE_FINGERPRINTS = {
    "e4f31febe7e7ad22fa126b61e9f3b8ca29d10cda877ef29d9933e33deb77af23",
    "72f55057c52ab2b6c046bfaf25c4b38760bba171fe667cc82cde02e342da559b",
    "8048c80ca15cebfabab8d0b6c688f6b247df67f0299985ec219e3907fcda1a78",
}
PRIVATE_NAME_MARKERS = ("benchmark_config_", "primo_secondo", "deepseek_xai")
RECORD_ID_RE = re.compile(r"[a-z0-9][a-z0-9.-]*\Z")
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
RATE_COLUMNS = [
    "model", "input_usd_per_million", "output_usd_per_million",
    "source_kind", "source", "note",
]
MANIFEST_RATE_FIELDS = {
    "record_id", "model_id", "model", "input_usd_per_million",
    "output_usd_per_million", "rate_origin_kind", "official_reference_url",
    "configuration_snapshot_sha256", "note",
}
REQUIRED_MODEL_FIELDS = {
    "provider", "model", "id", "release", "release_note", "parameters",
    "weights", "architecture", "reasoning", "context", "output", "modalities",
    "cutoff", "model_url", "provider_display", "api_display", "api_url",
    "public_release_display", "open_weights_display", "benchmark_reasoning_display",
    "latest_verified_rate", "benchmark_rate", "pricing_source_label",
    "pricing_source_url", "benchmark_input_usd_per_million",
    "benchmark_output_usd_per_million", "benchmark_price_source_kind",
    "benchmark_price_source",
}


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"{path.name}: missing CSV header")
        return reader.fieldnames, list(reader)


def decimal(value: object, *, context: str) -> Decimal:
    if isinstance(value, bool):
        raise ValueError(f"{context}: Boolean is not a valid rate")
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{context}: invalid numeric rate {value!r}") from exc
    if not parsed.is_finite() or parsed < 0:
        raise ValueError(f"{context}: rate must be finite and non-negative")
    return parsed


def expected_pointer(record_id: str) -> str:
    return f"{MANIFEST_REPO_PATH}#{record_id}"


def require_unique(values: list[str], *, context: str) -> None:
    if len(set(values)) != len(values):
        raise ValueError(f"{context}: duplicate values are not allowed")


def load_pricing_manifest(catalog: dict[str, object]) -> dict[str, dict[str, object]]:
    payload = json.loads(PRICING_MANIFEST.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise ValueError("benchmark_pricing_manifest.json: unsupported schema_version")
    for field in ("benchmark_snapshot_date", "currency", "price_unit"):
        if payload.get(field) != catalog.get(field):
            raise ValueError(f"pricing manifest and model catalog disagree on {field}")

    boundary = payload.get("source_boundary")
    if not isinstance(boundary, dict) or not all(
        isinstance(boundary.get(field), str) and boundary[field].strip()
        for field in ("distributed", "withheld", "fingerprint_semantics")
    ):
        raise ValueError("pricing manifest must document its public/private source boundary")

    rates = payload.get("rates")
    if not isinstance(rates, list) or len(rates) != 17:
        raise ValueError("benchmark_pricing_manifest.json must contain exactly 17 rates")

    records: dict[str, dict[str, object]] = {}
    model_ids: list[str] = []
    model_names: list[str] = []
    private_fingerprints: set[str] = set()
    for index, record in enumerate(rates, start=1):
        if not isinstance(record, dict) or set(record) != MANIFEST_RATE_FIELDS:
            raise ValueError(f"pricing manifest rate {index}: fields do not match the public contract")
        record_id = record["record_id"]
        model_id = record["model_id"]
        model = record["model"]
        if not isinstance(record_id, str) or not RECORD_ID_RE.fullmatch(record_id):
            raise ValueError(f"pricing manifest rate {index}: invalid record_id")
        if not isinstance(model_id, str) or not model_id.strip():
            raise ValueError(f"pricing manifest rate {index}: invalid model_id")
        if not isinstance(model, str) or not model.strip():
            raise ValueError(f"pricing manifest rate {index}: invalid model")
        if not isinstance(record["note"], str) or not record["note"].strip():
            raise ValueError(f"{model}: pricing note must be non-empty")
        decimal(record["input_usd_per_million"], context=f"{model} input rate")
        decimal(record["output_usd_per_million"], context=f"{model} output rate")

        url = record["official_reference_url"]
        if not isinstance(url, str) or not url.startswith("https://"):
            raise ValueError(f"{model}: official_reference_url must use HTTPS")
        origin = record["rate_origin_kind"]
        fingerprint = record["configuration_snapshot_sha256"]
        if origin == OFFICIAL_SOURCE_KIND:
            if fingerprint is not None:
                raise ValueError(f"{model}: official rate must not claim a private configuration fingerprint")
        elif origin == PRIVATE_SOURCE_KIND:
            if not isinstance(fingerprint, str) or not SHA256_RE.fullmatch(fingerprint):
                raise ValueError(f"{model}: private configuration fingerprint must be a SHA-256 digest")
            if fingerprint not in EXPECTED_PRIVATE_FINGERPRINTS:
                raise ValueError(f"{model}: unexpected private configuration fingerprint")
            private_fingerprints.add(fingerprint)
        else:
            raise ValueError(f"{model}: unsupported rate_origin_kind {origin!r}")

        if record_id in records:
            raise ValueError(f"pricing manifest: duplicate record_id {record_id!r}")
        records[record_id] = record
        model_ids.append(model_id)
        model_names.append(model)

    require_unique(model_ids, context="pricing manifest model_id")
    require_unique(model_names, context="pricing manifest model")
    if private_fingerprints != EXPECTED_PRIVATE_FINGERPRINTS:
        raise ValueError("pricing manifest does not bind every frozen private configuration snapshot")
    return records


def main() -> int:
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    models = catalog.get("models")
    if not isinstance(models, list) or len(models) != 17:
        raise ValueError("model_catalog.json must contain exactly 17 configurations")
    manifest = load_pricing_manifest(catalog)
    manifest_by_model_id = {str(record["model_id"]): record for record in manifest.values()}

    names = [str(model.get("model")) for model in models]
    ids = [str(model.get("id")) for model in models]
    require_unique(names, context="model catalog model")
    require_unique(ids, context="model catalog id")
    if set(ids) != set(manifest_by_model_id):
        raise ValueError("model catalog and pricing manifest contain different model IDs")

    model_by_name: dict[str, dict[str, object]] = {}
    for model in models:
        missing = REQUIRED_MODEL_FIELDS - model.keys()
        if missing:
            raise ValueError(f"{model.get('model', '<unknown>')}: missing fields {sorted(missing)}")
        for field in ("model_url", "api_url", "pricing_source_url"):
            if not str(model[field]).startswith("https://"):
                raise ValueError(f"{model['model']}: {field} must use HTTPS")

        record = manifest_by_model_id[str(model["id"])]
        record_id = str(record["record_id"])
        if model["model"] != record["model"]:
            raise ValueError(f"{model['model']}: pricing manifest model name differs")
        if model["benchmark_price_source_kind"] != PUBLIC_SOURCE_KIND:
            raise ValueError(f"{model['model']}: benchmark_price_source_kind must point to the public manifest")
        if model["benchmark_price_source"] != expected_pointer(record_id):
            raise ValueError(f"{model['model']}: invalid benchmark pricing manifest pointer")
        if model["pricing_source_url"] != record["official_reference_url"]:
            raise ValueError(f"{model['model']}: official pricing reference differs from manifest")
        for side in ("input", "output"):
            catalog_rate = decimal(
                model[f"benchmark_{side}_usd_per_million"],
                context=f"{model['model']} catalog {side} rate",
            )
            manifest_rate = decimal(
                record[f"{side}_usd_per_million"],
                context=f"{model['model']} manifest {side} rate",
            )
            if catalog_rate != manifest_rate:
                raise ValueError(f"{model['model']}: catalog and manifest {side} rates differ")
        model_by_name[str(model["model"])] = model

    _, ranking = read_csv(RANKING)
    if set(names) != {row["model"] for row in ranking}:
        raise ValueError("model catalog and overall ranking contain different model sets")

    rate_header, rates = read_csv(RATES)
    if rate_header != RATE_COLUMNS:
        raise ValueError(f"token_cost_rates.csv: expected columns {RATE_COLUMNS}")
    if len(rates) != 17:
        raise ValueError("token_cost_rates.csv must contain exactly 17 rows")
    rate_by_model = {row["model"]: row for row in rates}
    if len(rate_by_model) != len(rates) or set(names) != set(rate_by_model):
        raise ValueError("model catalog and frozen-rate table contain different or duplicate model sets")
    for model in models:
        record = manifest_by_model_id[str(model["id"])]
        row = rate_by_model[str(model["model"])]
        if row["source_kind"] != PUBLIC_SOURCE_KIND:
            raise ValueError(f"{model['model']}: rate table source_kind must point to the public manifest")
        if row["source"] != expected_pointer(str(record["record_id"])):
            raise ValueError(f"{model['model']}: rate table has an invalid manifest pointer")
        if row["note"] != record["note"]:
            raise ValueError(f"{model['model']}: rate table note differs from manifest")
        for side in ("input", "output"):
            table_rate = decimal(row[f"{side}_usd_per_million"], context=f"{model['model']} table {side} rate")
            manifest_rate = decimal(record[f"{side}_usd_per_million"], context=f"{model['model']} manifest {side} rate")
            if table_rate != manifest_rate:
                raise ValueError(f"{model['model']}: rate table and manifest {side} rates differ")

    _, resources = read_csv(RESOURCES)
    if len(resources) != 1020:
        raise ValueError("model_item_resources.csv must contain exactly 1020 matched model-item rows")
    if {row["model"] for row in resources} != set(names):
        raise ValueError("resource panel and model catalog contain different model sets")
    for index, row in enumerate(resources, start=2):
        model_name = row["model"]
        model = model_by_name[model_name]
        record = manifest_by_model_id[str(model["id"])]
        if row["price_source_kind"] != PUBLIC_SOURCE_KIND:
            raise ValueError(f"model_item_resources.csv line {index}: source_kind does not point to the public manifest")
        if row["price_source"] != expected_pointer(str(record["record_id"])):
            raise ValueError(f"model_item_resources.csv line {index}: invalid pricing manifest pointer")
        for side in ("input", "output"):
            panel_rate = decimal(row[f"{side}_rate_usd_per_million"], context=f"resource line {index} {side} rate")
            manifest_rate = decimal(record[f"{side}_usd_per_million"], context=f"{model_name} manifest {side} rate")
            if panel_rate != manifest_rate:
                raise ValueError(f"model_item_resources.csv line {index}: {side} rate differs from manifest")

    _, token_summaries = read_csv(MODEL_TOKEN_COSTS)
    token_summary_by_model = {row["model"]: row for row in token_summaries}
    if len(token_summaries) != 17 or len(token_summary_by_model) != 17 or set(token_summary_by_model) != set(names):
        raise ValueError("model_token_costs_17x60.csv must contain one row per model")
    for model_name, row in token_summary_by_model.items():
        model = model_by_name[model_name]
        record = manifest_by_model_id[str(model["id"])]
        if row["price_source_kind"] != PUBLIC_SOURCE_KIND:
            raise ValueError(f"{model_name}: token summary source_kind does not point to the public manifest")
        if row["price_source"] != expected_pointer(str(record["record_id"])):
            raise ValueError(f"{model_name}: token summary has an invalid pricing manifest pointer")
        for side in ("input", "output"):
            summary_rate = decimal(row[f"{side}_rate_usd_per_million"], context=f"{model_name} summary {side} rate")
            manifest_rate = decimal(record[f"{side}_usd_per_million"], context=f"{model_name} manifest {side} rate")
            if summary_rate != manifest_rate:
                raise ValueError(f"{model_name}: token summary and manifest {side} rates differ")

    _, quality_rows = read_csv(QUALITY_TOKEN_COST)
    quality_by_model = {row["model"]: row for row in quality_rows}
    if len(quality_rows) != 17 or len(quality_by_model) != 17 or set(quality_by_model) != set(names):
        raise ValueError("quality_token_cost_17x60.csv must contain one row per model")
    for model_name, row in quality_by_model.items():
        if row["price_source_kind"] != PUBLIC_SOURCE_KIND:
            raise ValueError(f"{model_name}: quality summary source_kind does not point to the public manifest")

    for path in (
        CATALOG, PRICING_MANIFEST, RESOURCES, RATES,
        MODEL_TOKEN_COSTS, QUALITY_TOKEN_COST,
    ):
        text = path.read_text(encoding="utf-8")
        if any(marker in text for marker in PRIVATE_NAME_MARKERS):
            raise ValueError(f"{path.name}: contains a private configuration name")

    print(
        "OK: 17 model records, 17 frozen rates, 1020 resource rows, and "
        "both cost summaries resolve to the public pricing manifest"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
