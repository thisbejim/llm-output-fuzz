"""Deterministic generation of model-shaped structured-output failures."""

from __future__ import annotations

import json
import random
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from jsonschema import Draft202012Validator

from .model import Case
from .schema_values import locate_leaf, mutate_value, sample_value, set_at_path

DEFAULT_MUTATIONS = (
    "valid",
    "missing-required",
    "wrong-type",
    "null-value",
    "below-minimum",
    "above-maximum",
    "unknown-property",
    "truncated-json",
    "markdown-fence",
    "trailing-text",
    "duplicate-key",
)
DEFAULT_TRANSPORTS = ("raw", "chat-tool-call", "responses-function-call")


@dataclass(frozen=True)
class FuzzConfig:
    count: int = 24
    seed: int = 0
    mutations: tuple[str, ...] = DEFAULT_MUTATIONS
    transports: tuple[str, ...] = ("raw",)
    include_valid: bool = True


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _remove_required(value: Any, schema: dict[str, Any]) -> Any:
    if not isinstance(value, dict):
        return value
    required = schema.get("required", [])
    if isinstance(required, list):
        for field in sorted(required):
            if field in value:
                result = dict(value)
                del result[field]
                return result
    return value


def _unknown_property(value: Any, schema: dict[str, Any]) -> Any:
    if not isinstance(value, dict):
        return value
    result = dict(value)
    name = "__fuzz_extra__"
    while name in result:
        name += "_"
    result[name] = "unexpected"
    if schema.get("additionalProperties", True) is not False:
        # The mutation is still useful for consumers that incorrectly assume a
        # closed object, but keep its expected schema validity honest.
        return result
    return result


def _mutate_document(document: Any, schema: dict[str, Any], mutation: str) -> tuple[Any, str, bool]:
    if mutation == "valid":
        return document, _json(document), Draft202012Validator(schema).is_valid(document)
    if mutation == "missing-required":
        changed = _remove_required(document, schema)
        return changed, _json(changed), Draft202012Validator(schema).is_valid(changed)
    if mutation == "unknown-property":
        changed = _unknown_property(document, schema)
        return changed, _json(changed), Draft202012Validator(schema).is_valid(changed)

    path, leaf = locate_leaf(schema, random.Random(0))
    changed = set_at_path(document, path, mutate_value(leaf, leaf, mutation))
    serialized = _json(changed)
    if mutation == "markdown-fence":
        return changed, f"```json\n{serialized}\n```", False
    if mutation == "trailing-text":
        return changed, serialized + "\nI hope this helps!", False
    if mutation == "duplicate-key":
        if isinstance(changed, dict) and changed:
            key = sorted(changed)[0]
            first = _json(changed)
            duplicate = first[:-1] + "," + json.dumps(key) + ":" + _json(changed[key]) + "}"
            return changed, duplicate, False
        return changed, '{"value":1,"value":2}', False
    if mutation == "truncated-json":
        cut = max(1, len(serialized) // 2)
        return changed, serialized[:cut], False
    return changed, serialized, Draft202012Validator(schema).is_valid(changed)


def _transport_payload(transport: str, json_text: str) -> Any:
    if transport == "raw":
        return json_text
    if transport == "chat-tool-call":
        return {
            "id": "chatcmpl-fuzz",
            "object": "chat.completion",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "tool_calls": [
                            {
                                "id": "call_fuzz",
                                "type": "function",
                                "function": {"name": "submit_result", "arguments": json_text},
                            }
                        ],
                    },
                    "finish_reason": "tool_calls",
                }
            ],
        }
    if transport == "responses-function-call":
        return {
            "id": "resp-fuzz",
            "object": "response",
            "output": [
                {
                    "type": "function_call",
                    "id": "fc_fuzz",
                    "call_id": "call_fuzz",
                    "name": "submit_result",
                    "arguments": json_text,
                }
            ],
        }
    raise ValueError(f"unsupported transport: {transport}")


def _transport_valid(mutation_valid: bool, transport: str, json_text: str) -> bool:
    """Transport envelopes stay valid; argument validity follows the mutation."""

    if transport == "raw":
        return mutation_valid
    return mutation_valid


def _description(mutation: str, transport: str) -> str:
    descriptions = {
        "valid": "Schema-valid baseline fixture.",
        "missing-required": "Required field removed before serialization.",
        "wrong-type": "A leaf value has the wrong JSON type.",
        "null-value": "A leaf is replaced with JSON null.",
        "below-minimum": "A numeric, string, or array lower bound is violated.",
        "above-maximum": "A numeric, string, or array upper bound is violated.",
        "unknown-property": "An unexpected object property is added.",
        "truncated-json": "The serialized argument is cut mid-document.",
        "markdown-fence": "A model wraps JSON in a markdown code fence.",
        "trailing-text": "A model appends natural-language text after JSON.",
        "duplicate-key": "The JSON text repeats an object key.",
    }
    return f"{descriptions.get(mutation, mutation)} Transport: {transport}."


def generate_cases(schema: dict[str, Any], config: FuzzConfig | None = None) -> list[Case]:
    """Generate stable, labeled cases from a JSON Schema object.

    ``seed`` controls all random choices. The output is stable for a given
    package version, schema, and configuration; callers should pin the version
    when snapshots are part of a release gate.
    """

    cfg = config or FuzzConfig()
    if cfg.count < 1:
        return []
    if not isinstance(schema, dict):
        raise TypeError("schema must be a JSON object")
    Draft202012Validator.check_schema(schema)
    rng = random.Random(cfg.seed)
    mutations = tuple(cfg.mutations)
    if not cfg.include_valid:
        mutations = tuple(item for item in mutations if item != "valid")
    if not mutations:
        raise ValueError("at least one mutation is required")
    transports = cfg.transports or ("raw",)
    cases: list[Case] = []
    for index in range(cfg.count):
        mutation = mutations[index % len(mutations)]
        transport = transports[(index // len(mutations)) % len(transports)]
        baseline = sample_value(schema, rng)
        changed, json_text, mutation_valid = _mutate_document(baseline, schema, mutation)
        payload = _transport_payload(transport, json_text)
        cases.append(
            Case(
                case_id=f"case-{index + 1:04d}",
                mutation=mutation,
                transport=transport,
                expected_valid=_transport_valid(mutation_valid, transport, json_text),
                payload=payload,
                json_text=json_text,
                schema_path="$",
                description=_description(mutation, transport),
            )
        )
    return cases


def iter_cases(schema: dict[str, Any], config: FuzzConfig | None = None) -> Iterable[Case]:
    """Yield cases for callers that prefer streaming writes."""

    yield from generate_cases(schema, config)
