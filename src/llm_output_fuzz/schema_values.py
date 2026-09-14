"""Small, predictable JSON Schema value generator.

This is deliberately a useful subset rather than a claim of full JSON Schema
generation. Validation is delegated to ``jsonschema`` when requested by the
library; generation supports the keywords most commonly used in LLM schemas.
"""

from __future__ import annotations

import random
from typing import Any


def sample_value(schema: dict[str, Any], rng: random.Random, depth: int = 0) -> Any:
    if depth > 8:
        return None
    if "const" in schema:
        return schema["const"]
    if "enum" in schema and schema["enum"]:
        return schema["enum"][0]

    for branch_key in ("oneOf", "anyOf", "allOf"):
        branches = schema.get(branch_key)
        if isinstance(branches, list) and branches:
            if branch_key == "allOf":
                merged: dict[str, Any] = {}
                for branch in branches:
                    if isinstance(branch, dict):
                        merged.update(branch)
                return sample_value(merged, rng, depth + 1)
            branch = branches[0]
            if isinstance(branch, dict):
                return sample_value(branch, rng, depth + 1)

    schema_type = schema.get("type")
    if isinstance(schema_type, list):
        schema_type = next((item for item in schema_type if item != "null"), schema_type[0])
    if schema_type == "object" or "properties" in schema:
        properties = schema.get("properties", {})
        value: dict[str, Any] = {}
        if isinstance(properties, dict):
            required = set(schema.get("required", []))
            for name in sorted(properties):
                if name in required or rng.random() < 0.65:
                    child = properties[name]
                    if isinstance(child, dict):
                        value[name] = sample_value(child, rng, depth + 1)
        return value
    if schema_type == "array" or "items" in schema:
        minimum = int(schema.get("minItems", 1))
        maximum = int(schema.get("maxItems", max(minimum, 2)))
        count = max(0, min(minimum, maximum))
        item_schema = schema.get("items", {})
        return [
            sample_value(item_schema, rng, depth + 1) if isinstance(item_schema, dict) else None
            for _ in range(count)
        ]
    if schema_type == "string" or "minLength" in schema or "maxLength" in schema:
        minimum = max(1, int(schema.get("minLength", 1)))
        maximum = max(minimum, int(schema.get("maxLength", minimum + 6)))
        length = min(minimum, maximum)
        pattern = schema.get("pattern")
        if pattern == "^[A-Z]+$":
            return "A" * length
        return "x" * length
    if schema_type == "integer":
        return int(schema.get("minimum", 1))
    if schema_type == "number":
        return float(schema.get("minimum", 1))
    if schema_type == "boolean":
        return True
    if schema_type == "null":
        return None
    return "fixture"


def wrong_type(value: Any) -> Any:
    """Return a deliberately incompatible JSON value."""

    if isinstance(value, bool):
        return "not-a-boolean"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return "not-a-number"
    if isinstance(value, str):
        return {"unexpected": "object"}
    if isinstance(value, list):
        return {"unexpected": "object"}
    if isinstance(value, dict):
        return ["unexpected", "array"]
    return "unexpected"


def mutate_value(value: Any, schema: dict[str, Any], mutation: str) -> Any:
    """Apply one named semantic mutation to a sampled value."""

    if mutation == "wrong-type":
        return wrong_type(value)
    if mutation == "null-value":
        return None
    if mutation == "oversized-string":
        return "X" * max(32, int(schema.get("maxLength", 0)) + 1)
    if mutation == "below-minimum":
        minimum = schema.get("minimum", schema.get("minItems", schema.get("minLength", 1)))
        if schema.get("type") == "array":
            return []
        if schema.get("type") == "string":
            return ""
        return minimum - 1 if isinstance(minimum, (int, float)) else -1
    if mutation == "above-maximum":
        maximum = schema.get("maximum", schema.get("maxItems", schema.get("maxLength", 1)))
        if schema.get("type") == "array":
            return [None] * (int(maximum) + 1)
        if schema.get("type") == "string":
            return "X" * (int(maximum) + 1)
        return maximum + 1 if isinstance(maximum, (int, float)) else 999999
    return value


def locate_leaf(schema: dict[str, Any], rng: random.Random) -> tuple[list[str], dict[str, Any]]:
    """Choose a deterministic leaf path, preferring required object fields."""

    path: list[str] = []
    current = schema
    for _ in range(8):
        properties = current.get("properties")
        if isinstance(properties, dict) and properties:
            required = [name for name in current.get("required", []) if name in properties]
            name = sorted(required or list(properties))[0]
            path.append(name)
            child = properties[name]
            if isinstance(child, dict):
                current = child
                continue
        items = current.get("items")
        if isinstance(items, dict):
            path.append("0")
            current = items
            continue
        break
    return path, current


def set_at_path(value: Any, path: list[str], replacement: Any) -> Any:
    """Copy a JSON value and replace one path without mutating caller data."""

    if not path:
        return replacement
    if isinstance(value, dict):
        clone = dict(value)
        key = path[0]
        if key in clone:
            clone[key] = set_at_path(clone[key], path[1:], replacement)
        return clone
    if isinstance(value, list):
        clone_list = list(value)
        index = int(path[0])
        if 0 <= index < len(clone_list):
            clone_list[index] = set_at_path(clone_list[index], path[1:], replacement)
        return clone_list
    return value
