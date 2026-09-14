"""Generate deterministic adversarial fixtures for LLM output consumers."""

from .fuzzer import FuzzConfig, generate_cases
from .model import Case

__all__ = ["Case", "FuzzConfig", "generate_cases"]
