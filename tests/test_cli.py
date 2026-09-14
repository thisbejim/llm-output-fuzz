from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
SCHEMA = ROOT / "examples/order.schema.json"


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "llm_output_fuzz.cli", *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_generate_and_inspect_jsonl(tmp_path: Path) -> None:
    output = tmp_path / "cases.jsonl"
    generated = run_cli("generate", str(SCHEMA), "-n", "6", "--seed", "3", "-o", str(output))
    assert generated.returncode == 0, generated.stderr
    assert len(output.read_text().splitlines()) == 6

    inspected = run_cli("inspect", str(output))
    assert inspected.returncode == 0, inspected.stderr
    report = json.loads(inspected.stdout)
    assert report["cases"] == 6
    assert report["expected_invalid"] >= 1


def test_invalid_mutation_name_fails(tmp_path: Path) -> None:
    result = run_cli("generate", str(SCHEMA), "--mutations", "nope", "-o", str(tmp_path / "x"))
    assert result.returncode == 2
    assert "unknown mutation" in result.stderr
