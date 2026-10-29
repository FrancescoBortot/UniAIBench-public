#!/usr/bin/env python3
"""Verify every fixed manuscript file without rewriting or compiling it."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


STUDY_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = STUDY_ROOT / "paper_snapshot_sha256.json"


def verify(paper: Path, expected: dict[str, str]) -> list[str]:
    errors = []
    # Compilation products are deliberately outside the frozen source inventory.
    actual = {
        path.relative_to(paper).as_posix(): path
        for path in paper.rglob("*")
        if (path.is_file() or path.is_symlink())
        and "build" not in path.relative_to(paper).parts
        and "__pycache__" not in path.relative_to(paper).parts
        and path.name != ".DS_Store"
    }
    for name in sorted(set(actual) | set(expected)):
        if name not in expected:
            errors.append(f"unexpected manuscript file: {name}")
        elif name not in actual:
            errors.append(f"missing manuscript file: {name}")
        elif actual[name].is_symlink():
            errors.append(f"manuscript symlink is not allowed: {name}")
        elif hashlib.sha256(actual[name].read_bytes()).hexdigest() != expected[name]:
            errors.append(f"fixed manuscript hash changed: {name}")
    return errors


def main() -> int:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    errors = verify(STUDY_ROOT / "paper", manifest["files"])
    for error in errors:
        print(f"ERROR: {error}")
    if errors:
        return 1
    print(f"OK: all {len(manifest['files'])} frozen paper files are byte-identical")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
