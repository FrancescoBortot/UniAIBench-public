"""Dependency-free validator for the JSON Schema features used here."""

from __future__ import annotations

import json
import math
import re
from datetime import datetime
from typing import Any


class SchemaValidationError(ValueError):
    """Raised when an instance does not satisfy a repository schema."""


def _resolve_reference(reference: str, root: dict[str, Any]) -> dict[str, Any]:
    if not reference.startswith("#/"):
        raise SchemaValidationError(f"unsupported schema reference: {reference}")
    current: Any = root
    for component in reference[2:].split("/"):
        component = component.replace("~1", "/").replace("~0", "~")
        if not isinstance(current, dict) or component not in current:
            raise SchemaValidationError(f"unresolved schema reference: {reference}")
        current = current[component]
    if not isinstance(current, dict):
        raise SchemaValidationError(f"schema reference is not an object: {reference}")
    return current


def _matches_type(value: Any, expected: str) -> bool:
    if expected == "null":
        return value is None
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
    raise SchemaValidationError(f"unsupported schema type: {expected}")


def _canonical_item(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _validate_format(value: str, format_name: str, path: str) -> None:
    if format_name != "date-time":
        raise SchemaValidationError(f"{path}: unsupported string format {format_name!r}")
    pattern = re.compile(
        r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}"
        r"(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$"
    )
    if pattern.fullmatch(value) is None:
        raise SchemaValidationError(f"{path}: value is not an RFC 3339 date-time")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00" if value.endswith("Z") else value)
    except ValueError as exc:
        raise SchemaValidationError(f"{path}: value is not a valid date-time") from exc
    if parsed.tzinfo is None:
        raise SchemaValidationError(f"{path}: date-time must include a UTC offset")


def validate_json_schema(
    value: Any,
    schema: dict[str, Any],
    *,
    root: dict[str, Any] | None = None,
    path: str = "$",
) -> None:
    """Validate a value against the closed schema subset used in this repo."""

    root = schema if root is None else root
    if "$ref" in schema:
        validate_json_schema(value, _resolve_reference(schema["$ref"], root), root=root, path=path)
        return

    if "enum" in schema and value not in schema["enum"]:
        raise SchemaValidationError(f"{path}: value {value!r} is not in {schema['enum']!r}")

    expected = schema.get("type")
    if expected is not None:
        allowed = [expected] if isinstance(expected, str) else list(expected)
        if not any(_matches_type(value, item) for item in allowed):
            raise SchemaValidationError(f"{path}: expected {' or '.join(allowed)}, got {type(value).__name__}")

    if isinstance(value, dict):
        missing = [name for name in schema.get("required", []) if name not in value]
        if missing:
            raise SchemaValidationError(f"{path}: missing required properties: {', '.join(missing)}")
        properties = schema.get("properties", {})
        extra = sorted(set(value) - set(properties))
        additional = schema.get("additionalProperties", True)
        if additional is False:
            if extra:
                raise SchemaValidationError(f"{path}: unexpected properties: {', '.join(extra)}")
        elif isinstance(additional, dict):
            for name in extra:
                validate_json_schema(
                    value[name], additional, root=root, path=f"{path}.{name}"
                )
        for present, dependencies in schema.get("dependentRequired", {}).items():
            if present not in value:
                continue
            missing_dependencies = [name for name in dependencies if name not in value]
            if missing_dependencies:
                raise SchemaValidationError(
                    f"{path}: property {present!r} requires "
                    + ", ".join(missing_dependencies)
                )
        for name, item in value.items():
            if name in properties:
                validate_json_schema(item, properties[name], root=root, path=f"{path}.{name}")

    if isinstance(value, list):
        if len(value) < int(schema.get("minItems", 0)):
            raise SchemaValidationError(f"{path}: expected at least {schema['minItems']} items")
        if schema.get("uniqueItems") and len({_canonical_item(item) for item in value}) != len(value):
            raise SchemaValidationError(f"{path}: duplicate array items are not allowed")
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(value):
                validate_json_schema(item, item_schema, root=root, path=f"{path}[{index}]")

    if isinstance(value, str):
        if "minLength" in schema and len(value) < int(schema["minLength"]):
            raise SchemaValidationError(f"{path}: string is shorter than {schema['minLength']}")
        if "pattern" in schema and re.search(str(schema["pattern"]), value) is None:
            raise SchemaValidationError(
                f"{path}: string does not match pattern {schema['pattern']!r}"
            )
        if "format" in schema:
            _validate_format(value, str(schema["format"]), path)

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            raise SchemaValidationError(f"{path}: value is below {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            raise SchemaValidationError(f"{path}: value is above {schema['maximum']}")
        if "exclusiveMinimum" in schema and value <= schema["exclusiveMinimum"]:
            raise SchemaValidationError(f"{path}: value must be greater than {schema['exclusiveMinimum']}")
        if "exclusiveMaximum" in schema and value >= schema["exclusiveMaximum"]:
            raise SchemaValidationError(f"{path}: value must be less than {schema['exclusiveMaximum']}")
