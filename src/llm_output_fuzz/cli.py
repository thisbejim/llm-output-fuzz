"""Command-line interface for ``llm-output-fuzz``."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from .fuzzer import DEFAULT_MUTATIONS, DEFAULT_TRANSPORTS, FuzzConfig, generate_cases


def _load_json(path: str) -> Any:
    if path == "-":
        return json.load(sys.stdin)
    with Path(path).open(encoding="utf-8") as handle:
        return json.load(handle)


def _write_cases(cases: list[Any], path: str) -> None:
    stream = sys.stdout if path == "-" else Path(path).open("w", encoding="utf-8")
    try:
        for case in cases:
            stream.write(json.dumps(case.to_dict(), ensure_ascii=False, sort_keys=True) + "\n")
    finally:
        if stream is not sys.stdout:
            stream.close()


def _generate(args: argparse.Namespace) -> int:
    schema = _load_json(args.schema)
    mutations = tuple(args.mutations.split(",")) if args.mutations else DEFAULT_MUTATIONS
    transports = tuple(args.transports.split(",")) if args.transports else ("raw",)
    unknown_mutations = sorted(set(mutations) - set(DEFAULT_MUTATIONS))
    if unknown_mutations:
        print(f"unknown mutation(s): {', '.join(unknown_mutations)}", file=sys.stderr)
        return 2
    unknown_transports = sorted(set(transports) - set(DEFAULT_TRANSPORTS))
    if unknown_transports:
        print(f"unknown transport(s): {', '.join(unknown_transports)}", file=sys.stderr)
        return 2
    cases = generate_cases(
        schema,
        FuzzConfig(
            count=args.count,
            seed=args.seed,
            mutations=mutations,
            transports=transports,
            include_valid=not args.no_valid,
        ),
    )
    _write_cases(cases, args.output)
    if args.output != "-":
        print(f"wrote {len(cases)} cases to {args.output}", file=sys.stderr)
    return 0


def _inspect(args: argparse.Namespace) -> int:
    counts: Counter[str] = Counter()
    invalid = 0
    total = 0
    path = sys.stdin if args.cases == "-" else Path(args.cases).open(encoding="utf-8")
    try:
        for line_number, line in enumerate(path, 1):
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError as exc:
                print(f"line {line_number}: invalid JSONL ({exc.msg})", file=sys.stderr)
                return 2
            total += 1
            counts[str(item.get("mutation", "unknown"))] += 1
            if item.get("expected_valid") is False:
                invalid += 1
    finally:
        if path is not sys.stdin:
            path.close()
    report = {
        "cases": total,
        "expected_invalid": invalid,
        "mutations": dict(sorted(counts.items())),
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="llm-output-fuzz",
        description=(
            "Generate deterministic adversarial fixtures for LLM structured-output parsers."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    generate = subparsers.add_parser("generate", help="write labeled JSONL fixtures from a schema")
    generate.add_argument("schema", help="JSON Schema file, or - for stdin")
    generate.add_argument("-o", "--output", default="-", help="JSONL destination (default: stdout)")
    generate.add_argument("-n", "--count", type=int, default=24)
    generate.add_argument("--seed", type=int, default=0)
    generate.add_argument("--mutations", help="comma-separated mutation names")
    generate.add_argument(
        "--transports",
        help="comma-separated transports: raw, chat-tool-call, responses-function-call",
    )
    generate.add_argument(
        "--no-valid", action="store_true", help="omit schema-valid baseline cases"
    )
    generate.set_defaults(handler=_generate)
    inspect = subparsers.add_parser("inspect", help="summarize a generated JSONL file")
    inspect.add_argument("cases", help="JSONL fixture file, or - for stdin")
    inspect.set_defaults(handler=_inspect)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return int(args.handler(args))
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
