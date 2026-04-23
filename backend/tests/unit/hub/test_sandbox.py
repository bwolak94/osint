"""Tests for SandboxManager — Docker container execution, security, timeouts."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.adapters.sandbox.manager import SandboxConfig, SandboxManager, SandboxResult


class TestSandboxResult:
    def test_success_true_when_exit_0_no_timeout(self) -> None:
        r = SandboxResult(exit_code=0, stdout="ok", stderr="")
        assert r.success is True

    def test_success_false_when_nonzero_exit(self) -> None:
        r = SandboxResult(exit_code=1, stdout="", stderr="error")
        assert r.success is False

    def test_success_false_when_timed_out(self) -> None:
        r = SandboxResult(exit_code=0, stdout="", stderr="", timed_out=True)
        assert r.success is False


class TestSandboxConfig:
    def test_defaults(self) -> None:
        cfg = SandboxConfig()
        assert cfg.timeout_seconds == 300
        assert cfg.memory == "512m"
        assert cfg.cpus == "0.5"
        assert cfg.network == "sandbox-net"
        assert cfg.image == "hub-agent-sandbox:hardened"

    def test_custom_config(self) -> None:
        cfg = SandboxConfig(
            image="my-image:v1",
            command=["python", "run.py"],
            secrets={"KEY": "value"},
            timeout_seconds=60,
        )
        assert cfg.image == "my-image:v1"
        assert cfg.command == ["python", "run.py"]
        assert cfg.secrets == {"KEY": "value"}
        assert cfg.timeout_seconds == 60


class TestSandboxManagerBuildCommand:
    def _mgr(self) -> SandboxManager:
        return SandboxManager(docker_bin="docker")

    def test_contains_rm_flag(self) -> None:
        mgr = self._mgr()
        cfg = SandboxConfig(command=["echo", "hi"])
        cmd = mgr._build_docker_command(cfg)
        assert "--rm" in cmd

    def test_contains_read_only(self) -> None:
        mgr = self._mgr()
        cmd = mgr._build_docker_command(SandboxConfig())
        assert "--read-only" in cmd

    def test_contains_cap_drop_all(self) -> None:
        mgr = self._mgr()
        cmd = mgr._build_docker_command(SandboxConfig())
        assert "--cap-drop=ALL" in cmd

    def test_contains_memory_and_cpus(self) -> None:
        mgr = self._mgr()
        cmd = mgr._build_docker_command(SandboxConfig(memory="256m", cpus="0.25"))
        assert "--memory=256m" in cmd
        assert "--cpus=0.25" in cmd

    def test_secrets_injected_as_env_vars(self) -> None:
        mgr = self._mgr()
        cfg = SandboxConfig(secrets={"MY_SECRET": "s3cr3t"})
        cmd = mgr._build_docker_command(cfg)
        # Secret must appear as "MY_SECRET=s3cr3t" after --env
        joined = " ".join(cmd)
        assert "MY_SECRET=s3cr3t" in joined

    def test_allowed_tools_injected(self) -> None:
        mgr = self._mgr()
        cfg = SandboxConfig(allowed_tools=["web_search", "python_repl"])
        cmd = mgr._build_docker_command(cfg)
        joined = " ".join(cmd)
        assert "HUB_ALLOWED_TOOLS=web_search,python_repl" in joined

    def test_no_allowed_tools_not_injected(self) -> None:
        mgr = self._mgr()
        cfg = SandboxConfig(allowed_tools=[])
        cmd = mgr._build_docker_command(cfg)
        joined = " ".join(cmd)
        assert "HUB_ALLOWED_TOOLS" not in joined

    def test_image_appears_before_command(self) -> None:
        mgr = self._mgr()
        cfg = SandboxConfig(image="test-img:1", command=["echo", "hi"])
        cmd = mgr._build_docker_command(cfg)
        img_idx = cmd.index("test-img:1")
        echo_idx = cmd.index("echo")
        assert img_idx < echo_idx

    def test_network_flag_included(self) -> None:
        mgr = self._mgr()
        cfg = SandboxConfig(network="my-net")
        cmd = mgr._build_docker_command(cfg)
        assert "--network=my-net" in cmd


class TestSandboxManagerRedactSecrets:
    def test_redacts_env_values(self) -> None:
        mgr = SandboxManager()
        cmd = ["docker", "run", "--env", "SECRET=plaintext", "--env", "KEY=val"]
        redacted = mgr._redact_secrets(cmd)
        assert "plaintext" not in redacted
        assert "SECRET=***" in redacted
        assert "KEY=***" in redacted

    def test_non_env_tokens_unchanged(self) -> None:
        mgr = SandboxManager()
        cmd = ["docker", "run", "--rm", "my-image"]
        redacted = mgr._redact_secrets(cmd)
        assert redacted == cmd


class TestSandboxManagerRun:
    async def test_successful_run(self) -> None:
        mgr = SandboxManager()
        cfg = SandboxConfig(command=["echo", "hello"])

        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(b"hello\n", b""))

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            result = await mgr.run(cfg)

        assert result.exit_code == 0
        assert result.stdout == "hello\n"
        assert result.success is True

    async def test_nonzero_exit_captured(self) -> None:
        mgr = SandboxManager()
        cfg = SandboxConfig(command=["false"])

        mock_proc = MagicMock()
        mock_proc.returncode = 1
        mock_proc.communicate = AsyncMock(return_value=(b"", b"error"))

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            result = await mgr.run(cfg)

        assert result.exit_code == 1
        assert result.success is False

    async def test_timeout_kills_container(self) -> None:
        mgr = SandboxManager()
        cfg = SandboxConfig(timeout_seconds=1)

        mock_proc = MagicMock()
        mock_proc.kill = MagicMock()
        mock_proc.wait = AsyncMock()

        async def slow_communicate() -> tuple[bytes, bytes]:
            await asyncio.sleep(10)
            return b"", b""

        mock_proc.communicate = slow_communicate

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            result = await mgr.run(cfg)

        assert result.timed_out is True
        assert result.exit_code == 124
        assert result.success is False
        mock_proc.kill.assert_called_once()

    async def test_docker_not_found_raises_runtime_error(self) -> None:
        mgr = SandboxManager()
        cfg = SandboxConfig()

        with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError):
            with pytest.raises(RuntimeError, match="Docker binary not found"):
                await mgr.run(cfg)


class TestSandboxManagerIsAvailable:
    async def test_returns_true_when_docker_ok(self) -> None:
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.wait = AsyncMock()

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            mgr = SandboxManager()
            assert await mgr.is_available() is True

    async def test_returns_false_when_docker_missing(self) -> None:
        with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError):
            mgr = SandboxManager()
            assert await mgr.is_available() is False

    async def test_returns_false_when_docker_fails(self) -> None:
        mock_proc = MagicMock()
        mock_proc.returncode = 1
        mock_proc.wait = AsyncMock()

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            mgr = SandboxManager()
            assert await mgr.is_available() is False
