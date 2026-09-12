#!/usr/bin/env python3
"""Asynchronous, resumable multi-provider benchmark reference harness."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib.metadata
import json
import os
import random
import re
import sys
import time
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from dotenv import load_dotenv


TOOLKIT_ROOT = Path(__file__).resolve().parents[1]
if str(TOOLKIT_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLKIT_ROOT))

from tools.schema_validation import validate_json_schema  # noqa: E402


ROOT = TOOLKIT_ROOT
KEY_BY_PROVIDER = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "google": "GEMINI_API_KEY",
    "kimi": "MOONSHOT_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
    "xai": "XAI_API_KEY",
}
DEFAULT_ENDPOINTS = {
    "openai": "https://api.openai.com/v1/responses",
    "anthropic": "https://api.anthropic.com/v1/messages",
    "google": "Google Gen AI generateContent",
    "kimi": "https://api.moonshot.ai/v1/chat/completions",
    "deepseek": "https://api.deepseek.com/chat/completions",
    "xai": "https://api.x.ai/v1/responses",
}
SDK_DISTRIBUTIONS = {
    "openai": "openai",
    "anthropic": "anthropic",
    "google": "google-genai",
    "kimi": "openai",
    "deepseek": "openai",
    "xai": "openai",
}


@dataclass(frozen=True)
class Job:
    dataset_item_prefix: str
    provider: str
    display_name: str
    model_id: str
    output_slug: str
    model_mode: str
    max_output_tokens: int
    reasoning_effort: Optional[str]
    thinking_level: Optional[str]
    thinking_mode: Optional[str]
    pricing_usd_per_million: Optional[Dict[str, float]]
    endpoint: str
    year: int
    session: str
    item_number: int
    item_file: Path
    run_number: int

    @property
    def item_id(self) -> str:
        return f"item_{self.item_number}"

    @property
    def dataset_item_id(self) -> str:
        return f"{self.dataset_item_prefix}_{self.year}_{self.session}_{self.item_id}"

    @property
    def run_id(self) -> str:
        return f"{self.dataset_item_id}_{self.provider}_{self.output_slug}_r{self.run_number:02d}"


@dataclass
class ProviderResult:
    answer: str
    raw_response: Dict[str, Any]
    response_id: Optional[str]
    response_model_id: Optional[str]
    finish_reason: Optional[str]
    tokens: Dict[str, Any]
    billing: Dict[str, Any]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json_atomic(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    temporary.replace(path)


def write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        handle.write(text)
        if text and not text.endswith("\n"):
            handle.write("\n")
    temporary.replace(path)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_config(config: Dict[str, Any]) -> None:
    schema = read_json(TOOLKIT_ROOT / "schemas" / "benchmark-config.schema.json")
    validate_json_schema(config, schema)
    for session in config["sessions"]:
        require_safe_path_component(str(session), "session")
    glob_pattern = str(config["item_filename_glob"])
    if Path(glob_pattern).name != glob_pattern or "/" in glob_pattern or "\\" in glob_pattern:
        raise ValueError("item_filename_glob must be a filename pattern, not a path")
    try:
        item_expression = re.compile(str(config["item_filename_regex"]))
    except re.error as exc:
        raise ValueError(f"invalid item_filename_regex: {exc}") from exc
    if item_expression.groups < 1:
        raise ValueError("item_filename_regex must capture the positive item number in group 1")

    destinations: set[tuple[str, str]] = set()
    for model in config["models"]:
        output_slug = str(model.get("output_slug", model["model_id"]))
        require_safe_path_component(output_slug, "model output_slug")
        destination = (str(model["provider"]), output_slug)
        if destination in destinations:
            raise ValueError(
                "models must have unique (provider, output_slug) output destinations: "
                f"{destination}"
            )
        destinations.add(destination)

    if contains_unresolved_placeholder(config):
        raise ValueError("configuration contains unresolved <PLACEHOLDER> values")
    try:
        date.fromisoformat(str(config["access_date"]))
    except ValueError as exc:
        raise ValueError("access_date must use the ISO YYYY-MM-DD format") from exc


def require_safe_path_component(value: str, label: str) -> None:
    if (
        not value
        or value in {".", ".."}
        or Path(value).name != value
        or "/" in value
        or "\\" in value
        or "\x00" in value
    ):
        raise ValueError(f"{label} must be one safe path component: {value!r}")


def contains_unresolved_placeholder(value: Any) -> bool:
    if isinstance(value, str):
        return re.fullmatch(r"<[^<>]+>", value.strip()) is not None
    if isinstance(value, list):
        return any(contains_unresolved_placeholder(item) for item in value)
    if isinstance(value, dict):
        return any(contains_unresolved_placeholder(item) for item in value.values())
    return False


def config_directory(config: Dict[str, Any]) -> Path:
    """Return the private campaign directory used to resolve relative paths."""

    return Path(config.get("_runtime_config_directory", ROOT)).resolve()


def resolve_config_path(config: Dict[str, Any], field: str) -> Path:
    """Resolve a declared path relative to the configuration file."""

    declared = Path(str(config[field])).expanduser()
    if declared.is_absolute():
        return declared.resolve()
    return (config_directory(config) / declared).resolve()


def recorded_artifact_path(config: Dict[str, Any], path: Path) -> str:
    """Record a path without embedding a machine-specific absolute prefix."""

    return Path(os.path.relpath(path.resolve(), config_directory(config))).as_posix()


def sdk_metadata(provider: str) -> Dict[str, Optional[str]]:
    distribution = SDK_DISTRIBUTIONS[provider]
    try:
        version: Optional[str] = importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError:
        version = None
    return {"distribution": distribution, "version": version}


def load_prompt_template(path: Path) -> str:
    document = path.read_text(encoding="utf-8")
    headings = ("## Prompt to send to the model", "## Prompt da inviare al modello")
    heading = next((candidate for candidate in headings if candidate in document), None)
    if heading is None:
        expected = "' or '".join(headings)
        raise ValueError(f"Prompt section '{expected}' not found in {path}")
    body = document[document.find(heading) + len(heading):].strip()
    fenced = re.search(r"```(?:text)?\s*\n(.*?)\n```", body, flags=re.DOTALL)
    return (fenced.group(1) if fenced else body).strip()


def benchmark_year(config: Dict[str, Any]) -> int:
    return int(config.get("assessment_metadata", {}).get("year", 2025))


def dataset_item_prefix(config: Dict[str, Any]) -> str:
    prefix = str(config.get("dataset_item_prefix", "benchmark")).strip()
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", prefix):
        raise ValueError(f"invalid dataset_item_prefix: {prefix!r}")
    return prefix


def session_directory(config: Dict[str, Any], dataset_root: Path, year: int, session: str) -> Path:
    template = str(config.get("session_directory_template", "sessions/{session}"))
    expected = (dataset_root / template.format(year=year, session=session)).resolve()
    try:
        expected.relative_to(dataset_root.resolve())
    except ValueError:
        raise ValueError(
            f"session_directory_template escapes dataset_root for session {session!r}"
        )
    if not expected.is_dir():
        raise FileNotFoundError(f"session directory not found: {expected}")
    return expected


def discover_items(config: Dict[str, Any]) -> List[Tuple[str, int, Path]]:
    dataset_root = resolve_config_path(config, "dataset_root")
    year = benchmark_year(config)
    selected_numbers = config.get("item_numbers")
    if selected_numbers is not None:
        if (
            not isinstance(selected_numbers, list)
            or not selected_numbers
            or not all(isinstance(number, int) and number > 0 for number in selected_numbers)
            or len(selected_numbers) != len(set(selected_numbers))
        ):
            raise ValueError("item_numbers must be a non-empty list of distinct positive integers")
        selected_numbers = set(selected_numbers)
    items: List[Tuple[str, int, Path]] = []
    for session in config["sessions"]:
        directory = session_directory(config, dataset_root, year, session)
        pattern = str(config.get("item_filename_glob", "item_*.txt"))
        expression = re.compile(str(config.get("item_filename_regex", r"item_(\d+)\.txt")))
        numbered: List[Tuple[int, Path]] = []
        for path in directory.glob(pattern):
            match = expression.fullmatch(path.name)
            if match is None:
                continue
            if not path.is_file():
                raise ValueError(f"matched item is not a regular file: {path}")
            resolved_path = path.resolve()
            try:
                resolved_path.relative_to(dataset_root.resolve())
            except ValueError:
                raise ValueError(f"matched item escapes dataset_root: {path}")
            numbered.append((int(match.group(1)), resolved_path))
        discovered_numbers = [number for number, _ in numbered]
        if any(number < 1 for number in discovered_numbers):
            raise ValueError(f"item numbers must be positive in {directory}")
        if len(discovered_numbers) != len(set(discovered_numbers)):
            raise ValueError(f"item_filename_regex produces duplicate item numbers in {directory}")
        files = [path for _, path in sorted(numbered)]
        expected_count = int(config.get("expected_items_per_session", 3))
        if len(files) != expected_count:
            raise ValueError(f"Expected {expected_count} items in {directory}, found {len(files)}")
        if selected_numbers is not None:
            missing_for_session = selected_numbers - set(discovered_numbers)
            if missing_for_session:
                missing = ", ".join(str(number) for number in sorted(missing_for_session))
                raise ValueError(f"selected items not found in session {session}: {missing}")
        for path in files:
            match = expression.fullmatch(path.name)
            assert match is not None
            number = int(match.group(1))
            if selected_numbers is None or number in selected_numbers:
                items.append((session, number, path))
    return items


def build_jobs(config: Dict[str, Any], providers: Optional[Sequence[str]] = None) -> List[Job]:
    requested = set(providers or [])
    models = [m for m in config["models"] if not requested or m["provider"] in requested]
    unknown = requested - {m["provider"] for m in config["models"]}
    if unknown:
        raise ValueError(f"unknown providers: {', '.join(sorted(unknown))}")

    jobs: List[Job] = []
    year = benchmark_year(config)
    item_prefix = dataset_item_prefix(config)
    discovered = discover_items(config)
    for session, number, item_file in discovered:
        for model in models:
            for run_number in range(1, int(config["repetitions"]) + 1):
                jobs.append(
                    Job(
                        dataset_item_prefix=item_prefix,
                        provider=model["provider"],
                        display_name=model["display_name"],
                        model_id=model["model_id"],
                        output_slug=model.get("output_slug", model["model_id"]),
                        model_mode=model.get("model_mode", "not available"),
                        max_output_tokens=int(model["max_output_tokens"]),
                        reasoning_effort=model.get("reasoning_effort"),
                        thinking_level=model.get("thinking_level"),
                        thinking_mode=model.get("thinking_mode"),
                        pricing_usd_per_million=model.get("pricing_usd_per_million"),
                        endpoint=str(model.get("endpoint", DEFAULT_ENDPOINTS[model["provider"]])),
                        year=year,
                        session=session,
                        item_number=number,
                        item_file=item_file,
                        run_number=run_number,
                    )
                )
    random.Random(int(config["shuffle_seed"])).shuffle(jobs)
    return jobs


def run_directory(config: Dict[str, Any], job: Job) -> Path:
    return (
        resolve_config_path(config, "output_root")
        / str(job.year)
        / job.session
        / job.item_id
        / job.provider
        / job.output_slug
        / f"run_{job.run_number:02d}"
    )


def completed(config: Dict[str, Any], job: Job) -> bool:
    metadata_path = run_directory(config, job) / "metadata.json"
    if not metadata_path.exists():
        return False
    try:
        return read_json(metadata_path).get("execution", {}).get("status") == "completed"
    except (OSError, ValueError, json.JSONDecodeError):
        return False


def prompt_values(config: Dict[str, Any], job: Job, problem_text: str) -> Dict[str, str]:
    assessment = config.get("assessment_metadata", {})
    return {
        "run_id": job.run_id,
        "benchmark_id": str(config["benchmark_id"]),
        "assessment_name": str(assessment.get("name", "not available")),
        "assessment_context": str(assessment.get("context", "not available")),
        "domain": str(assessment.get("domain", "not available")),
        "session": job.session,
        "item_id": job.item_id,
        "subject": str(assessment.get("subject", "not available")),
        "topic": str(assessment.get("topic", "not available")),
        "model_name": job.display_name,
        "model_version": job.model_id,
        "provider": job.provider,
        "model_mode": job.model_mode,
        "source_file": recorded_artifact_path(config, job.item_file),
        "prompt_id": str(config["prompt_id"]),
        "start_timestamp": "not available",
        "end_timestamp": "not available",
        "elapsed_time": "not available",
        "reasoning_time": "not available",
        "input_tokens": "not available",
        "reasoning_tokens": "not available",
        "output_tokens": "not available",
        "temperature": "not available",
        "top_p": "not available",
        "seed": "not available",
        "max_output_tokens": str(job.max_output_tokens),
        "run_number": str(job.run_number),
        "allowed_tools": str(assessment.get("allowed_tools", "none")),
        "web_allowed": str(assessment.get("web_allowed", "no")),
        "allowed_materials": str(assessment.get("allowed_materials", "none")),
        "problem_text": problem_text.strip(),
    }


def render_prompt(template: str, values: Dict[str, str]) -> str:
    rendered = template
    for key, value in values.items():
        rendered = rendered.replace("{{" + key + "}}", value)
    rendered = re.sub(r"\{\{[^{}]+\}\}", "not available", rendered)
    return rendered


def snapshot_campaign(config: Dict[str, Any]) -> None:
    """Persist the exact non-secret configuration and prompt before API calls."""

    campaign_dir = resolve_config_path(config, "output_root") / "_campaign"
    public_config = {key: value for key, value in config.items() if not key.startswith("_runtime_")}
    prompt_path = resolve_config_path(config, "prompt_file")
    write_json_atomic(campaign_dir / "config.json", public_config)
    write_text_atomic(campaign_dir / "prompt-template.md", prompt_path.read_text(encoding="utf-8"))
    write_json_atomic(
        campaign_dir / "manifest.json",
        {
            "benchmark_id": config["benchmark_id"],
            "access_date": config["access_date"],
            "configuration_sha256": config["_runtime_config_sha256"],
            "prompt_sha256": sha256_file(prompt_path),
            "created_at": utc_now(),
        },
    )


def require_keys(jobs: Sequence[Job]) -> None:
    missing = sorted(
        env_name
        for provider, env_name in KEY_BY_PROVIDER.items()
        if any(job.provider == provider for job in jobs) and not os.getenv(env_name)
    )
    if missing:
        raise RuntimeError(
            "Missing API keys: " + ", ".join(missing) + ". Copy .env.example to .env and fill it locally."
        )


def as_json_dict(value: Any) -> Dict[str, Any]:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json", exclude_none=False)
    if hasattr(value, "to_dict"):
        return value.to_dict()
    raise TypeError(f"response is not serializable: {type(value)!r}")


class Providers:
    def __init__(self, timeout_seconds: float, provider_names: Sequence[str]) -> None:
        requested = set(provider_names)
        self.openai = None
        self.anthropic = None
        self.google = None
        self.kimi = None
        self.deepseek = None
        self.xai = None
        if "openai" in requested:
            from openai import AsyncOpenAI

            self.openai = AsyncOpenAI(
                api_key=os.getenv("OPENAI_API_KEY"), timeout=timeout_seconds, max_retries=0
            )
        if "anthropic" in requested:
            from anthropic import AsyncAnthropic

            self.anthropic = AsyncAnthropic(
                api_key=os.getenv("ANTHROPIC_API_KEY"), timeout=timeout_seconds, max_retries=0
            )
        if "google" in requested:
            from google import genai

            self.google = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        if requested & {"kimi", "deepseek", "xai"}:
            from openai import AsyncOpenAI

            if "kimi" in requested:
                self.kimi = AsyncOpenAI(
                    api_key=os.getenv("MOONSHOT_API_KEY"),
                    base_url="https://api.moonshot.ai/v1",
                    timeout=timeout_seconds,
                    max_retries=0,
                )
            if "deepseek" in requested:
                self.deepseek = AsyncOpenAI(
                    api_key=os.getenv("DEEPSEEK_API_KEY"),
                    base_url="https://api.deepseek.com",
                    timeout=timeout_seconds,
                    max_retries=0,
                )
            if "xai" in requested:
                self.xai = AsyncOpenAI(
                    api_key=os.getenv("XAI_API_KEY"),
                    base_url="https://api.x.ai/v1",
                    timeout=timeout_seconds,
                    max_retries=0,
                )
        self.timeout_seconds = timeout_seconds

    async def close(self) -> None:
        if self.openai is not None:
            await self.openai.close()
        if self.anthropic is not None:
            await self.anthropic.close()
        if self.google is not None:
            await self.google.aio.aclose()
        for client in (self.kimi, self.deepseek, self.xai):
            if client is not None:
                await client.close()

    async def generate(self, job: Job, prompt: str) -> ProviderResult:
        if job.provider == "openai":
            return await self._openai(job, prompt)
        if job.provider == "anthropic":
            return await self._anthropic(job, prompt)
        if job.provider == "google":
            return await self._google(job, prompt)
        if job.provider in {"kimi", "deepseek"}:
            return await self._openai_compatible_chat(job, prompt)
        if job.provider == "xai":
            return await self._xai(job, prompt)
        raise ValueError(f"unsupported provider: {job.provider}")

    async def _openai(self, job: Job, prompt: str) -> ProviderResult:
        kwargs: Dict[str, Any] = {
            "model": job.model_id,
            "input": prompt,
            "max_output_tokens": job.max_output_tokens,
            "store": False,
        }
        if job.reasoning_effort:
            kwargs["reasoning"] = {"effort": job.reasoning_effort}
        response = await self.openai.responses.create(**kwargs)
        usage = response.usage
        details = getattr(usage, "output_tokens_details", None) if usage else None
        return ProviderResult(
            answer=response.output_text or "",
            raw_response=as_json_dict(response),
            response_id=getattr(response, "id", None),
            response_model_id=getattr(response, "model", None),
            finish_reason=getattr(response, "status", None),
            tokens={
                "input": getattr(usage, "input_tokens", None),
                "reasoning_provider_reported": getattr(details, "reasoning_tokens", None),
                "output": getattr(usage, "output_tokens", None),
                "total": getattr(usage, "total_tokens", None),
            },
            billing={},
        )

    async def _anthropic(self, job: Job, prompt: str) -> ProviderResult:
        kwargs: Dict[str, Any] = {
            "model": job.model_id,
            "max_tokens": job.max_output_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if job.reasoning_effort:
            kwargs["thinking"] = {"type": "adaptive", "display": "omitted"}
            kwargs["output_config"] = {"effort": job.reasoning_effort}
        response = await self.anthropic.messages.create(**kwargs)
        answer = "\n".join(block.text for block in response.content if getattr(block, "type", None) == "text")
        usage = response.usage
        details = getattr(usage, "output_tokens_details", None)
        input_tokens = (
            (getattr(usage, "input_tokens", 0) or 0)
            + (getattr(usage, "cache_creation_input_tokens", 0) or 0)
            + (getattr(usage, "cache_read_input_tokens", 0) or 0)
        )
        output_tokens = getattr(usage, "output_tokens", None)
        return ProviderResult(
            answer=answer,
            raw_response=as_json_dict(response),
            response_id=getattr(response, "id", None),
            response_model_id=getattr(response, "model", None),
            finish_reason=getattr(response, "stop_reason", None),
            tokens={
                "input": input_tokens,
                "reasoning_provider_reported": getattr(details, "thinking_tokens", None),
                "output": output_tokens,
                "total": input_tokens + output_tokens if output_tokens is not None else None,
            },
            billing={},
        )

    async def _google(self, job: Job, prompt: str) -> ProviderResult:
        from google.genai import types

        thinking_config = (
            types.ThinkingConfig(thinking_level=job.thinking_level)
            if job.thinking_level
            else None
        )
        config = types.GenerateContentConfig(
            max_output_tokens=job.max_output_tokens,
            thinking_config=thinking_config,
        )
        response = await asyncio.wait_for(
            self.google.aio.models.generate_content(model=job.model_id, contents=prompt, config=config),
            timeout=self.timeout_seconds,
        )
        usage = response.usage_metadata
        finish_reason = None
        if response.candidates:
            reason = response.candidates[0].finish_reason
            finish_reason = getattr(reason, "value", str(reason)) if reason is not None else None
        return ProviderResult(
            answer=response.text or "",
            raw_response=as_json_dict(response),
            response_id=getattr(response, "response_id", None),
            response_model_id=getattr(response, "model_version", None),
            finish_reason=finish_reason,
            tokens={
                "input": getattr(usage, "prompt_token_count", None),
                "reasoning_provider_reported": getattr(usage, "thoughts_token_count", None),
                "output": getattr(usage, "candidates_token_count", None),
                "total": getattr(usage, "total_token_count", None),
            },
            billing={},
        )

    async def _openai_compatible_chat(self, job: Job, prompt: str) -> ProviderResult:
        client = self.kimi if job.provider == "kimi" else self.deepseek
        kwargs: Dict[str, Any] = {
            "model": job.model_id,
            "messages": [{"role": "user", "content": prompt}],
        }
        if job.provider == "kimi":
            kwargs["max_completion_tokens"] = job.max_output_tokens
        else:
            kwargs["max_tokens"] = job.max_output_tokens
        if job.reasoning_effort:
            kwargs["reasoning_effort"] = job.reasoning_effort
        if job.provider == "deepseek" and job.thinking_mode:
            kwargs["extra_body"] = {"thinking": {"type": job.thinking_mode}}

        response = await client.chat.completions.create(**kwargs)
        choice = response.choices[0] if response.choices else None
        message = getattr(choice, "message", None)
        answer = getattr(message, "content", None) or ""
        usage = response.usage
        prompt_details = getattr(usage, "prompt_tokens_details", None) if usage else None
        completion_details = getattr(usage, "completion_tokens_details", None) if usage else None
        cached_tokens = getattr(prompt_details, "cached_tokens", None)
        if cached_tokens is None and usage is not None:
            cached_tokens = getattr(usage, "cached_tokens", None)
        if cached_tokens is None and usage is not None:
            cached_tokens = getattr(usage, "prompt_cache_hit_tokens", None)
        return ProviderResult(
            answer=answer,
            raw_response=as_json_dict(response),
            response_id=getattr(response, "id", None),
            response_model_id=getattr(response, "model", None),
            finish_reason=getattr(choice, "finish_reason", None),
            tokens={
                "input": getattr(usage, "prompt_tokens", None),
                "input_cached": cached_tokens,
                "input_cache_miss": getattr(usage, "prompt_cache_miss_tokens", None),
                "reasoning_provider_reported": getattr(completion_details, "reasoning_tokens", None),
                "output": getattr(usage, "completion_tokens", None),
                "total": getattr(usage, "total_tokens", None),
            },
            billing={},
        )

    async def _xai(self, job: Job, prompt: str) -> ProviderResult:
        kwargs: Dict[str, Any] = {
            "model": job.model_id,
            "input": prompt,
            "max_output_tokens": job.max_output_tokens,
        }
        if job.reasoning_effort:
            kwargs["reasoning"] = {"effort": job.reasoning_effort}
        response = await self.xai.responses.create(**kwargs)
        raw_response = as_json_dict(response)
        usage = response.usage
        details = getattr(usage, "output_tokens_details", None) if usage else None
        input_details = getattr(usage, "input_tokens_details", None) if usage else None
        raw_usage = raw_response.get("usage") or {}
        cost_ticks = getattr(usage, "cost_in_usd_ticks", None) if usage else None
        if cost_ticks is None:
            cost_ticks = raw_usage.get("cost_in_usd_ticks")
        billing: Dict[str, Any] = {}
        if cost_ticks is not None:
            billing = {
                "cost_in_usd_ticks": cost_ticks,
                "cost_usd_provider_reported": cost_ticks / 10_000_000_000,
            }
        return ProviderResult(
            answer=response.output_text or "",
            raw_response=raw_response,
            response_id=getattr(response, "id", None),
            response_model_id=getattr(response, "model", None),
            finish_reason=getattr(response, "status", None),
            tokens={
                "input": getattr(usage, "input_tokens", None),
                "input_cached": getattr(input_details, "cached_tokens", None),
                "reasoning_provider_reported": getattr(details, "reasoning_tokens", None),
                "output": getattr(usage, "output_tokens", None),
                "total": getattr(usage, "total_tokens", None),
            },
            billing=billing,
        )


def retryable(exc: BaseException) -> bool:
    status = getattr(exc, "status_code", None)
    if status is not None:
        return status == 429 or 500 <= status < 600
    name = type(exc).__name__.lower()
    return any(marker in name for marker in ("timeout", "connection", "rate", "server"))


def completion_error(job: Job, result: ProviderResult) -> Optional[str]:
    if not result.answer.strip():
        return "empty textual response"
    accepted = {
        "openai": {"completed"},
        "anthropic": {"end_turn", "stop_sequence"},
        "google": {"STOP"},
        "kimi": {"stop"},
        "deepseek": {"stop"},
        "xai": {"completed"},
    }
    if result.finish_reason not in accepted.get(job.provider, set()):
        return f"incomplete response: finish_reason={result.finish_reason!r}"
    return None


def billing_metadata(job: Job, result: ProviderResult) -> Dict[str, Any]:
    billing = dict(result.billing)
    billing["pricing_usd_per_million"] = job.pricing_usd_per_million
    if job.pricing_usd_per_million:
        input_tokens = result.tokens.get("input")
        output_tokens = result.tokens.get("output")
        input_rate = job.pricing_usd_per_million.get("input")
        output_rate = job.pricing_usd_per_million.get("output")
        if None not in (input_tokens, output_tokens, input_rate, output_rate):
            billing["estimated_cost_usd_from_tokens"] = (
                input_tokens * input_rate + output_tokens * output_rate
            ) / 1_000_000
            billing["estimate_assumes_uncached_input_rate"] = True
    return billing


def failure_metadata(config: Dict[str, Any], job: Job, prompt_hash: str, started_at: str, error: str, attempts: int) -> Dict[str, Any]:
    return {
        "benchmark_id": config["benchmark_id"],
        "configuration": {
            "path": config["_runtime_config_path"],
            "sha256": config["_runtime_config_sha256"],
            "access_date": config["access_date"],
        },
        "run_id": job.run_id,
        "dataset_item_id": job.dataset_item_id,
        "model": {
            "display_name": job.display_name,
            "provider": job.provider,
            "api_model_id": job.model_id,
            "output_slug": job.output_slug,
            "api_response_model_id": None,
            "mode": job.model_mode,
            "endpoint": job.endpoint,
            "sdk": sdk_metadata(job.provider),
        },
        "prompt": {
            "prompt_id": config["prompt_id"],
            "prompt_hash": prompt_hash,
            "language": config["prompt_language"],
        },
        "generation": {
            "reasoning_effort": job.reasoning_effort,
            "thinking_level": job.thinking_level,
            "thinking_mode": job.thinking_mode,
            "max_output_tokens": job.max_output_tokens,
            "run_number": job.run_number,
        },
        "tokens": {},
        "billing": {"pricing_usd_per_million": job.pricing_usd_per_million},
        "timing": {"started_at": started_at, "completed_at": utc_now()},
        "execution": {"status": "failed", "attempt_count": attempts, "error": error},
    }


async def execute_job(
    config: Dict[str, Any],
    job: Job,
    prompt_template: str,
    providers: Providers,
    global_semaphore: asyncio.Semaphore,
    provider_semaphore: asyncio.Semaphore,
) -> str:
    destination = run_directory(config, job)
    source_files = (job.item_file,)
    problem_text = job.item_file.read_text(encoding="utf-8")
    prompt = render_prompt(prompt_template, prompt_values(config, job, problem_text))
    prompt_hash = sha256_text(prompt)
    write_text_atomic(destination / "prompt.txt", prompt)

    max_attempts = int(config["max_attempts"])
    base_delay = float(config["retry_base_seconds"])
    started_at: Optional[str] = None
    monotonic_start: Optional[float] = None
    last_error = ""

    for attempt in range(1, max_attempts + 1):
        try:
            async with provider_semaphore, global_semaphore:
                if started_at is None:
                    started_at = utc_now()
                    monotonic_start = time.monotonic()
                result = await providers.generate(job, prompt)
            completed_at = utc_now()
            assert monotonic_start is not None
            elapsed = time.monotonic() - monotonic_start
            write_text_atomic(destination / "answer.txt", result.answer)
            write_json_atomic(destination / "raw_response.json", result.raw_response)
            validation_error = completion_error(job, result)
            execution_status = "failed" if validation_error else "completed"
            metadata = {
                "benchmark_id": config["benchmark_id"],
                "configuration": {
                    "path": config["_runtime_config_path"],
                    "sha256": config["_runtime_config_sha256"],
                    "access_date": config["access_date"],
                },
                "run_id": job.run_id,
                "dataset_item_id": job.dataset_item_id,
                "assessment": {
                    "year": job.year,
                    "session": job.session,
                    "item_id": job.item_id,
                    "task_unit": "item",
                    "domain": str(config.get("assessment_metadata", {}).get("domain", "not available")),
                    "subject": str(config.get("assessment_metadata", {}).get("subject", "not available")),
                    "source_file": recorded_artifact_path(config, job.item_file),
                    "source_files": [recorded_artifact_path(config, path) for path in source_files],
                    "source_sha256": [sha256_file(path) for path in source_files],
                },
                "model": {
                    "display_name": job.display_name,
                    "provider": job.provider,
                    "api_model_id": job.model_id,
                    "output_slug": job.output_slug,
                    "api_response_model_id": result.response_model_id,
                    "mode": job.model_mode,
                    "endpoint": job.endpoint,
                    "sdk": sdk_metadata(job.provider),
                },
                "prompt": {
                    "prompt_id": config["prompt_id"],
                    "prompt_hash": prompt_hash,
                    "language": config["prompt_language"],
                    "input_format": "text",
                },
                "generation": {
                    "reasoning_effort": job.reasoning_effort,
                    "thinking_level": job.thinking_level,
                    "thinking_mode": job.thinking_mode,
                    "max_output_tokens": job.max_output_tokens,
                    "run_number": job.run_number,
                    "temperature": None,
                    "top_p": None,
                    "seed": None,
                },
                "timing": {
                    "started_at": started_at,
                    "completed_at": completed_at,
                    "elapsed_seconds": round(elapsed, 6),
                },
                "tokens": result.tokens,
                "billing": billing_metadata(job, result),
                "tools": {
                    "allowed": config.get("assessment_metadata", {}).get("allowed_tools", []),
                    "web_allowed": bool(config.get("assessment_metadata", {}).get("web_allowed", False)),
                },
                "execution": {
                    "status": execution_status,
                    "attempt_count": attempt,
                    "retry_count": attempt - 1,
                    "response_id": result.response_id,
                    "finish_reason": result.finish_reason,
                    "error": validation_error,
                    "raw_response_file": "raw_response.json",
                    "response_text_sha256": sha256_text(result.answer),
                    "raw_response_sha256": sha256_file(destination / "raw_response.json"),
                },
            }
            write_json_atomic(destination / "metadata.json", metadata)
            return execution_status
        except Exception as exc:  # Errors are recorded without including credentials.
            last_error = f"{type(exc).__name__}: {exc}"
            if attempt >= max_attempts or not retryable(exc):
                effective_started_at = started_at or utc_now()
                write_json_atomic(
                    destination / "metadata.json",
                    failure_metadata(config, job, prompt_hash, effective_started_at, last_error, attempt),
                )
                return "failed"
            jitter = random.random() * base_delay
            await asyncio.sleep(base_delay * (2 ** (attempt - 1)) + jitter)

    raise AssertionError(last_error)


async def run_jobs(config: Dict[str, Any], jobs: List[Job], force: bool) -> int:
    pending = jobs if force else [job for job in jobs if not completed(config, job)]
    skipped = len(jobs) - len(pending)
    if not pending:
        print(f"No requests to run; {skipped} already completed.")
        return 0

    require_keys(pending)
    prompt_template = load_prompt_template(resolve_config_path(config, "prompt_file"))
    global_semaphore = asyncio.Semaphore(int(config["global_concurrency"]))
    limits = {
        (m["provider"], m.get("output_slug", m["model_id"])): asyncio.Semaphore(
            int(m["concurrency"])
        )
        for m in config["models"]
    }
    providers = Providers(
        float(config["request_timeout_seconds"]),
        {job.provider for job in pending},
    )
    counts = {"completed": 0, "failed": 0}
    print(f"Starting {len(pending)} requests; {skipped} already completed.")
    try:
        tasks = [
            asyncio.create_task(
                execute_job(
                    config,
                    job,
                    prompt_template,
                    providers,
                    global_semaphore,
                    limits[(job.provider, job.output_slug)],
                )
            )
            for job in pending
        ]
        for index, task in enumerate(asyncio.as_completed(tasks), start=1):
            status = await task
            counts[status] += 1
            print(f"[{index}/{len(tasks)}] completed={counts['completed']} failed={counts['failed']}")
    finally:
        await providers.close()
    return 1 if counts["failed"] else 0


def print_plan(config: Dict[str, Any], jobs: Sequence[Job]) -> None:
    by_provider: Dict[str, int] = {}
    for job in jobs:
        by_provider[job.provider] = by_provider.get(job.provider, 0) + 1
    tasks = {(job.session, job.item_id) for job in jobs}
    print(f"Benchmark: {config['benchmark_id']}")
    print(f"Sessions: {', '.join(config['sessions'])}")
    print("Task unit: item")
    print(f"Distinct tasks: {len(tasks)}")
    print(f"Repetitions: {config['repetitions']}")
    print(f"Total requests: {len(jobs)}")
    for provider in sorted(by_provider):
        print(f"  {provider}: {by_provider[provider]}")


def print_status(config: Dict[str, Any], jobs: Sequence[Job]) -> None:
    states = {"completed": 0, "failed": 0, "pending": 0}
    for job in jobs:
        metadata_path = run_directory(config, job) / "metadata.json"
        if not metadata_path.exists():
            states["pending"] += 1
            continue
        try:
            status = read_json(metadata_path).get("execution", {}).get("status", "pending")
        except (OSError, ValueError, json.JSONDecodeError):
            status = "failed"
        states[status if status in states else "failed"] += 1
    print("Run status:")
    for state in ("completed", "failed", "pending"):
        print(f"  {state}: {states[state]}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("plan", "run", "status"))
    parser.add_argument(
        "--config",
        default="configs/benchmark_config.template.json",
    )
    parser.add_argument("--provider", action="append", choices=tuple(KEY_BY_PROVIDER))
    parser.add_argument("--limit", type=int, help="limit the number of jobs for an initial smoke test")
    parser.add_argument("--dry-run", action="store_true", help="print the plan without calling provider APIs")
    parser.add_argument("--force", action="store_true", help="rerun jobs that are already complete")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    supplied_config_path = Path(args.config).expanduser()
    if supplied_config_path.is_absolute():
        config_path = supplied_config_path.resolve()
    elif supplied_config_path.exists():
        config_path = supplied_config_path.resolve()
    else:
        config_path = (ROOT / supplied_config_path).resolve()
    config = read_json(config_path)
    validate_config(config)
    try:
        recorded_config_path = str(config_path.relative_to(ROOT))
    except ValueError:
        recorded_config_path = config_path.name
    config["_runtime_config_path"] = recorded_config_path
    config["_runtime_config_sha256"] = sha256_file(config_path)
    config["_runtime_config_directory"] = str(config_path.parent)
    jobs = build_jobs(config, args.provider)
    if args.limit is not None:
        if args.limit < 1:
            raise ValueError("--limit must be at least 1")
        jobs = jobs[: args.limit]

    if args.command == "plan" or args.dry_run:
        print_plan(config, jobs)
        if args.dry_run:
            print("Dry run complete: no provider API was called and no credit was consumed.")
        return 0
    if args.command == "status":
        print_status(config, jobs)
        return 0
    if config.get("provider_calls_authorized") is False:
        raise PermissionError(
            "Provider calls are blocked by the configuration: "
            "provider_calls_authorized=false"
        )
    environment_path = config_path.parent / ".env"
    if config_path.parent == (ROOT / "configs").resolve():
        environment_path = ROOT / ".env"
    load_dotenv(environment_path)
    snapshot_campaign(config)
    return asyncio.run(run_jobs(config, jobs, force=args.force))


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("Interrupted by the user; saved runs will be reused.", file=sys.stderr)
        raise SystemExit(130)
    except Exception as exc:
        print(f"Error: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(2)
