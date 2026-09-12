#!/usr/bin/env python3
"""Validate a benchmark configuration against its versioned JSON Schema."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from schema_validation import validate_json_schema


ROOT = Path(__file__).resolve().parents[1]


def display_path(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    if args.path.is_absolute():
        path = args.path
    elif args.path.exists():
        path = args.path.resolve()
    else:
        path = (ROOT / args.path).resolve()
    payload = json.loads(path.read_text(encoding="utf-8"))
    schema = json.loads((ROOT / "schemas/benchmark-config.schema.json").read_text(encoding="utf-8"))
    validate_json_schema(payload, schema)
    print(f"OK: {display_path(path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
