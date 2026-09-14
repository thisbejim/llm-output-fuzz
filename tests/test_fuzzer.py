from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

from llm_output_fuzz import FuzzConfig, generate_cases

ROOT = Path(__file__).parents[1]


def schema() -> dict:
    return json.loads((ROOT / "examples/order.schema.json").read_text())


def test_generation_is_deterministic() -> None:
    config = FuzzConfig(count=15, seed=7, transports=("raw", "chat-tool-call"))
    first = [case.to_dict() for case in generate_cases(schema(), config)]
    second = [case.to_dict() for case in generate_cases(schema(), config)]
    assert first == second


def test_all_named_mutations_are_present_and_labeled() -> None:
    mutations = (
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
    cases = generate_cases(schema(), FuzzConfig(count=len(mutations), mutations=mutations))
    assert [case.mutation for case in cases] == list(mutations)
    assert all(case.case_id.startswith("case-") for case in cases)


def test_valid_baseline_matches_schema() -> None:
    case = generate_cases(schema(), FuzzConfig(count=1, mutations=("valid",)))[0]
    assert case.expected_valid is True
    Draft202012Validator(schema()).validate(json.loads(case.json_text))


def test_transports_have_expected_provider_shapes() -> None:
    cases = generate_cases(
        schema(),
        FuzzConfig(
            count=3,
            mutations=("valid",),
            transports=("raw", "chat-tool-call", "responses-function-call"),
        ),
    )
    assert isinstance(cases[0].payload, str)
    assert (
        cases[1].payload["choices"][0]["message"]["tool_calls"][0]["function"]["name"]
        == "submit_result"
    )
    assert cases[2].payload["output"][0]["type"] == "function_call"


def test_malformed_text_is_not_marked_valid() -> None:
    cases = generate_cases(
        schema(),
        FuzzConfig(
            count=4,
            mutations=("truncated-json", "markdown-fence", "trailing-text", "duplicate-key"),
        ),
    )
    assert all(case.expected_valid is False for case in cases)
    assert any("```json" in case.json_text for case in cases)


def test_no_valid_cases_can_be_requested() -> None:
    cases = generate_cases(
        schema(),
        FuzzConfig(count=4, mutations=("valid", "wrong-type"), include_valid=False),
    )
    assert all(case.mutation == "wrong-type" for case in cases)
