#!/usr/bin/env python3
"""Fail closed when a publication repository contains private artifacts."""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {
    ".cff", ".csv", ".gitignore", ".gitattributes", ".json", ".md",
    ".py", ".tex", ".txt", ".yaml", ".yml",
}
FORBIDDEN_TOP_LEVEL = {
    "DATASET", "DATASET_ANALISI_3", "DATASET_FISICA_2", "DOCUMENTI",
    "EXPERIMENTS", "JUDGING", "REPORTS", "RETRY_ARCHIVE", "RUNS",
    "SELF_REVIEW", "website",
}
FORBIDDEN_FILENAMES = {
    ".env", "identity_map.json", "raw_response.json", "response.txt",
}
REQUIRED = {
    "README.md", "DATA_PROVENANCE.md", "LICENSE.md", "CITATION.cff",
    "rubrics/templates/rubric.template.json", "schemas/rubric.schema.json",
    "schemas/judgment.schema.json", "schemas/judgment.template.json",
    "prompts/solver-prompt.md", "prompts/rubric-builder-prompt.md",
    "prompts/judge-prompt.md", "prompts/adjudicator-prompt.md",
    "configs/benchmark_config.template.json",
}


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def text_files() -> list[Path]:
    return [
        path for path in ROOT.rglob("*")
        if path.is_file()
        and ".git" not in path.parts
        and (path.suffix.lower() in TEXT_SUFFIXES or path.name in {"Makefile"})
    ]


def check_markdown_links(path: Path, text: str, errors: list[str]) -> None:
    for target in re.findall(r"!?\[[^\]]*\]\(([^)]+)\)", text):
        target = target.strip().split("#", 1)[0]
        if not target or target.startswith(("http://", "https://", "mailto:", "#")):
            continue
        target = target.strip("<>")
        if not (path.parent / target).resolve().exists():
            errors.append(f"broken local link in {relative(path)}: {target}")


def check_secret_assignment(path: Path, text: str, errors: list[str]) -> None:
    assignment = re.compile(
        r"(?im)^\s*(?:OPENAI|ANTHROPIC|GOOGLE|GEMINI|MOONSHOT|KIMI|DEEPSEEK|XAI)"
        r"_[A-Z0-9_]*(?:KEY|TOKEN)\s*=\s*([^\s#]+)"
    )
    for match in assignment.finditer(text):
        value = match.group(1).strip().strip("'\"")
        if value and not (value.startswith("<") and value.endswith(">")):
            errors.append(f"non-empty credential assignment in {relative(path)}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict", action="store_true", help="also require the publication checklist to be complete")
    args = parser.parse_args()
    errors: list[str] = []

    present = {path.name for path in ROOT.iterdir()}
    for name in sorted(FORBIDDEN_TOP_LEVEL & present):
        errors.append(f"forbidden top-level private artifact: {name}")
    for required in sorted(REQUIRED):
        if not (ROOT / required).is_file():
            errors.append(f"required file missing: {required}")

    rubric_json = sorted((ROOT / "rubrics").rglob("*.json"))
    expected_template = ROOT / "rubrics/templates/rubric.template.json"
    if rubric_json != [expected_template]:
        errors.append("rubrics/ must contain only the single blank rubric template")

    exercise_files = list(ROOT.rglob("esercizio_*.txt")) + list(ROOT.rglob("exercise_[0-9]*.txt"))
    if exercise_files:
        errors.append("source exercise text files are present")

    local_home_marker = "/" + "Users" + "/"
    token_prefixes = ("sk" + "-", "gh" + "p_", "gh" + "o_", "AIza" + "Sy")
    for path in text_files():
        if path.name in FORBIDDEN_FILENAMES:
            errors.append(f"forbidden file: {relative(path)}")
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if local_home_marker in text:
            errors.append(f"absolute local user path in {relative(path)}")
        if any(prefix in text for prefix in token_prefixes):
            errors.append(f"possible credential token in {relative(path)}")
        check_secret_assignment(path, text, errors)
        if path.suffix.lower() == ".md":
            check_markdown_links(path, text, errors)
        if path.suffix.lower() == ".json":
            try:
                json.loads(text)
            except json.JSONDecodeError as exc:
                errors.append(f"invalid JSON in {relative(path)}: {exc}")

    sensitive_headers = {"email", "phone", "person_name", "student_id", "user_id"}
    for path in ROOT.rglob("*.csv"):
        with path.open(newline="", encoding="utf-8") as handle:
            header = next(csv.reader(handle), [])
        overlap = sensitive_headers & {field.strip().lower() for field in header}
        if overlap:
            errors.append(f"potentially personal CSV fields in {relative(path)}: {sorted(overlap)}")

    if args.strict:
        checklist = (ROOT / "PUBLICATION_CHECKLIST.md").read_text(encoding="utf-8")
        if "- [ ]" in checklist:
            errors.append("publication checklist is not complete")

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("OK: publication repository contains no detected private artifacts or credentials")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
