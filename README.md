# llm-output-fuzz

Deterministic, offline adversarial fixtures for testing LLM structured-output
parsers and tool-call consumers.

## Problem

An LLM parser rarely fails on the one valid object in its unit test. It fails on
the model-shaped boundary cases: a required field disappears, a tool argument
is cut off mid-string, a model wraps JSON in a markdown fence, or a provider
returns an unexpected type. Recreating those cases by hand in every repository
is tedious and leaves important paths untested.

## Solution

`llm-output-fuzz` turns one JSON Schema into stable JSONL fixtures. Each case is
labeled with its mutation, transport envelope, expected validity, and the exact
text a parser would receive. It never calls a model, starts a server, or sends
your schema anywhere.

## Quick start

```bash
python -m pip install "git+https://github.com/thisbejim/llm-output-fuzz.git"

llm-output-fuzz generate examples/order.schema.json \
  --count 12 --seed 42 --transports raw,chat-tool-call \
  --mutations valid,wrong-type,truncated-json,markdown-fence \
  -o cases.jsonl

llm-output-fuzz inspect cases.jsonl
```

Example output:

```json
{
  "cases": 12,
  "expected_invalid": 9,
  "mutations": {
    "markdown-fence": 3,
    "truncated-json": 3,
    "valid": 3,
    "wrong-type": 3
  }
}
```

A generated line is intentionally data-only:

```json
{"case_id":"case-0002","description":"A leaf value has the wrong JSON type. Transport: chat-tool-call.","expected_valid":false,"json_text":"{\"item\":{\"sku\":{\"unexpected\":\"object\"},\"quantity\":1}}","mutation":"wrong-type","payload":{"choices":[{"message":{"role":"assistant","tool_calls":[{"function":{"arguments":"{\"item\":{\"sku\":{\"unexpected\":\"object\"},\"quantity\":1}}","name":"submit_result"},"id":"call_fuzz","type":"function"}],"finish_reason":"tool_calls","index":0}],"id":"chatcmpl-fuzz","object":"chat.completion"},"schema_path":"$","transport":"chat-tool-call"}
```

Feed `payload` or `json_text` to the parser under test. The package never
executes a tool call or treats fixture text as code.

## Supported mutations

* `valid`, `missing-required`, `wrong-type`, `null-value`
* `below-minimum`, `above-maximum`, `unknown-property`
* `truncated-json`, `markdown-fence`, `trailing-text`, `duplicate-key`

Use `--mutations` to select a focused regression matrix. `--seed` makes the
generated baseline values reproducible.

## Supported transports

* `raw`: the JSON text a response parser receives.
* `chat-tool-call`: an OpenAI-style Chat Completions tool-call envelope.
* `responses-function-call`: an OpenAI-style Responses function-call item.

These are documented shapes for test fixtures, not claims of complete provider
compatibility or endorsement. Add your own adapter around `payload` when your
client uses another envelope.

## Python API

```python
import json
from llm_output_fuzz import FuzzConfig, generate_cases

schema = json.load(open("examples/order.schema.json", encoding="utf-8"))
cases = generate_cases(
    schema,
    FuzzConfig(count=50, seed=7, mutations=("valid", "wrong-type", "truncated-json")),
)
for case in cases:
    assert case.case_id
    send_to_parser(case.payload)  # your code; llm-output-fuzz never executes it
```

## Why this instead of a schema faker?

General JSON Schema generators are good at producing valid values. This tool is
for the missing second half of an AI reliability suite: deterministic invalid
text and provider-shaped argument envelopes that reproduce the failure modes
reported by real OpenAI-compatible servers. It complements validators and
contract checkers; it does not replace them.

## Public evidence

* [TensorRT-LLM issue #10612](https://github.com/NVIDIA/TensorRT-LLM/issues/10612)
  reports malformed JSON across batch and streaming structured-output paths.
* [llama.cpp issue #22072](https://github.com/ggml-org/llama.cpp/issues/22072)
  reports malformed or truncated JSON tool-call arguments from an
  OpenAI-compatible server.
* [QASkills' streaming partial JSON testing guide](https://qaskills.sh/blog/llm-testing-streaming-partial-json)
  describes the need to test incomplete chunks, schema drift, cancellation,
  and delayed closing braces.
* [A developer's 288-call corpus](https://www.reddit.com/r/LocalLLaMA/comments/1qz2fra/i_catalogued_every_way_local_models_break_json/)
  catalogs recurring model-output breakage such as fences, trailing text,
  comments, and truncated streams.

## Privacy and security

Everything runs locally. There is no telemetry, login, hosted service, or
network request. Schemas and generated fixtures stay on your machine. Fixture
payloads are never executed, deserialized with unsafe formats, or used as shell
arguments. Review any harness that consumes them before connecting it to real
tools.

## Development

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
pytest
ruff check .
mypy src
```

The test suite uses only local schemas and synthetic values; no API key or
network access is required.

## License

MIT
