from __future__ import annotations

import json

from llm_output_fuzz import FuzzConfig, generate_cases


def test_fixture_text_is_data_not_executable() -> None:
    schema = {
        "type": "object",
        "required": ["command"],
        "properties": {"command": {"type": "string"}},
    }
    case = generate_cases(schema, FuzzConfig(count=1, mutations=("valid",)))[0]
    assert isinstance(case.payload, str)
    assert json.loads(case.payload)["command"] == "x"
