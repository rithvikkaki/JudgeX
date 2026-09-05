"""Resource-limited subprocess backend.

This is the fallback used where a Docker daemon is not reachable - most
notably on free PaaS tiers, which do not expose the Docker socket to your
container.  On Linux it applies POSIX ``rlimit`` ceilings in the child before
``exec``:

* ``RLIMIT_AS``     - virtual address space (the memory cap)
* ``RLIMIT_CPU``    - CPU seconds, a backstop for the wall-clock timeout
* ``RLIMIT_NPROC``  - process count, which defeats fork bombs
* ``RLIMIT_FSIZE``  - maximum file size the program may write
* ``RLIMIT_CORE``   - disables core dumps

The child is also placed in its own process group so a timeout kills the whole
tree, not just the direct child.

**This is weaker than the Docker backend** - there is no filesystem or network
namespace, so it must only be used for a demo deployment or trusted input.
Prefer :mod:`app.execution.docker_backend` wherever a daemon is available.
"""

from __future__ import annotations

import logging
import os
import shutil
import signal
import subprocess
import tempfile
import threading
import time
from pathlib import Path

from app.config import settings
from app.execution.base import (
    ExecutionRequest,
    ExecutionResult,
    Outcome,
    SandboxBackend,
    truncate,
)
from app.execution.languages import LanguageSpec, get_language

logger = logging.getLogger(__name__)

IS_POSIX = os.name == "posix"

try:  # pragma: no cover - platform dependent
    import resource
except ImportError:  # Windows
    resource = None  # type: ignore[assignment]


class LocalBackend(SandboxBackend):
    name = "local"

    def is_available(self) -> bool:
        # Always usable; individual languages may still be missing a toolchain.
        return True

    def describe(self) -> dict:
        return {
            "backend": self.name,
            "available": settings.ALLOW_UNSAFE_LOCAL_EXECUTION,
            "unsafe_local_execution_allowed": settings.ALLOW_UNSAFE_LOCAL_EXECUTION,
            "rlimits_enforced": IS_POSIX and resource is not None,
            "toolchains": {
                spec.id: all(_which(binary) for binary in spec.local_requirements)
                for spec in _all_specs()
            },
            "warning": (
                "Subprocess execution has no network or filesystem namespace isolation. "
                "LocalBackend is unsafe for untrusted code in production."
            ),
        }

    # ------------------------------------------------------------------ #
    def run(self, request: ExecutionRequest) -> ExecutionResult:
        if not settings.ALLOW_UNSAFE_LOCAL_EXECUTION:
            return ExecutionResult(
                outcome=Outcome.INTERNAL_ERROR,
                detail=(
                    "Secure code execution infrastructure is unavailable. "
                    "Container sandbox is required for code execution in production "
                    "(ALLOW_UNSAFE_LOCAL_EXECUTION is False)."
                ),
                backend=self.name,
            )
        try:
            return self._run(request)
        except Exception as exc:  # noqa: BLE001 - the backend must never raise
            logger.exception("Local backend failed")
            return ExecutionResult(
                outcome=Outcome.INTERNAL_ERROR,
                detail=f"{type(exc).__name__}: {exc}",
                backend=self.name,
            )

    def _run(self, request: ExecutionRequest) -> ExecutionResult:
        try:
            spec = get_language(request.language)
        except ValueError as exc:
            return ExecutionResult(
                outcome=Outcome.INTERNAL_ERROR, detail=str(exc), backend=self.name
            )

        missing = [b for b in spec.local_requirements if not _which(b)]
        if missing:
            return ExecutionResult(
                outcome=Outcome.INTERNAL_ERROR,
                detail=(
                    f"Toolchain for {spec.display_name} is not installed on this "
                    f"host (missing: {', '.join(missing)})."
                ),
                backend=self.name,
            )

        staging = settings.execution_workdir
        if staging:
            os.makedirs(staging, exist_ok=True)

        with tempfile.TemporaryDirectory(prefix="judge-", dir=staging) as workdir:
            base = Path(workdir)
            (base / spec.source_filename).write_text(
                request.source_code, encoding="utf-8"
            )

            if spec.needs_compile:
                error = self._compile(spec, workdir, request)
                if error is not None:
                    return error

            return self._execute(spec, workdir, request)

    # ------------------------------------------------------------------ #
    def _compile(
        self, spec: LanguageSpec, workdir: str, request: ExecutionRequest
    ) -> ExecutionResult | None:
        assert spec.compile_cmd is not None
        argv = _resolve_argv(spec.compile_cmd, workdir)

        try:
            completed = subprocess.run(
                argv,
                cwd=workdir,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=settings.EXECUTION_COMPILE_TIMEOUT_S,
                env=_sandbox_env(),
            )
        except subprocess.TimeoutExpired:
            return ExecutionResult(
                outcome=Outcome.COMPILE_ERROR,
                compile_output="Compilation timed out",
                backend=self.name,
            )
        except Exception as exc:  # noqa: BLE001 - see _execute for the rationale
            logger.exception("Local compilation failed to start")
            return ExecutionResult(
                outcome=Outcome.INTERNAL_ERROR,
                detail=f"Failed to start compiler: {type(exc).__name__}: {exc}",
                backend=self.name,
            )

        if completed.returncode != 0:
            message = (completed.stderr or completed.stdout).strip()
            return ExecutionResult(
                outcome=Outcome.COMPILE_ERROR,
                compile_output=message or "Compilation failed",
                exit_code=completed.returncode,
                backend=self.name,
            )

        return None

    def _execute(
        self, spec: LanguageSpec, workdir: str, request: ExecutionRequest
    ) -> ExecutionResult:
        argv = _resolve_argv(spec.render_run_cmd(request.memory_limit_mb), workdir)
        timeout_s = request.time_limit_ms / 1000

        preexec = (
            _build_preexec(spec, request)
            if IS_POSIX and resource is not None
            else None
        )

        started = time.perf_counter()
        monitor: _PeakMemoryMonitor | None = None

        try:
            process = subprocess.Popen(  # noqa: S603
                argv,
                cwd=workdir,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=_sandbox_env(),
                preexec_fn=preexec,  # noqa: PLW1509 - intentional, POSIX only
                start_new_session=IS_POSIX,
            )

            # Sample this specific child's peak RSS while it runs. The previous
            # approach diffed getrusage(RUSAGE_CHILDREN).ru_maxrss, which is a
            # high-water mark across *every* child the process has ever reaped —
            # so it reported 0 for any run that did not beat the all-time peak.
            monitor = _PeakMemoryMonitor(process.pid)
            monitor.start()

            stdout_text, stderr_text = process.communicate(
                input=request.stdin, timeout=timeout_s
            )
            returncode = process.returncode
            memory_kb = monitor.stop()

        except subprocess.TimeoutExpired:
            if monitor is not None:
                memory_kb = monitor.stop()
            _terminate_tree(process)
            return ExecutionResult(
                outcome=Outcome.TIMEOUT,
                duration_ms=round(timeout_s * 1000, 2),
                exit_code=-1,
                memory_kb=memory_kb if monitor is not None else 0,
                backend=self.name,
            )
        except MemoryError:
            return ExecutionResult(
                outcome=Outcome.MEMORY_EXCEEDED,
                duration_ms=round((time.perf_counter() - started) * 1000, 2),
                backend=self.name,
            )
        except Exception as exc:  # noqa: BLE001
            # Deliberately broad. A sandbox backend must never raise: the judge
            # turns an ExecutionResult into a verdict, whereas an exception
            # becomes a 500 and the user loses their submission. OSError covers
            # a missing binary, but subprocess also raises SubprocessError for
            # preexec_fn failures, and the detail is worth surfacing either way.
            logger.exception("Local execution failed to start")
            return ExecutionResult(
                outcome=Outcome.INTERNAL_ERROR,
                detail=f"Failed to start program: {type(exc).__name__}: {exc}",
                backend=self.name,
            )

        duration_ms = (time.perf_counter() - started) * 1000

        stdout, stdout_clipped = truncate(stdout_text, request.max_output_bytes)
        stderr, _ = truncate(stderr_text, request.max_output_bytes)

        if stdout_clipped:
            return ExecutionResult(
                outcome=Outcome.OUTPUT_EXCEEDED,
                stdout=stdout,
                stderr=stderr,
                exit_code=returncode,
                duration_ms=round(duration_ms, 2),
                memory_kb=memory_kb,
                backend=self.name,
            )

        if returncode != 0:
            # A process killed by SIGSEGV/SIGKILL after hitting RLIMIT_AS, or a
            # JVM that reports an OOM, is a memory violation rather than a plain
            # runtime error.
            if _looks_like_oom(returncode, stderr, memory_kb, request):
                outcome = Outcome.MEMORY_EXCEEDED
            else:
                outcome = Outcome.RUNTIME_ERROR
            return ExecutionResult(
                outcome=outcome,
                stdout=stdout,
                stderr=stderr,
                exit_code=returncode,
                duration_ms=round(duration_ms, 2),
                memory_kb=memory_kb,
                backend=self.name,
            )

        return ExecutionResult(
            outcome=Outcome.OK,
            stdout=stdout,
            stderr=stderr,
            exit_code=0,
            duration_ms=round(duration_ms, 2),
            memory_kb=memory_kb,
            backend=self.name,
        )


# ---------------------------------------------------------------------- #
# Helpers
# ---------------------------------------------------------------------- #
def _all_specs() -> list[LanguageSpec]:
    from app.execution.languages import LANGUAGES

    return list(LANGUAGES.values())


def _which(binary: str) -> str | None:
    if binary == "python":
        return shutil.which("python") or shutil.which("python3") or sys.executable
    return shutil.which(binary)


def _resolve_argv(argv: list[str], workdir: str) -> list[str]:
    """Map logical argv onto real paths for this host."""
    resolved: list[str] = []
    for index, part in enumerate(argv):
        if index == 0:
            if part.startswith("./"):
                # A compiled artefact living in the sandbox directory.
                resolved.append(str(Path(workdir) / part[2:]))
                continue
            resolved.append(_which(part) or part)
            continue
        resolved.append(part)
    return resolved


def _sandbox_env() -> dict[str, str]:
    """A deliberately minimal environment for the child process."""
    env = {
        "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
        "HOME": tempfile.gettempdir(),
        "LANG": "C.UTF-8",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONIOENCODING": "utf-8",
    }
    if os.name == "nt":  # Windows needs these to start any process at all.
        for key in ("SYSTEMROOT", "SystemRoot", "TEMP", "TMP", "COMSPEC"):
            if key in os.environ:
                env[key] = os.environ[key]
    return env


def _build_preexec(spec: LanguageSpec, request: ExecutionRequest):  # pragma: no cover
    """Build the POSIX ``preexec_fn`` that installs rlimits in the child."""
    memory_bytes = request.memory_limit_mb * 1024 * 1024
    cpu_seconds = max(1, int(request.time_limit_ms / 1000) + 1)
    apply_address_space = spec.supports_address_space_limit
    max_output = request.max_output_bytes

    def _limit() -> None:
        assert resource is not None
        # NB: do NOT call os.setsid() here. `start_new_session=True` already
        # does it, and CPython runs setsid() *before* preexec_fn - so a second
        # call fails with EPERM (the child is already a session leader).
        # CPython reports any preexec_fn failure as SubprocessError, which is
        # not an OSError, so it escapes narrow handlers and 500s the request.

        if apply_address_space:
            resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))

        resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds + 1))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        # Cap what the program may write to disk, generously above the output
        # ceiling so legitimate buffering is unaffected.
        file_cap = max(max_output * 8, 1024 * 1024)
        resource.setrlimit(resource.RLIMIT_FSIZE, (file_cap, file_cap))

        try:
            resource.setrlimit(resource.RLIMIT_NPROC, (256, 256))
        except (ValueError, OSError):
            # Some containers already sit at a lower hard limit; not fatal.
            pass

    return _limit


class _PeakMemoryMonitor(threading.Thread):
    """Samples one process's peak resident memory while it runs.

    On Linux, ``/proc/<pid>/status`` exposes ``VmHWM`` — the kernel's own
    high-water mark for that process — so a single read after the fact would be
    exact. It is polled instead because the file disappears the moment the
    process exits, and a short-lived program can finish before the first read.

    Elsewhere there is no cheap per-process equivalent, so this reports 0 and
    ``/health`` advertises memory reporting as unavailable.
    """

    def __init__(self, pid: int) -> None:
        super().__init__(daemon=True)
        self._pid = pid
        self._peak_kb = 0
        self._stop_event = threading.Event()

    def run(self) -> None:  # pragma: no cover - timing dependent
        status_path = f"/proc/{self._pid}/status"
        while not self._stop_event.is_set():
            try:
                with open(status_path, encoding="ascii") as handle:
                    for line in handle:
                        if line.startswith("VmHWM:"):
                            self._peak_kb = max(
                                self._peak_kb, int(line.split()[1])
                            )
                            break
            except (OSError, ValueError, IndexError):
                # The process exited, or this is not Linux. Either way the last
                # sample we took is the best answer available.
                break
            self._stop_event.wait(0.01)

    def stop(self) -> int:
        self._stop_event.set()
        self.join(timeout=0.3)
        return self._peak_kb


def _terminate_tree(process: subprocess.Popen) -> None:
    """Kill the whole process group, not just the direct child."""
    try:
        if IS_POSIX:
            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
        else:
            process.kill()
    except (OSError, ProcessLookupError):
        pass
    finally:
        try:
            process.wait(timeout=2)
        except Exception:  # noqa: BLE001 - best-effort reap
            pass


def _looks_like_oom(
    returncode: int, stderr: str, memory_kb: int, request: ExecutionRequest
) -> bool:
    if "OutOfMemoryError" in stderr or "MemoryError" in stderr:
        return True
    if memory_kb >= request.memory_limit_mb * 1024 * 0.95:
        return True
    # Negative return codes are signals on POSIX; -9 is SIGKILL (the OOM
    # killer) and -11 is SIGSEGV, the usual symptom of hitting RLIMIT_AS.
    return returncode in (-9, -11) and memory_kb > 0
