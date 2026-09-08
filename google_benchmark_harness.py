#!/usr/bin/env python3
"""Convenience entry point for a locally configured Google benchmark."""

from __future__ import annotations

import sys
from pathlib import Path

import benchmark_harness


ROOT = Path(__file__).resolve().parent
DEFAULT_CONFIG = ROOT / "configs" / "google_benchmark_config.template.json"


def main() -> int:
    if "--config" not in sys.argv[1:]:
        sys.argv.extend(("--config", str(DEFAULT_CONFIG)))
    return benchmark_harness.main()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("Interrotto dall'utente; le esecuzioni già salvate saranno riutilizzate.", file=sys.stderr)
        raise SystemExit(130)
    except Exception as exc:
        print(f"Errore: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(2)
