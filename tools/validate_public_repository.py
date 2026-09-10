#!/usr/bin/env python3
"""Fail closed when a publication repository contains private artifacts."""

from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {
    ".cff", ".csv", ".gitignore", ".gitattributes", ".json", ".md",
    ".js", ".mjs", ".py", ".tex", ".ts", ".tsx", ".txt", ".yaml", ".yml",
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
    "PUBLICATION_CHECKLIST.md", "PUBLICATION_REVIEW.md",
    "rubrics/templates/rubric.template.json", "schemas/rubric.schema.json",
    "schemas/judgment.schema.json", "schemas/judgment.template.json",
    "prompts/solver-prompt.md", "prompts/rubric-builder-prompt.md",
    "prompts/judge-prompt.md", "prompts/adjudicator-prompt.md",
    "configs/benchmark_config.template.json",
    "schemas/benchmark-config.schema.json", "analysis/FIGURE_PROVENANCE.md",
    "analysis/scripts/build_main_chart_collection.py",
    "analysis/scripts/build_model_catalog_docs.py",
    "analysis/data/model_catalog.json", "tools/validate_model_catalog.py",
    "docs/assets/social-preview.png",
    "CONTRIBUTING.md",
}
OFFICIAL_SITE = "https://uniaibench.org"
RELEASE_VERSION = "1.0"
REQUIRED_CHECKS = {
    "ai-review", "rights", "scope", "licence", "metadata", "aggregate-data",
}
EXPECTED_ANALYSIS_FIGURES = {"overall_ranking.png"}
EXPECTED_PAPER_FIGURES = {
    "focused_response_time_charts.pdf",
    "focused_token_cost_charts.pdf",
    "item_difficulty.tex",
    "model_technical_specifications.pdf",
    "performance_overview.tex",
    "publication_benchmark_map.tex",
    "resource_frontiers.tex",
    "rubric_anatomy.tex",
    "selected_correctness_charts.pdf",
    "subject_contrast.tex",
    "token_ablation.tex",
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


def git_paths(*arguments: str) -> list[str]:
    process = subprocess.run(
        ["git", *arguments], cwd=ROOT, text=True, capture_output=True, check=False
    )
    if process.returncode != 0:
        return []
    return [line.strip() for line in process.stdout.splitlines() if line.strip()]


def private_path_reason(candidate: str) -> str | None:
    parts = candidate.replace("\\", "/").split("/")
    if any(part.upper() in FORBIDDEN_TOP_LEVEL for part in parts):
        return "contains a private-artifact directory"
    if any(part.lower() in {name.lower() for name in FORBIDDEN_FILENAMES} for part in parts):
        return "contains a forbidden artifact filename"
    return None


def required_checklist_status(text: str) -> tuple[set[str], set[str]]:
    pattern = re.compile(
        r"^- \[(?P<status>[ xX])\] <!-- required:(?P<identifier>[a-z0-9-]+) -->",
        re.MULTILINE,
    )
    found: set[str] = set()
    incomplete: set[str] = set()
    for match in pattern.finditer(text):
        identifier = match.group("identifier")
        found.add(identifier)
        if match.group("status").lower() != "x":
            incomplete.add(identifier)
    return found, incomplete


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

    for candidate in git_paths("ls-files"):
        reason = private_path_reason(candidate)
        if reason:
            errors.append(f"tracked path {reason}: {candidate}")
    for candidate in git_paths("log", "--all", "--format=", "--name-only"):
        reason = private_path_reason(candidate)
        if reason:
            errors.append(f"Git history path {reason}: {candidate}")

    rubric_json = sorted((ROOT / "rubrics").rglob("*.json"))
    expected_template = ROOT / "rubrics/templates/rubric.template.json"
    if rubric_json != [expected_template]:
        errors.append("rubrics/ must contain only the single blank rubric template")

    figures_dir = ROOT / "analysis/figures"
    actual_figures = {
        path.name for path in figures_dir.iterdir() if path.is_file()
    } if figures_dir.is_dir() else set()
    if actual_figures != EXPECTED_ANALYSIS_FIGURES:
        errors.append(
            "analysis/figures must contain only the current English README figure; "
            f"expected {sorted(EXPECTED_ANALYSIS_FIGURES)}, found {sorted(actual_figures)}"
        )

    paper_figures_dir = ROOT / "paper/figures"
    actual_paper_figures = {
        path.name for path in paper_figures_dir.iterdir() if path.is_file()
    } if paper_figures_dir.is_dir() else set()
    if actual_paper_figures != EXPECTED_PAPER_FIGURES:
        errors.append(
            "paper/figures must contain only manuscript figures and current English supplements; "
            f"expected {sorted(EXPECTED_PAPER_FIGURES)}, found {sorted(actual_paper_figures)}"
        )

    exercise_files = list(ROOT.rglob("esercizio_*.txt")) + list(ROOT.rglob("exercise_[0-9]*.txt"))
    if exercise_files:
        errors.append("source exercise text files are present")

    local_home_marker = "/" + "Users" + "/"
    token_patterns = (
        re.compile(r"(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{16,}"),
        re.compile(r"\bgh[po]_[A-Za-z0-9]{20,}"),
        re.compile(r"\bAIzaSy[A-Za-z0-9_-]{20,}"),
        re.compile(r"\bAKIA[A-Z0-9]{16}\b"),
        re.compile("-----BEGIN " + "PRIVATE KEY-----"),
    )
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
        if any(pattern.search(text) for pattern in token_patterns):
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
        found, incomplete = required_checklist_status(checklist)
        missing = REQUIRED_CHECKS - found
        unexpected = found - REQUIRED_CHECKS
        if missing:
            errors.append(f"required publication checks missing: {sorted(missing)}")
        if unexpected:
            errors.append(f"unknown required publication checks: {sorted(unexpected)}")
        if incomplete:
            errors.append(f"required publication checks incomplete: {sorted(incomplete)}")

        review = (ROOT / "PUBLICATION_REVIEW.md").read_text(encoding="utf-8")
        for marker in ("AI_REVIEW_STATUS: PASSED", "HUMAN_RIGHTS_STATUS: CONFIRMED"):
            if marker not in review:
                errors.append(f"publication review marker missing: {marker}")

        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        citation = (ROOT / "CITATION.cff").read_text(encoding="utf-8")
        if OFFICIAL_SITE not in readme or OFFICIAL_SITE not in citation:
            errors.append(f"official website must be consistent: {OFFICIAL_SITE}")
        version_pattern = rf'^version:\s*["\']?{re.escape(RELEASE_VERSION)}["\']?\s*$'
        if re.search(version_pattern, citation, re.MULTILINE) is None:
            errors.append(f"CITATION.cff version must be {RELEASE_VERSION}")

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("OK: publication repository contains no detected private artifacts or credentials")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
