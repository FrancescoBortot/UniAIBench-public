#!/usr/bin/env python3
"""Fail closed when a publication repository contains private artifacts."""

from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
from pathlib import Path
from typing import Iterator


ROOT = Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {
    ".cff", ".csv", ".gitignore", ".gitattributes", ".json", ".md",
    ".bash", ".cfg", ".css", ".html", ".ini", ".ipynb", ".js", ".mjs",
    ".py", ".rst", ".sh", ".svg", ".tex", ".toml", ".ts", ".tsx", ".txt",
    ".xml", ".yaml", ".yml", ".zsh",
}
TEXT_FILENAMES = {".gitattributes", ".gitignore", "Makefile"}
FORBIDDEN_TOP_LEVEL = {
    "DATASET", "DATASET_ANALISI_3", "DATASET_FISICA_2", "DOCUMENTI",
    "EXPERIMENTS", "JUDGING", "REPORTS", "RETRY_ARCHIVE", "RUNS",
    "Router", "SELF_REVIEW", "benchmark-workspace", "local_data",
    "local_outputs", "local_workflow", "results", "website",
}
FORBIDDEN_FILENAMES = {
    ".env", "identity-map.json", "identity_map.json", "raw_response.json", "response.txt",
}
IDENTITY_MAP_TEMPLATE = "benchmark-toolkit/templates/identity-map.template.json"
APPROVED_BLANK_TEMPLATES = {
    "benchmark-toolkit/templates/adjudication.template.json": "adjudication record",
    "benchmark-toolkit/templates/blind-batch-manifest.template.json": "operational blind-batch manifest",
    "benchmark-toolkit/templates/identity-map.template.json": "private identity map",
    "benchmark-toolkit/templates/judgment.template.json": "individual judgment",
    "benchmark-toolkit/templates/rubric.template.json": "item-specific rubric",
    # These paths occur in the clean pre-restructure history.
    "rubrics/templates/rubric.template.json": "item-specific rubric",
    "schemas/judgment.template.json": "individual judgment",
}
IGNORED_LOCAL_PARTS = {".git", ".venv", "__pycache__"}
MAX_HISTORY_TEXT_BLOB_BYTES = 2_000_000
ZERO_SHA256 = "0" * 64
SECRET_ASSIGNMENT_PATTERN = re.compile(
    r"(?im)^\s*[A-Z][A-Z0-9_]*(?:API_KEY|ACCESS_TOKEN|AUTH_TOKEN|SECRET_KEY)"
    r"\s*=\s*([^\s#]+)"
)
TOKEN_PATTERNS = (
    re.compile(r"(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{16,}"),
    re.compile(r"\bgh[po]_[A-Za-z0-9]{20,}"),
    re.compile(r"\bAIzaSy[A-Za-z0-9_-]{20,}"),
    re.compile(r"\bAKIA[A-Z0-9]{16}\b"),
    re.compile("-----BEGIN " + "PRIVATE KEY-----"),
)
REQUIRED = {
    "README.md", "uniaibench/DATA_PROVENANCE.md", "LICENSE.md", "CITATION.cff",
    "PUBLICATION_CHECKLIST.md", "PUBLICATION_REVIEW.md",
    "uniaibench/README.md",
    "uniaibench/STUDY_MANIFEST.json",
    "uniaibench/METHOD_IMPLEMENTATION.md",
    "benchmark-toolkit/README.md",
    "benchmark-toolkit/templates/rubric.template.json",
    "benchmark-toolkit/schemas/rubric.schema.json",
    "benchmark-toolkit/schemas/judgment.schema.json",
    "benchmark-toolkit/templates/judgment.template.json",
    "benchmark-toolkit/templates/blind-batch-manifest.template.json",
    "benchmark-toolkit/schemas/blind-batch-manifest.schema.json",
    "benchmark-toolkit/templates/identity-map.template.json",
    "benchmark-toolkit/schemas/identity-map.schema.json",
    "benchmark-toolkit/templates/adjudication.template.json",
    "benchmark-toolkit/schemas/adjudication.schema.json",
    "benchmark-toolkit/templates/aggregation-config.template.json",
    "benchmark-toolkit/schemas/aggregation-config.schema.json",
    "benchmark-toolkit/prompts/solver-prompt.md",
    "benchmark-toolkit/prompts/rubric-builder-prompt.md",
    "benchmark-toolkit/prompts/judge-prompt.md",
    "benchmark-toolkit/prompts/adjudicator-prompt.md",
    "benchmark-toolkit/configs/benchmark_config.template.json",
    "benchmark-toolkit/schemas/benchmark-config.schema.json",
    "uniaibench/analysis/FIGURE_PROVENANCE.md",
    "uniaibench/analysis/scripts/build_main_chart_collection.py",
    "uniaibench/analysis/scripts/build_model_catalog_docs.py",
    "uniaibench/analysis/data/model_catalog.json",
    "uniaibench/analysis/tools/validate_model_catalog.py",
    "uniaibench/assets/social-preview.png",
    "tools/check_dependency_direction.py",
    "CONTRIBUTING.md",
}
OFFICIAL_SITE = "https://uniaibench.org"
RELEASE_VERSION = "1.1"
REQUIRED_CHECKS = {
    "semantic-review", "rights", "scope", "licence", "metadata", "aggregate-data",
}
EXPECTED_ANALYSIS_FIGURES = {
    "site/01_01_overall_ranking.svg",
    "site/02_02_overall_t1_t8_profile.svg",
    "site/05_01_cost_ranking.svg",
    "site/06_02_token_composition.svg",
    "site/07_01_response_time_ranking.svg",
    "site/08_02_model_exercise_heatmap.svg",
    "site/09_03_time_drivers.svg",
    "site/10_04_response_time_accuracy_correlation.svg",
}
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
        and not path.is_symlink()
        and not (set(path.relative_to(ROOT).parts) & IGNORED_LOCAL_PARTS)
        and is_text_repository_path(relative(path))
        and private_path_reason(relative(path)) is None
    ]


def check_markdown_links(path: Path, text: str, errors: list[str]) -> None:
    for target in re.findall(r"!?\[[^\]]*\]\(([^)]+)\)", text):
        target = target.strip().split("#", 1)[0]
        if not target or target.startswith(("http://", "https://", "mailto:", "#")):
            continue
        target = target.strip("<>")
        if not (path.parent / target).resolve().exists():
            errors.append(f"broken local link in {relative(path)}: {target}")


def has_nonplaceholder_secret_assignment(text: str) -> bool:
    for match in SECRET_ASSIGNMENT_PATTERN.finditer(text):
        value = match.group(1).strip().strip("'\"")
        if value and not (value.startswith("<") and value.endswith(">")):
            return True
    return False


def sensitive_text_findings(text: str) -> set[str]:
    findings: set[str] = set()
    local_home_marker = "/" + "Users" + "/"
    if local_home_marker in text:
        findings.add("absolute local user path")
    if any(pattern.search(text) for pattern in TOKEN_PATTERNS):
        findings.add("possible credential token")
    if has_nonplaceholder_secret_assignment(text):
        findings.add("non-empty credential assignment")
    return findings


def git_paths(*arguments: str) -> list[str]:
    process = subprocess.run(
        ["git", *arguments], cwd=ROOT, text=True, capture_output=True, check=False
    )
    if process.returncode != 0:
        raise RuntimeError("unable to enumerate Git paths")
    return [line.strip() for line in process.stdout.splitlines() if line.strip()]


def private_path_reason(candidate: str) -> str | None:
    parts = candidate.replace("\\", "/").split("/")
    forbidden_directories = {name.casefold() for name in FORBIDDEN_TOP_LEVEL}
    forbidden_filenames = {name.casefold() for name in FORBIDDEN_FILENAMES}
    if any(part.casefold() in forbidden_directories for part in parts):
        return "contains a private-artifact directory"
    if any(part.casefold() in forbidden_filenames for part in parts):
        return "contains a forbidden artifact filename"
    if any(
        part.casefold().startswith(".env.") and part.casefold() != ".env.example"
        for part in parts
    ):
        return "contains a forbidden environment filename"
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


def looks_like_identity_map(payload: object) -> bool:
    if not isinstance(payload, dict):
        return False
    schema_name = str(payload.get("$schema", "")).replace("\\", "/").rsplit("/", 1)[-1]
    identity_fields = {"campaign_id", "batch_id", "blind_batch_manifest_path", "entries"}
    return schema_name.casefold() == "identity-map.schema.json" or identity_fields <= payload.keys()


def schema_basename(payload: dict[str, object]) -> str:
    return str(payload.get("$schema", "")).replace("\\", "/").rsplit("/", 1)[-1].casefold()


def looks_like_rubric_artifact(payload: object) -> bool:
    if not isinstance(payload, dict):
        return False
    fields = {
        "rubric_version", "item_id", "atomic_criteria",
        "dimension_point_budget", "human_approval",
    }
    return schema_basename(payload) == "rubric.schema.json" or fields <= payload.keys()


def looks_like_completed_rubric(payload: object) -> bool:
    if not looks_like_rubric_artifact(payload):
        return False
    assert isinstance(payload, dict)
    approval = payload.get("human_approval")
    approved = isinstance(approval, dict) and approval.get("approved") is True
    criteria = payload.get("atomic_criteria")
    return payload.get("frozen") is True or approved or isinstance(criteria, list) and bool(criteria)


def looks_like_individual_judgment(payload: object) -> bool:
    if not isinstance(payload, dict):
        return False
    fields = {
        "judgment_version", "item_id", "response_id", "criterion_assessment",
        "dimensions", "technical_score",
    }
    return schema_basename(payload) == "judgment.schema.json" or fields <= payload.keys()


def looks_like_source_manifest(payload: object) -> bool:
    if not isinstance(payload, dict):
        return False
    if not {
        "schema_version", "campaign_id", "batch_id", "judging_contract", "responses"
    } <= payload.keys():
        return False
    responses = payload.get("responses")
    return isinstance(responses, list) and any(
        isinstance(entry, dict)
        and {"source_run_id", "system_id", "response_path", "model_identity"} <= entry.keys()
        for entry in responses
    )


def looks_like_blind_batch_manifest(payload: object) -> bool:
    if not isinstance(payload, dict):
        return False
    fields = {
        "schema_version", "campaign_id", "batch_id", "judging_contract",
        "item_artifacts", "responses",
    }
    return schema_basename(payload) == "blind-batch-manifest.schema.json" or fields <= payload.keys()


def looks_like_final_adjudication(payload: object) -> bool:
    if not isinstance(payload, dict):
        return False
    fields = {
        "adjudication_id", "decision_status", "reviewer", "decision",
        "impact", "affected_response_ids", "reevaluation",
    }
    shaped = schema_basename(payload) == "adjudication.schema.json" or fields <= payload.keys()
    if not shaped:
        return False
    reviewer = payload.get("reviewer")
    return payload.get("decision_status") == "final" or (
        isinstance(reviewer, dict) and reviewer.get("human_confirmed") is True
    )


def looks_like_adjudication_artifact(payload: object) -> bool:
    if not isinstance(payload, dict):
        return False
    fields = {
        "adjudication_id", "decision_status", "reviewer", "decision",
        "impact", "affected_response_ids", "reevaluation",
    }
    return schema_basename(payload) == "adjudication.schema.json" or fields <= payload.keys()


def looks_like_unblinded_results(payload: object) -> bool:
    if not isinstance(payload, dict):
        return False
    fields = {
        "campaign_id", "batch_id", "blind_batch_manifest_path",
        "identity_map_path", "records",
    }
    if not fields <= payload.keys():
        return False
    records = payload.get("records")
    return isinstance(records, list) and (
        "identity_map_sha256" in payload
        or any(
            isinstance(entry, dict)
            and {"anonymous_response_id", "system_id", "model_identity", "judgment"}
            <= entry.keys()
            for entry in records
        )
    )


def private_json_artifact_kind(payload: object) -> str | None:
    detectors = (
        ("private identity map", looks_like_identity_map),
        ("private source manifest", looks_like_source_manifest),
        ("operational blind-batch manifest", looks_like_blind_batch_manifest),
        ("private unblinded results", looks_like_unblinded_results),
        ("item-specific rubric", looks_like_rubric_artifact),
        ("individual judgment", looks_like_individual_judgment),
        ("adjudication record", looks_like_adjudication_artifact),
    )
    for kind, detector in detectors:
        if detector(payload):
            return kind
    return None


def placeholder(value: object) -> bool:
    if not isinstance(value, str):
        return False
    lowered = value.casefold()
    return (
        value == ZERO_SHA256
        or value == "1970-01-01T00:00:00Z"
        or value.startswith("<") and value.endswith(">")
        or lowered.startswith("replace-with-")
        or lowered.startswith("replace/with/")
    )


def contains_placeholder(value: object) -> bool:
    if not isinstance(value, str):
        return False
    lowered = value.casefold()
    return placeholder(value) or "replace-with-" in lowered or "replace/with/" in lowered


def hashes_are_placeholders(payload: object) -> bool:
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key.endswith("sha256") and value not in (ZERO_SHA256, None):
                return False
            if not hashes_are_placeholders(value):
                return False
    elif isinstance(payload, list):
        return all(hashes_are_placeholders(item) for item in payload)
    return True


def approved_blank_template(path: str, kind: str, payload: object) -> bool:
    normalized = path.replace("\\", "/")
    if APPROVED_BLANK_TEMPLATES.get(normalized) != kind or not isinstance(payload, dict):
        return False
    if kind == "item-specific rubric":
        approval = payload.get("human_approval")
        profile = payload.get("domain_profile")
        subproblems = payload.get("subproblems")
        return (
            payload.get("created_without_model_answers") is True
            and payload.get("frozen") is False
            and payload.get("reference_status") == "unverified"
            and payload.get("reference_notes", "") == ""
            and payload.get("atomic_criteria") == []
            and payload.get("rubric_specific_caps") == []
            and payload.get("human_review_triggers") == []
            and isinstance(approval, dict)
            and approval.get("approved") is False
            and approval.get("reviewer") == ""
            and approval.get("date") == ""
            and placeholder(payload.get("item_id"))
            and placeholder(payload.get("subject"))
            and isinstance(profile, dict)
            and placeholder(profile.get("discipline"))
            and placeholder(profile.get("topic"))
            and placeholder(profile.get("task_type"))
            and profile.get("domain_specific_fields") == {}
            and isinstance(subproblems, list)
            and len(subproblems) == 1
            and all(
                isinstance(item, dict)
                and placeholder(item.get("id"))
                and placeholder(item.get("request"))
                and item.get("expected_results") == []
                and item.get("required_conditions") == []
                and item.get("accepted_equivalences") == []
                and item.get("accepted_alternative_methods") == []
                for item in subproblems
            )
        )
    if kind == "individual judgment":
        score = payload.get("technical_score")
        dimensions = payload.get("dimensions")
        cap = payload.get("cap")
        return (
            placeholder(payload.get("item_id"))
            and placeholder(payload.get("response_id"))
            and placeholder(payload.get("rubric_version"))
            and payload.get("criterion_assessment") == []
            and payload.get("atomic_errors") == []
            and payload.get("extra_penalties") == []
            and payload.get("result_status") == "incomplete"
            and payload.get("technical_summary") == ""
            and payload.get("review_flags") == []
            and payload.get("requires_human_review") is False
            and payload.get("human_review_reason") == ""
            and payload.get("run_validity") == "uncertain"
            and isinstance(score, dict)
            and score.get("final_score") == 0
            and score.get("raw_score") == 0
            and score.get("normalized_score_before_penalties") == 0
            and score.get("extra_penalty_total") == 0
            and score.get("score_after_penalties") == 0
            and score.get("applied_cap") is None
            and isinstance(cap, dict)
            and cap == {"applied": False, "value": None, "reason": ""}
            and isinstance(dimensions, dict)
            and set(dimensions) == {f"T{index}" for index in range(1, 9)}
            and all(
                isinstance(dimension, dict)
                and dimension.get("score") == 0
                and dimension.get("summary", "") == ""
                for dimension in dimensions.values()
            )
        )
    if kind == "private identity map":
        entries = payload.get("entries")
        return (
            placeholder(payload.get("campaign_id"))
            and placeholder(payload.get("batch_id"))
            and placeholder(payload.get("created_at"))
            and hashes_are_placeholders(payload)
            and isinstance(entries, list)
            and len(entries) == 1
            and isinstance(entries[0], dict)
            and placeholder(entries[0].get("anonymous_response_id"))
            and placeholder(entries[0].get("item_id"))
            and placeholder(entries[0].get("source_run_id"))
            and placeholder(entries[0].get("system_id"))
            and placeholder(entries[0].get("repetition_id"))
            and contains_placeholder(entries[0].get("source_response_path"))
            and contains_placeholder(entries[0].get("blind_input_path"))
            and contains_placeholder(entries[0].get("planned_judgment_path"))
            and entries[0].get("model_identity") == {"replace_with_private_metadata": True}
        )
    if kind == "operational blind-batch manifest":
        items = payload.get("item_artifacts")
        responses = payload.get("responses")
        return (
            placeholder(payload.get("campaign_id"))
            and placeholder(payload.get("batch_id"))
            and placeholder(payload.get("created_at"))
            and hashes_are_placeholders(payload)
            and isinstance(items, list)
            and len(items) == 1
            and isinstance(items[0], dict)
            and placeholder(items[0].get("item_id"))
            and contains_placeholder(items[0].get("item_path"))
            and contains_placeholder(items[0].get("rubric_path"))
            and contains_placeholder(items[0].get("reference_path"))
            and isinstance(responses, list)
            and len(responses) == 1
            and isinstance(responses[0], dict)
            and placeholder(responses[0].get("anonymous_response_id"))
            and placeholder(responses[0].get("item_id"))
            and contains_placeholder(responses[0].get("blind_input_path"))
            and contains_placeholder(responses[0].get("planned_judgment_path"))
        )
    if kind == "adjudication record":
        reviewer = payload.get("reviewer")
        trigger = payload.get("trigger")
        source_artifacts = payload.get("source_artifacts")
        decision = payload.get("decision")
        impact = payload.get("impact")
        reevaluation = payload.get("reevaluation")
        affected = payload.get("affected_response_ids")
        return (
            payload.get("decision_status") == "draft"
            and placeholder(payload.get("adjudication_id"))
            and placeholder(payload.get("campaign_id"))
            and placeholder(payload.get("batch_id"))
            and placeholder(payload.get("recorded_at"))
            and payload.get("supersedes_adjudication_id") is None
            and payload.get("supersedes_adjudication_sha256") is None
            and isinstance(reviewer, dict)
            and reviewer.get("human_confirmed") is False
            and placeholder(reviewer.get("reviewer_id"))
            and isinstance(trigger, dict)
            and contains_placeholder(trigger.get("summary"))
            and contains_placeholder(trigger.get("evidence"))
            and isinstance(source_artifacts, list)
            and len(source_artifacts) == 1
            and isinstance(source_artifacts[0], dict)
            and placeholder(source_artifacts[0].get("artifact_type"))
            and placeholder(source_artifacts[0].get("artifact_id"))
            and contains_placeholder(source_artifacts[0].get("path"))
            and isinstance(decision, dict)
            and decision.get("outcome") == "other"
            and contains_placeholder(decision.get("summary"))
            and contains_placeholder(decision.get("technical_rationale"))
            and isinstance(impact, dict)
            and impact == {
                "reference": {
                    "changed": False,
                    "previous_version": None,
                    "replacement_version": None,
                },
                "rubric": {
                    "changed": False,
                    "previous_version": None,
                    "replacement_version": None,
                },
                "response_validity": {"changed": False, "new_status": None},
                "scores": {"changed": False, "requires_recomputation": False},
            }
            and isinstance(affected, list)
            and len(affected) == 1
            and placeholder(affected[0])
            and isinstance(reevaluation, dict)
            and reevaluation.get("required") is False
            and reevaluation.get("scope") == "none"
            and contains_placeholder(reevaluation.get("reason"))
            and reevaluation.get("replacement_artifact_paths") == []
            and payload.get("superseded_artifacts") == []
            and payload.get("notes") == ""
            and hashes_are_placeholders(payload)
        )
    return False


def is_text_repository_path(path: str) -> bool:
    candidate = Path(path)
    return candidate.suffix.lower() in TEXT_SUFFIXES or candidate.name in TEXT_FILENAMES


def git_history_text_blobs(root: Path = ROOT) -> Iterator[tuple[str, str, str]]:
    """Yield ``(object id, historical path, UTF-8 text)`` for reachable blobs.

    Any path already forbidden by policy, especially ``.env``, is deliberately
    excluded before its blob is read. The path scan reports that artifact on its
    own, so inspecting potentially secret file contents is unnecessary.
    """
    listing = subprocess.run(
        ["git", "rev-list", "--objects", "--all"],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    if listing.returncode != 0:
        raise RuntimeError("unable to enumerate reachable Git objects")

    candidates: list[tuple[str, str]] = []
    object_ids: list[str] = []
    for line in listing.stdout.splitlines():
        object_id, separator, path = line.partition(" ")
        if (
            not separator
            or not is_text_repository_path(path)
            or private_path_reason(path) is not None
        ):
            continue
        candidates.append((object_id, path))
        object_ids.append(object_id)

    unique_ids = list(dict.fromkeys(object_ids))
    if not unique_ids:
        return
    metadata = subprocess.run(
        ["git", "cat-file", "--batch-check=%(objectname) %(objecttype) %(objectsize)"],
        cwd=root,
        input="\n".join(unique_ids) + "\n",
        text=True,
        capture_output=True,
        check=False,
    )
    if metadata.returncode != 0:
        raise RuntimeError("unable to inspect reachable Git object metadata")
    eligible: set[str] = set()
    oversized: set[str] = set()
    for line in metadata.stdout.splitlines():
        fields = line.split()
        if len(fields) == 3 and fields[1] == "blob":
            try:
                size = int(fields[2])
            except ValueError:
                continue
            if size <= MAX_HISTORY_TEXT_BLOB_BYTES:
                eligible.add(fields[0])
            else:
                oversized.add(fields[0])
    if oversized:
        first_path = next(path for object_id, path in candidates if object_id in oversized)
        raise RuntimeError(
            "reachable text blob exceeds the safe scan limit at " + first_path
        )

    cache: dict[str, str | None] = {}
    for object_id, path in candidates:
        if object_id not in eligible:
            continue
        if object_id not in cache:
            content = subprocess.run(
                ["git", "cat-file", "blob", object_id],
                cwd=root,
                capture_output=True,
                check=False,
            )
            if content.returncode != 0:
                raise RuntimeError("unable to read a reachable Git text blob")
            try:
                cache[object_id] = content.stdout.decode("utf-8")
            except UnicodeDecodeError:
                cache[object_id] = None
        text = cache[object_id]
        if text is not None:
            yield object_id, path, text


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict", action="store_true", help="also require the publication checklist to be complete")
    args = parser.parse_args()
    errors: list[str] = []

    forbidden_top_level = {name.casefold() for name in FORBIDDEN_TOP_LEVEL}
    for path in sorted(ROOT.iterdir(), key=lambda candidate: candidate.name.casefold()):
        if path.name.casefold() in forbidden_top_level:
            errors.append(f"forbidden top-level private artifact: {path.name}")
    for required in sorted(REQUIRED):
        if not (ROOT / required).is_file():
            errors.append(f"required file missing: {required}")

    # Include untracked files in the local release audit. A forbidden file such
    # as .env is rejected by path and is never opened by the content scanner.
    for path in ROOT.rglob("*"):
        repository_parts = set(path.relative_to(ROOT).parts)
        if repository_parts & IGNORED_LOCAL_PARTS:
            continue
        if path.is_file() or path.is_symlink():
            reason = private_path_reason(relative(path))
            if reason:
                errors.append(f"working-tree path {reason}: {relative(path)}")

    try:
        tracked_paths = git_paths("ls-files")
        historical_paths = git_paths("log", "--all", "--format=", "--name-only")
    except RuntimeError as exc:
        errors.append(f"Git path scan failed closed: {exc}")
        tracked_paths = []
        historical_paths = []
    for candidate in tracked_paths:
        reason = private_path_reason(candidate)
        if reason:
            errors.append(f"tracked path {reason}: {candidate}")
    for candidate in historical_paths:
        reason = private_path_reason(candidate)
        if reason:
            errors.append(f"Git history path {reason}: {candidate}")

    template_json = {
        path.relative_to(ROOT).as_posix()
        for path in (ROOT / "benchmark-toolkit/templates").rglob("*.json")
    }
    expected_templates = {
        "benchmark-toolkit/templates/adjudication.template.json",
        "benchmark-toolkit/templates/aggregation-config.template.json",
        "benchmark-toolkit/templates/blind-batch-manifest.template.json",
        "benchmark-toolkit/templates/identity-map.template.json",
        "benchmark-toolkit/templates/judgment.template.json",
        "benchmark-toolkit/templates/rubric.template.json",
    }
    if template_json != expected_templates:
        errors.append(
            "benchmark-toolkit/templates/ must contain only the approved blank templates; "
            f"expected {sorted(expected_templates)}, found {sorted(template_json)}"
        )

    figures_dir = ROOT / "uniaibench/analysis/figures"
    actual_figures = {
        path.relative_to(figures_dir).as_posix()
        for path in figures_dir.rglob("*") if path.is_file()
    } if figures_dir.is_dir() else set()
    if actual_figures != EXPECTED_ANALYSIS_FIGURES:
        errors.append(
            "uniaibench/analysis/figures must contain only the current English website figure set; "
            f"expected {sorted(EXPECTED_ANALYSIS_FIGURES)}, found {sorted(actual_figures)}"
        )

    paper_figures_dir = ROOT / "uniaibench/paper/figures"
    actual_paper_figures = {
        path.name for path in paper_figures_dir.iterdir() if path.is_file()
    } if paper_figures_dir.is_dir() else set()
    if actual_paper_figures != EXPECTED_PAPER_FIGURES:
        errors.append(
            "uniaibench/paper/figures must contain only manuscript figures and current English supplements; "
            f"expected {sorted(EXPECTED_PAPER_FIGURES)}, found {sorted(actual_paper_figures)}"
        )

    exercise_files = list(ROOT.rglob("esercizio_*.txt")) + list(ROOT.rglob("exercise_[0-9]*.txt"))
    if exercise_files:
        errors.append("source exercise text files are present")

    for path in text_files():
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for finding in sensitive_text_findings(text):
            errors.append(f"{finding} in {relative(path)}")
        if path.suffix.lower() == ".md":
            check_markdown_links(path, text, errors)
        if path.suffix.lower() == ".json":
            try:
                payload = json.loads(text)
            except json.JSONDecodeError as exc:
                errors.append(f"invalid JSON in {relative(path)}: {exc}")
            else:
                kind = private_json_artifact_kind(payload)
                if kind and not approved_blank_template(relative(path), kind, payload):
                    errors.append(f"private {kind} JSON artifact in {relative(path)}")

    try:
        history_blobs = git_history_text_blobs()
        for object_id, historical_path, text in history_blobs:
            label = f"Git history blob {object_id[:12]} at {historical_path}"
            for finding in sensitive_text_findings(text):
                errors.append(f"{finding} in {label}")
            if Path(historical_path).suffix.lower() != ".json":
                continue
            try:
                payload = json.loads(text)
            except json.JSONDecodeError:
                continue
            kind = private_json_artifact_kind(payload)
            if kind and not approved_blank_template(historical_path, kind, payload):
                errors.append(f"private {kind} JSON artifact in {label}")
    except RuntimeError as exc:
        errors.append(f"Git history content scan failed closed: {exc}")

    sensitive_headers = {"email", "phone", "person_name", "student_id", "user_id"}
    for path in (candidate for candidate in text_files() if candidate.suffix.lower() == ".csv"):
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
        for marker in ("SEMANTIC_REVIEW_STATUS: PASSED", "HUMAN_RIGHTS_STATUS: CONFIRMED"):
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
        for error in sorted(set(errors)):
            print(f"ERROR: {error}")
        return 1
    print("OK: publication repository contains no detected private artifacts or credentials")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
