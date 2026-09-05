"""Docker-sandboxed execution backend.

Each program runs in a throw-away container with, per submission:

* **no network** (``network_disabled``),
* a **hard memory cap** with swap pinned to the same value, so a program cannot
  escape the cap by swapping,
* a **CPU quota** expressed as a percentage of one core,
* a **process cap** (``pids_limit``) that defeats fork bombs,
* a **read-only root filesystem** plus a small ``tmpfs`` for scratch space,
* **all Linux capabilities dropped** and ``no-new-privileges`` set,
* execution as an **unprivileged uid**, never root,
* a **wall-clock timeout** enforced by the host, independent of the guest.

Compilation and execution happen in *separate* containers: the compile step
gets a writable mount, the run step gets a read-only one.  That split is what
lets the judge distinguish a Compilation Error from a Runtime Error.
"""

from __future__ import annotations

import logging
import os
import shlex
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

#: uid/gid used inside containers - `nobody` on every mainstream base image.
_SANDBOX_UID = "65534:65534"
_WORKDIR = "/sandbox"


class DockerBackend(SandboxBackend):
    name = "docker"

    def __init__(self) -> None:
        self._client = None
        self._probed = False
        self._probe_error: str = ""

    # ------------------------------------------------------------------ #
    # Client management
    # ------------------------------------------------------------------ #
    def _get_client(self):
        if self._probed:
            return self._client

        self._probed = True
        try:
            import docker  # imported lazily so the package stays optional

            client = docker.from_env()
            client.ping()
            self._client = client
        except Exception as exc:  # noqa: BLE001 - any failure means "no Docker"
            self._probe_error = f"{type(exc).__name__}: {exc}"
            logger.warning("Docker backend unavailable: %s", self._probe_error)
            self._client = None

        return self._client

    def is_available(self) -> bool:
        return self._get_client() is not None

    def describe(self) -> dict:
        info = {"backend": self.name, "available": self.is_available()}
        if not info["available"]:
            info["reason"] = self._probe_error or "Docker daemon not reachable"
        info["isolation"] = {
            "network": "disabled",
            "memory_limit_mb": settings.EXECUTION_MEMORY_LIMIT_MB,
            "cpu_quota_percent": settings.EXECUTION_CPU_QUOTA_PERCENT,
            "pids_limit": settings.EXECUTION_PIDS_LIMIT,
            "read_only_rootfs": True,
            "capabilities": "all dropped",
            "user": "nobody (65534)",
        }
        return info

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def run(self, request: ExecutionRequest) -> ExecutionResult:
        client = self._get_client()
        if client is None:
            return ExecutionResult(
                outcome=Outcome.INTERNAL_ERROR,
                detail=self._probe_error or "Docker daemon is not reachable",
                backend=self.name,
            )

        try:
            spec = get_language(request.language)
        except ValueError as exc:
            return ExecutionResult(
                outcome=Outcome.INTERNAL_ERROR, detail=str(exc), backend=self.name
            )

        # Staged under EXECUTION_WORKDIR when set, so that the path the daemon
        # is asked to bind-mount also exists on the host - see the setting's
        # documentation for why that matters when the API is containerised.
        staging = settings.execution_workdir
        if staging:
            os.makedirs(staging, exist_ok=True)

        with tempfile.TemporaryDirectory(prefix="judge-", dir=staging) as workdir:
            try:
                self._materialise(workdir, spec, request)
            except OSError as exc:
                return ExecutionResult(
                    outcome=Outcome.INTERNAL_ERROR,
                    detail=f"Failed to stage sandbox: {exc}",
                    backend=self.name,
                )

            if spec.needs_compile:
                compile_result = self._compile(client, workdir, spec, request)
                if compile_result is not None:
                    return compile_result

            return self._execute(client, workdir, spec, request)

    # ------------------------------------------------------------------ #
    # Stages
    # ------------------------------------------------------------------ #
    def _materialise(
        self, workdir: str, spec: LanguageSpec, request: ExecutionRequest
    ) -> None:
        base = Path(workdir)
        (base / spec.source_filename).write_text(request.source_code, encoding="utf-8")
        (base / "input.txt").write_text(request.stdin, encoding="utf-8")

        # Prefer ownership transfer to container UID/GID (nobody: 65534:65534)
        # with restrictive 0700 directory / 0600 file permissions.
        try:
            os.chown(base, 65534, 65534)
            for child in base.iterdir():
                os.chown(child, 65534, 65534)
                os.chmod(child, 0o600)
            os.chmod(base, 0o700)
        except (AttributeError, OSError, PermissionError):
            # Fallback for non-root host process or Windows host where chown is unavailable:
            # Grant minimal read access for container user while avoiding world-writable 0777/0666.
            os.chmod(base, 0o755)
            for child in base.iterdir():
                os.chmod(child, 0o644)

    def _compile(
        self,
        client,
        workdir: str,
        spec: LanguageSpec,
        request: ExecutionRequest,
    ) -> ExecutionResult | None:
        """Return an error result on failure, or ``None`` when compilation succeeded."""
        assert spec.compile_cmd is not None

        outcome = self._run_container(
            client,
            workdir=workdir,
            image=spec.docker_image,
            argv=spec.compile_cmd,
            stdin_file=None,
            timeout_s=settings.EXECUTION_COMPILE_TIMEOUT_S,
            # Compilers are memory hungry; give them headroom but stay bounded.
            memory_limit_mb=max(request.memory_limit_mb, 512),
            writable=True,
            max_output_bytes=request.max_output_bytes,
        )

        if outcome.outcome is Outcome.TIMEOUT:
            return ExecutionResult(
                outcome=Outcome.COMPILE_ERROR,
                compile_output="Compilation timed out",
                detail="compile timeout",
                backend=self.name,
            )

        if outcome.outcome is Outcome.INTERNAL_ERROR:
            return outcome

        if outcome.exit_code != 0:
            message = (outcome.stderr or outcome.stdout).strip()
            return ExecutionResult(
                outcome=Outcome.COMPILE_ERROR,
                compile_output=message or "Compilation failed",
                exit_code=outcome.exit_code,
                backend=self.name,
            )

        return None

    def _execute(
        self,
        client,
        workdir: str,
        spec: LanguageSpec,
        request: ExecutionRequest,
    ) -> ExecutionResult:
        return self._run_container(
            client,
            workdir=workdir,
            image=spec.docker_image,
            argv=spec.render_run_cmd(request.memory_limit_mb),
            stdin_file="input.txt",
            timeout_s=request.time_limit_ms / 1000,
            memory_limit_mb=request.memory_limit_mb,
            writable=False,
            max_output_bytes=request.max_output_bytes,
        )

    # ------------------------------------------------------------------ #
    # Container driver
    # ------------------------------------------------------------------ #
    def _run_container(
        self,
        client,
        *,
        workdir: str,
        image: str,
        argv: list[str],
        stdin_file: str | None,
        timeout_s: float,
        memory_limit_mb: int,
        writable: bool,
        max_output_bytes: int,
    ) -> ExecutionResult:
        command = " ".join(shlex.quote(part) for part in argv)
        if stdin_file:
            command = f"{command} < {shlex.quote(stdin_file)}"

        memory = f"{memory_limit_mb}m"
        container = None
        monitor: _MemoryMonitor | None = None

        try:
            container = client.containers.create(
                image=image,
                command=["/bin/sh", "-c", command],
                working_dir=_WORKDIR,
                volumes={
                    workdir: {"bind": _WORKDIR, "mode": "rw" if writable else "ro"}
                },
                # --- isolation -------------------------------------------
                network_disabled=True,
                mem_limit=memory,
                # Pinning swap to the memory limit means the cgroup cannot use
                # any swap, so the cap is a true ceiling.
                memswap_limit=memory,
                cpu_period=100_000,
                cpu_quota=int(100_000 * settings.EXECUTION_CPU_QUOTA_PERCENT / 100),
                pids_limit=settings.EXECUTION_PIDS_LIMIT,
                read_only=True,
                tmpfs={"/tmp": f"rw,noexec,nosuid,size={min(memory_limit_mb, 64)}m"},
                cap_drop=["ALL"],
                security_opt=["no-new-privileges:true"],
                user=_SANDBOX_UID,
                # --- housekeeping ----------------------------------------
                stdin_open=False,
                tty=False,
                detach=True,
                environment={"HOME": "/tmp", "PYTHONDONTWRITEBYTECODE": "1"},
            )

            started = time.perf_counter()
            container.start()

            monitor = _MemoryMonitor(container)
            monitor.start()

            try:
                status = container.wait(timeout=timeout_s + 0.5)
                exit_code = int(status.get("StatusCode", -1))
            except Exception:  # noqa: BLE001 - docker raises several types here
                duration_ms = (time.perf_counter() - started) * 1000
                _safe_kill(container)
                return ExecutionResult(
                    outcome=Outcome.TIMEOUT,
                    duration_ms=round(duration_ms, 2),
                    memory_kb=monitor.stop(),
                    exit_code=-1,
                    backend=self.name,
                )

            duration_ms = (time.perf_counter() - started) * 1000
            memory_kb = monitor.stop()

            stdout_raw = container.logs(stdout=True, stderr=False).decode(
                "utf-8", errors="replace"
            )
            stderr_raw = container.logs(stdout=False, stderr=True).decode(
                "utf-8", errors="replace"
            )

            stdout, stdout_clipped = truncate(stdout_raw, max_output_bytes)
            stderr, _ = truncate(stderr_raw, max_output_bytes)

            if _was_oom_killed(container):
                return ExecutionResult(
                    outcome=Outcome.MEMORY_EXCEEDED,
                    stdout=stdout,
                    stderr=stderr,
                    exit_code=exit_code,
                    duration_ms=round(duration_ms, 2),
                    memory_kb=max(memory_kb, memory_limit_mb * 1024),
                    backend=self.name,
                )

            if stdout_clipped:
                return ExecutionResult(
                    outcome=Outcome.OUTPUT_EXCEEDED,
                    stdout=stdout,
                    stderr=stderr,
                    exit_code=exit_code,
                    duration_ms=round(duration_ms, 2),
                    memory_kb=memory_kb,
                    backend=self.name,
                )

            outcome = Outcome.OK if exit_code == 0 else Outcome.RUNTIME_ERROR
            return ExecutionResult(
                outcome=outcome,
                stdout=stdout,
                stderr=stderr,
                exit_code=exit_code,
                duration_ms=round(duration_ms, 2),
                memory_kb=memory_kb,
                backend=self.name,
            )

        except Exception as exc:  # noqa: BLE001 - never let the judge crash
            logger.exception("Docker execution failed")
            if monitor is not None:
                monitor.stop()
            return ExecutionResult(
                outcome=Outcome.INTERNAL_ERROR,
                detail=f"{type(exc).__name__}: {exc}",
                backend=self.name,
            )

        finally:
            if container is not None:
                try:
                    container.remove(force=True)
                except Exception:  # noqa: BLE001 - best-effort cleanup
                    logger.warning("Failed to remove container", exc_info=True)


class _MemoryMonitor(threading.Thread):
    """Samples container memory so the API can report a real peak.

    Docker exposes ``memory_stats.max_usage`` only on cgroup v1, so this polls
    the live stats stream and keeps the maximum it observed.
    """

    def __init__(self, container) -> None:
        super().__init__(daemon=True)
        self._container = container
        self._peak_bytes = 0
        self._stop_event = threading.Event()

    def run(self) -> None:  # pragma: no cover - timing dependent
        try:
            for stat in self._container.stats(stream=True, decode=True):
                if self._stop_event.is_set():
                    break
                mem = stat.get("memory_stats") or {}
                usage = mem.get("max_usage") or mem.get("usage") or 0
                self._peak_bytes = max(self._peak_bytes, int(usage))
        except Exception:  # noqa: BLE001 - the stream dies with the container
            pass

    def stop(self) -> int:
        """Signal the sampler to finish and return the peak in kilobytes."""
        self._stop_event.set()
        self.join(timeout=0.5)
        return self._peak_bytes // 1024


def _was_oom_killed(container) -> bool:
    try:
        container.reload()
        return bool(container.attrs.get("State", {}).get("OOMKilled", False))
    except Exception:  # noqa: BLE001
        return False


def _safe_kill(container) -> None:
    try:
        container.kill()
    except Exception:  # noqa: BLE001 - it may already be dead
        pass
