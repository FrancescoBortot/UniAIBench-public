#!/usr/bin/env python3
"""Validate a UniAIBench configuration against its versioned JSON Schema."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from schema_validation import validate_json_schema


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    path = args.path if args.path.is_absolute() else ROOT / args.path
    payload = json.loads(path.read_text(encoding="utf-8"))
    schema = json.loads((ROOT / "schemas/benchmark-config.schema.json").read_text(encoding="utf-8"))
    validate_json_schema(payload, schema)
    print(f"OK: {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
