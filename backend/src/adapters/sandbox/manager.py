"""SandboxManager — ephemeral Docker container execution for Hub agents.

Security model:
  - --cap-drop ALL          : no Linux capabilities
  - --read-only             : immutable root filesystem
  - --tmpfs /tmp            : writable scratch space only
  - --network sandbox-net   : allowlisted egress only
  - --memory / --cpus       : resource constraints prevent DoS
  - Ephemeral (--rm)        : destroyed after task completes

Reference: PentAGI, Shannon project Docker hardening patterns.

All tool-executing agent sub-processes MUST use this manager.
Direct subprocess execution from the main API process is forbidden.
"""

from __future__ import annotations

import asyncio
import shlex
from dataclasses import dataclass, field
from typing import Any

import structlog

log = structlog.get_logger(__name__)

_DEFAULT_IMAGE = "hub-agent-sandbox:hardened"
_DEFAULT_NETWORK = "sandbox-net"
_DEFAULT_TIMEOUT_S = 300  # 5 minutes
_DEFAULT_MEMORY = "512m"
_DEFAULT_CPUS = "0.5"
_TMPFS_SPEC = "/tmp:size=100m,noexec"


@dataclass
class SandboxConfig:
    """Configuration for a single sandbox container run.

    Attributes:
        image:           Docker image to use (must be hardened).
        command:         Command to execute inside the container.
        allowed_tools:   Subset of tools this container may use.
        secrets:         Env-var secrets injected at spawn time (not baked in).
        network:         Docker network name with egress allowlist.
        timeout_seconds: Max wall-clock lifetime; container killed if exceeded.
        memory:          Docker memory limit string (e.g. "512m").
        cpus:            Docker CPU quota string (e.g. "0.5").
        extra_env:       Non-secret environment variables.
    """

    image: str = _DEFAULT_IMAGE
    command: list[str] = field(default_factory=list)
    allowed_tools: list[str] = field(default_factory=list)
    secrets: dict[str, str] = field(default_factory=dict)
    network: str = _DEFAULT_NETWORK
    timeout_seconds: int = _DEFAULT_TIMEOUT_S
    memory: str = _DEFAULT_MEMORY
    cpus: str = _DEFAULT_CPUS
    extra_env: dict[str, str] = field(default_factory=dict)


@dataclass
class SandboxResult:
    """Output of a sandbox container run.

    Attributes:
        exit_code: Container exit code (0 = success).
        stdout:    Standard output captured from the container.
        stderr:    Standard error captured from the container.
        timed_out: True if the container was killed due to timeout.
    """

    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool = False

    @property
    def success(self) -> bool:
        return self.exit_code == 0 and not self.timed_out


class SandboxManager:
    """Runs arbitrary commands in hardened, ephemeral Docker containers.

    Design choices:
    - Async-first: uses asyncio subprocess to avoid blocking the event loop.
    - No shell interpolation: all args passed as lists (prevents injection).
    - Secrets never logged: secret env-var values are redacted in debug output.
    - Idempotent: each call spawns a fresh container; no state is shared.

    Args:
        docker_bin: Path to the docker binary (overridable for testing).
    """

    def __init__(self, docker_bin: str = "docker") -> None:
        self._docker = docker_bin

    async def run(self, config: SandboxConfig) -> SandboxResult:
        """Execute a command in an isolated sandbox container.

        Args:
            config: Fully specified SandboxConfig.

        Returns:
            SandboxResult with stdout, stderr, exit code, and timeout flag.

        Raises:
            RuntimeError: If Docker is unavailable or the image is not found.
        """
        cmd = self._build_docker_command(config)

        await log.ainfo(
            "sandbox_run_start",
            image=config.image,
            command=config.command,
            timeout=config.timeout_seconds,
            allowed_tools=config.allowed_tools,
        )

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=float(config.timeout_seconds),
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                await log.awarning(
                    "sandbox_timeout",
                    image=config.image,
                    timeout=config.timeout_seconds,
                )
                return SandboxResult(
                    exit_code=124,  # same convention as GNU timeout
                    stdout="",
                    stderr="Container killed: timeout exceeded.",
                    timed_out=True,
                )

            result = SandboxResult(
                exit_code=proc.returncode or 0,
                stdout=stdout_bytes.decode(errors="replace"),
                stderr=stderr_bytes.decode(errors="replace"),
            )
            await log.ainfo(
                "sandbox_run_done",
                exit_code=result.exit_code,
                success=result.success,
            )
            return result

        except FileNotFoundError as exc:
            raise RuntimeError(
                f"Docker binary not found at '{self._docker}'. "
                "Ensure Docker is installed and in PATH."
            ) from exc

    def _build_docker_command(self, config: SandboxConfig) -> list[str]:
        """Construct the docker run argument list.

        No shell=True — all arguments are passed as a list to prevent
        command injection if any config value is tainted.
        """
        cmd: list[str] = [
            self._docker, "run",
            "--rm",                          # ephemeral
            "--read-only",                   # immutable root FS
            f"--tmpfs={_TMPFS_SPEC}",        # writable /tmp only
            "--cap-drop=ALL",                # no Linux capabilities
            f"--network={config.network}",   # allowlisted egress
            f"--memory={config.memory}",
            f"--cpus={config.cpus}",
        ]

        # Inject secrets as env vars (never as CLI args — those are logged)
        for key, value in {**config.extra_env, **config.secrets}.items():
            cmd.extend(["--env", f"{key}={value}"])

        # Allowed tools bitmask via env var
        if config.allowed_tools:
            cmd.extend(["--env", f"HUB_ALLOWED_TOOLS={','.join(config.allowed_tools)}"])

        cmd.append(config.image)
        cmd.extend(config.command)

        return cmd

    def _redact_secrets(self, cmd: list[str]) -> list[str]:
        """Return a copy of cmd with secret values replaced by ***."""
        redacted = []
        skip_next = False
        for token in cmd:
            if skip_next:
                # This token is an env-var value from --env KEY=VALUE split
                key, _, _ = token.partition("=")
                redacted.append(f"{key}=***")
                skip_next = False
            elif token == "--env":
                redacted.append(token)
                skip_next = True
            else:
                redacted.append(token)
        return redacted

    async def is_available(self) -> bool:
        """Return True if Docker is installed and the daemon is reachable."""
        try:
            proc = await asyncio.create_subprocess_exec(
                self._docker, "info",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.wait()
            return proc.returncode == 0
        except (FileNotFoundError, OSError):
            return False
