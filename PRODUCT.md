# Product specification

## Target developer

An AI platform, agent, or inference engineer who owns code that parses JSON
structured outputs or function/tool-call arguments from OpenAI-style or local
OpenAI-compatible endpoints.

## Problem

Happy-path fixtures do not exercise the failures that occur at the model/API
boundary: truncated streams, wrong types, missing required fields, duplicate
keys, markdown fences, and natural-language trailers. Teams hand-write these
cases in each parser test suite, so regressions are easy to miss and hard to
reproduce.

## Evidence

Public reports document malformed structured output in batch and streaming
TensorRT-LLM responses, malformed/incomplete tool-call arguments in llama.cpp,
and repeated developer reports that streaming JSON needs partial-input tests.
See the evidence links in the README.

## Existing workflow and alternatives

Developers commonly use `jsonschema`, Pydantic, or general JSON Schema fakers to
validate happy-path values. Those tools do not emit model-shaped transport
envelopes or labeled malformed text. Provider-specific server scripts, such as
llama.cpp's structured-output test, test one server rather than the consumer
parser and require a running model server.

## Product thesis

For engineers testing LLM output consumers, `llm-output-fuzz` produces stable,
provider-shaped malformed fixtures better than hand-written examples because a
single schema expands into labeled semantic and serialization failures with no
model, server, network, or API key.

## Core workflow

```text
schema.json -> llm-output-fuzz generate -> labeled JSONL fixtures
                                      -> parser/agent CI regression tests
```

## Non-goals

* It does not call models or benchmark model quality.
* It does not repair malformed JSON.
* It does not execute tool calls or arbitrary commands.
* It is not a full JSON Schema generator or validator.
* It does not claim an API provider's certification.

## Interface

The primary interface is a small CLI; the Python library exposes the same
generator for pytest/property-based harnesses.

## Offline and integration story

Generation and inspection are completely offline. The output can represent
raw JSON text, Chat Completions tool calls, and Responses API function-call
items. Optional provider traffic is intentionally outside the project: users
can feed fixtures to any local parser, API-compatible server, or agent test.
