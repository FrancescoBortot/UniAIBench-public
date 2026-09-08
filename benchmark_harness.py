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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from dotenv import load_dotenv

from tools.schema_validation import validate_json_schema


ROOT = Path(__file__).resolve().parent
SESSION_ORDER = {"primoapp": 1, "secondoapp": 2, "terzoapp": 3, "quartoapp": 4, "quintoapp": 5}
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
    exercise_number: int
    exercise_file: Path
    run_number: int
    exercise_files: Tuple[Path, ...] = ()

    @property
    def exercise_id(self) -> str:
        if self.exercise_files:
            return "intero_esame"
        return f"esercizio_{self.exercise_number}"

    @property
    def dataset_item_id(self) -> str:
        return f"{self.dataset_item_prefix}_{self.year}_{self.session}_{self.exercise_id}"

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
    schema = read_json(ROOT / "schemas" / "benchmark-config.schema.json")
    validate_json_schema(config, schema)


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
    return int(config.get("exam_metadata", {}).get("year", 2025))


def dataset_item_prefix(config: Dict[str, Any]) -> str:
    prefix = str(config.get("dataset_item_prefix", "analisi3")).strip()
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", prefix):
        raise ValueError(f"dataset_item_prefix non valido: {prefix!r}")
    return prefix


def session_directory(config: Dict[str, Any], dataset_root: Path, year: int, session: str) -> Path:
    template = str(config.get("session_directory_template", "02_esercizi_{year}_{session}"))
    expected = dataset_root / template.format(year=year, session=session)
    if not expected.is_dir():
        raise FileNotFoundError(f"Cartella dell'appello non trovata: {expected}")
    return expected


def discover_exercises(config: Dict[str, Any]) -> List[Tuple[str, int, Path]]:
    dataset_root = ROOT / config["dataset_root"]
    year = benchmark_year(config)
    selected_numbers = config.get("exercise_numbers")
    if selected_numbers is not None:
        if (
            not isinstance(selected_numbers, list)
            or not selected_numbers
            or not all(isinstance(number, int) and number > 0 for number in selected_numbers)
            or len(selected_numbers) != len(set(selected_numbers))
        ):
            raise ValueError("exercise_numbers deve essere una lista non vuota di interi positivi distinti")
        selected_numbers = set(selected_numbers)
    exercises: List[Tuple[str, int, Path]] = []
    for session in config["sessions"]:
        directory = session_directory(config, dataset_root, year, session)
        pattern = str(config.get("exercise_filename_glob", "esercizio_*.txt"))
        expression = re.compile(str(config.get("exercise_filename_regex", r"(?:esercizio|exercise)_(\d+)\.txt")))
        numbered: List[Tuple[int, Path]] = []
        for path in directory.glob(pattern):
            match = expression.fullmatch(path.name)
            if match:
                numbered.append((int(match.group(1)), path))
        files = [path for _, path in sorted(numbered)]
        expected_count = int(config.get("expected_exercises_per_session", 3))
        if len(files) != expected_count:
            raise ValueError(f"Expected {expected_count} exercises in {directory}, found {len(files)}")
        for path in files:
            match = expression.fullmatch(path.name)
            assert match is not None
            number = int(match.group(1))
            if selected_numbers is None or number in selected_numbers:
                exercises.append((session, number, path))
    if selected_numbers is not None:
        discovered_numbers = {number for _, number, _ in exercises}
        missing_numbers = selected_numbers - discovered_numbers
        if missing_numbers:
            missing = ", ".join(str(number) for number in sorted(missing_numbers))
            raise ValueError(f"Esercizi selezionati non trovati: {missing}")
    return exercises


def build_jobs(config: Dict[str, Any], providers: Optional[Sequence[str]] = None) -> List[Job]:
    requested = set(providers or [])
    models = [m for m in config["models"] if not requested or m["provider"] in requested]
    unknown = requested - {m["provider"] for m in config["models"]}
    if unknown:
        raise ValueError(f"Provider sconosciuti: {', '.join(sorted(unknown))}")

    jobs: List[Job] = []
    year = benchmark_year(config)
    item_prefix = dataset_item_prefix(config)
    discovered = discover_exercises(config)
    task_unit = config.get("task_unit", "exercise")
    if task_unit not in {"exercise", "exam"}:
        raise ValueError("task_unit deve essere 'exercise' oppure 'exam'")
    if task_unit == "exam" and config.get("exercise_numbers") is not None:
        raise ValueError("exercise_numbers non è compatibile con task_unit='exam'")

    task_sources: List[Tuple[str, int, Path, Tuple[Path, ...]]] = []
    if task_unit == "exam":
        by_session: Dict[str, List[Path]] = {}
        for session, _, exercise_file in discovered:
            by_session.setdefault(session, []).append(exercise_file)
        task_sources = [
            (session, 0, files[0], tuple(files))
            for session, files in by_session.items()
        ]
    else:
        task_sources = [
            (session, number, exercise_file, ())
            for session, number, exercise_file in discovered
        ]

    for session, number, exercise_file, exercise_files in task_sources:
        for model in models:
            for run_number in range(1, int(config["repetitions"]) + 1):
                jobs.append(
                    Job(
                        dataset_item_prefix=item_prefix,
                        provider=model["provider"],
                        display_name=model["display_name"],
                        model_id=model["model_id"],
                        output_slug=model.get("output_slug", model["model_id"]),
                        model_mode=model.get("model_mode", "non disponibile"),
                        max_output_tokens=int(model["max_output_tokens"]),
                        reasoning_effort=model.get("reasoning_effort"),
                        thinking_level=model.get("thinking_level"),
                        thinking_mode=model.get("thinking_mode"),
                        pricing_usd_per_million=model.get("pricing_usd_per_million"),
                        endpoint=str(model.get("endpoint", DEFAULT_ENDPOINTS[model["provider"]])),
                        year=year,
                        session=session,
                        exercise_number=number,
                        exercise_file=exercise_file,
                        run_number=run_number,
                        exercise_files=exercise_files,
                    )
                )
    random.Random(int(config["shuffle_seed"])).shuffle(jobs)
    return jobs


def run_directory(config: Dict[str, Any], job: Job) -> Path:
    return (
        ROOT
        / config["output_root"]
        / str(job.year)
        / job.session
        / job.exercise_id
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
    exam = config.get("exam_metadata", {})
    return {
        "run_id": job.run_id,
        "exam_name": str(exam.get("exam_name", "non disponibile")),
        "degree_program": str(exam.get("degree_program", "non disponibile")),
        "institution": str(exam.get("institution", "non disponibile")),
        "exam_date": "non disponibile",
        "exam_session": job.session,
        "academic_year": str(exam.get("academic_year", "2024/2025")),
        "exercise_id": job.exercise_id,
        "subject": str(exam.get("subject", "non disponibile")),
        "topic": str(exam.get("topic", "non disponibile")),
        "model_name": job.display_name,
        "model_version": job.model_id,
        "provider": job.provider,
        "model_mode": job.model_mode,
        "source_file": ", ".join(
            str(path.relative_to(ROOT))
            for path in (job.exercise_files or (job.exercise_file,))
        ),
        "prompt_id": str(config["prompt_id"]),
        "start_timestamp": "non disponibile",
        "end_timestamp": "non disponibile",
        "elapsed_time": "non disponibile",
        "reasoning_time": "non disponibile",
        "input_tokens": "non disponibile",
        "reasoning_tokens": "non disponibile",
        "output_tokens": "non disponibile",
        "temperature": "non disponibile",
        "top_p": "non disponibile",
        "seed": "non disponibile",
        "max_output_tokens": str(job.max_output_tokens),
        "run_number": str(job.run_number),
        "allowed_tools": str(exam.get("allowed_tools", "nessuno")),
        "web_allowed": str(exam.get("web_allowed", "no")),
        "allowed_materials": str(exam.get("allowed_materials", "nessuno")),
        "problem_text": problem_text.strip(),
    }


def render_prompt(template: str, values: Dict[str, str]) -> str:
    rendered = template
    for key, value in values.items():
        rendered = rendered.replace("{{" + key + "}}", value)
    rendered = re.sub(r"\{\{[^{}]+\}\}", "non disponibile", rendered)
    return rendered


def snapshot_campaign(config: Dict[str, Any]) -> None:
    """Persist the exact non-secret configuration and prompt before API calls."""

    campaign_dir = ROOT / config["output_root"] / "_campaign"
    public_config = {key: value for key, value in config.items() if not key.startswith("_runtime_")}
    prompt_path = ROOT / config["prompt_file"]
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
            "Chiavi API mancanti: " + ", ".join(missing) + ". Copia .env.example in .env e compilalo."
        )


def as_json_dict(value: Any) -> Dict[str, Any]:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json", exclude_none=False)
    if hasattr(value, "to_dict"):
        return value.to_dict()
    raise TypeError(f"Risposta non serializzabile: {type(value)!r}")


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
        raise ValueError(f"Provider non supportato: {job.provider}")

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
        return "Risposta testuale vuota"
    accepted = {
        "openai": {"completed"},
        "anthropic": {"end_turn", "stop_sequence"},
        "google": {"STOP"},
        "kimi": {"stop"},
        "deepseek": {"stop"},
        "xai": {"completed"},
    }
    if result.finish_reason not in accepted.get(job.provider, set()):
        return f"Risposta incompleta: finish_reason={result.finish_reason!r}"
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
    source_files = job.exercise_files or (job.exercise_file,)
    if job.exercise_files:
        problem_text = "\n\n".join(
            f"===== ESERCIZIO {index} =====\n\n{path.read_text(encoding='utf-8').strip()}"
            for index, path in enumerate(source_files, start=1)
        )
    else:
        problem_text = job.exercise_file.read_text(encoding="utf-8")
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
                "exam": {
                    "year": job.year,
                    "session": job.session,
                    "exercise_id": job.exercise_id,
                    "task_unit": "exam" if job.exercise_files else "exercise",
                    "subject": str(config.get("exam_metadata", {}).get("subject", "non disponibile")),
                    "source_file": str(job.exercise_file.relative_to(ROOT)),
                    "source_files": [str(path.relative_to(ROOT)) for path in source_files],
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
                    "allowed": config.get("exam_metadata", {}).get("allowed_tools", []),
                    "web_allowed": bool(config.get("exam_metadata", {}).get("web_allowed", False)),
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
        except Exception as exc:  # Le eccezioni vengono registrate senza includere credenziali.
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
        print(f"Nessuna richiesta da eseguire; {skipped} già completate.")
        return 0

    require_keys(pending)
    prompt_template = load_prompt_template(ROOT / config["prompt_file"])
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
    print(f"Avvio di {len(pending)} richieste; {skipped} già completate.")
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
            print(f"[{index}/{len(tasks)}] completate={counts['completed']} fallite={counts['failed']}")
    finally:
        await providers.close()
    return 1 if counts["failed"] else 0


def print_plan(config: Dict[str, Any], jobs: Sequence[Job]) -> None:
    by_provider: Dict[str, int] = {}
    for job in jobs:
        by_provider[job.provider] = by_provider.get(job.provider, 0) + 1
    tasks = {(job.session, job.exercise_id) for job in jobs}
    print(f"Benchmark: {config['benchmark_id']}")
    print(f"Appelli: {', '.join(config['sessions'])}")
    print(f"Unità del task: {config.get('task_unit', 'exercise')}")
    print(f"Task distinti: {len(tasks)}")
    print(f"Ripetizioni: {config['repetitions']}")
    print(f"Richieste totali: {len(jobs)}")
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
    print("Stato delle esecuzioni:")
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
    parser.add_argument("--limit", type=int, help="Limita il numero di job, utile per il test iniziale")
    parser.add_argument("--dry-run", action="store_true", help="Mostra il piano senza chiamare le API")
    parser.add_argument("--force", action="store_true", help="Riesegue anche i job già completati")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config_path = (ROOT / args.config).resolve()
    config = read_json(config_path)
    validate_config(config)
    try:
        recorded_config_path = str(config_path.relative_to(ROOT))
    except ValueError:
        recorded_config_path = config_path.name
    config["_runtime_config_path"] = recorded_config_path
    config["_runtime_config_sha256"] = sha256_file(config_path)
    jobs = build_jobs(config, args.provider)
    if args.limit is not None:
        if args.limit < 1:
            raise ValueError("--limit deve essere almeno 1")
        jobs = jobs[: args.limit]

    if args.command == "plan" or args.dry_run:
        print_plan(config, jobs)
        if args.dry_run:
            print("Dry-run concluso: nessuna API è stata chiamata e nessun credito è stato consumato.")
        return 0
    if args.command == "status":
        print_status(config, jobs)
        return 0
    if config.get("provider_calls_authorized") is False:
        raise PermissionError(
            "La configurazione blocca le chiamate provider: "
            "provider_calls_authorized=false"
        )
    load_dotenv(ROOT / ".env")
    snapshot_campaign(config)
    return asyncio.run(run_jobs(config, jobs, force=args.force))


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("Interrotto dall'utente; le esecuzioni già salvate saranno riutilizzate.", file=sys.stderr)
        raise SystemExit(130)
    except Exception as exc:
        print(f"Errore: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(2)
