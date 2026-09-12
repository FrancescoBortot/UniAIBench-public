#!/usr/bin/env python3
"""Convenience entry point for a locally configured Google benchmark."""

from __future__ import annotations

import sys
from pathlib import Path

import benchmark_harness


TOOLKIT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = TOOLKIT_ROOT / "configs" / "google_benchmark_config.template.json"


def main() -> int:
    if not any(
        argument == "--config" or argument.startswith("--config=")
        for argument in sys.argv[1:]
    ):
        sys.argv.extend(("--config", str(DEFAULT_CONFIG)))
    return benchmark_harness.main()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("Interrupted by the user; saved runs will be reused.", file=sys.stderr)
        raise SystemExit(130)
    except Exception as exc:
        print(f"Error: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(2)
