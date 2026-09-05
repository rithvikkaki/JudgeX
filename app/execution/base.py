"""Backend-agnostic contract for running one program against one input.

Every sandbox backend takes an :class:`ExecutionRequest` and returns an
:class:`ExecutionResult`.  The judge above them never needs to know whether the
code ran in a container or a resource-limited subprocess.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from enum import Enum


class Outcome(str, Enum):
    """How a single program run terminated."""

    OK = "ok"
    COMPILE_ERROR = "compile_error"
    TIMEOUT = "timeout"
    MEMORY_EXCEEDED = "memory_exceeded"
    OUTPUT_EXCEEDED = "output_exceeded"
    RUNTIME_ERROR = "runtime_error"
    INTERNAL_ERROR = "internal_error"


@dataclass(slots=True)
class ExecutionRequest:
    language: str
    source_code: str
    stdin: str = ""
    time_limit_ms: int = 2000
    memory_limit_mb: int = 128
    max_output_bytes: int = 64 * 1024


@dataclass(slots=True)
class ExecutionResult:
    outcome: Outcome
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    duration_ms: float = 0.0
    memory_kb: int = 0
    compile_output: str = ""
    detail: str = ""
    # Which backend produced this result - surfaced in the API so a reviewer
    # can tell container-isolated runs from fallback runs.
    backend: str = field(default="unknown")

    @property
    def ok(self) -> bool:
        return self.outcome is Outcome.OK


class SandboxBackend(abc.ABC):
    """Executes untrusted source code under resource limits."""

    name: str = "base"

    @abc.abstractmethod
    def is_available(self) -> bool:
        """Whether this backend can run right now on this host."""

    @abc.abstractmethod
    def run(self, request: ExecutionRequest) -> ExecutionResult:
        """Compile (if needed) and run ``request``, never raising."""

    def describe(self) -> dict:
        """Human-readable capability summary, exposed on ``/health``."""
        return {"backend": self.name, "available": self.is_available()}


def truncate(text: str, limit: int) -> tuple[str, bool]:
    """Clip ``text`` to ``limit`` bytes, reporting whether it was clipped."""
    encoded = text.encode("utf-8", errors="replace")
    if len(encoded) <= limit:
        return text, False
    clipped = encoded[:limit].decode("utf-8", errors="ignore")
    return clipped + "\n... [output truncated]", True
