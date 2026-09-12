#!/usr/bin/env python3
"""Ensure the reusable toolkit does not depend on UniAIBench study artifacts."""

from __future__ import annotations

import ast
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOLKIT_ROOT = ROOT / "benchmark-toolkit"
SCANNED_SUFFIXES = {".json", ".py", ".sh", ".toml", ".yaml", ".yml"}
SCANNED_FILENAMES = {"Makefile"}
STUDY_PATH = re.compile(r"(?:^|[/\\])uniaibench(?:[/\\]|$)", re.IGNORECASE)


def is_study_module(value: str) -> bool:
    normalized = value.strip().casefold()
    return normalized == "uniaibench" or normalized.startswith("uniaibench.")


def is_study_path(value: str) -> bool:
    return STUDY_PATH.search(value) is not None


def python_dependency_reasons(source: str) -> list[str]:
    """Return prohibited import/path reasons found in Python source."""
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return [f"invalid Python syntax: {exc.msg} at line {exc.lineno}"]

    reasons: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if is_study_module(alias.name):
                    reasons.append(f"imports {alias.name!r} at line {node.lineno}")
        elif isinstance(node, ast.ImportFrom):
            if node.module and is_study_module(node.module):
                reasons.append(f"imports from {node.module!r} at line {node.lineno}")
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            if is_study_module(node.value) or is_study_path(node.value):
                reasons.append(f"references a UniAIBench study path at line {node.lineno}")
    return reasons


def dependency_errors(toolkit_root: Path = TOOLKIT_ROOT) -> list[str]:
    if not toolkit_root.is_dir():
        return [f"toolkit directory is missing: {toolkit_root}"]

    errors: list[str] = []
    for path in sorted(toolkit_root.rglob("*")):
        if path.is_symlink():
            try:
                path.resolve().relative_to(toolkit_root.resolve())
            except ValueError:
                errors.append(
                    f"{path.relative_to(ROOT).as_posix()}: symlink resolves outside benchmark-toolkit"
                )
                continue
        if not path.is_file():
            continue
        if path.suffix.lower() not in SCANNED_SUFFIXES and path.name not in SCANNED_FILENAMES:
            continue
        relative = path.relative_to(ROOT).as_posix()
        try:
            source = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            errors.append(f"{relative}: executable/configuration file is not UTF-8 text")
            continue

        if path.suffix.lower() == ".py":
            for reason in python_dependency_reasons(source):
                errors.append(f"{relative}: {reason}")
        else:
            for line_number, line in enumerate(source.splitlines(), start=1):
                if is_study_path(line):
                    errors.append(
                        f"{relative}: references a UniAIBench study path at line {line_number}"
                    )
    return errors


def main() -> int:
    errors = dependency_errors()
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("OK: benchmark-toolkit has no executable or configuration dependency on uniaibench")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
