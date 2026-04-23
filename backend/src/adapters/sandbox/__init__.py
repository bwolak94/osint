"""Docker sandbox adapter — least-privilege ephemeral container execution."""

from .manager import SandboxConfig, SandboxManager, SandboxResult

__all__ = ["SandboxManager", "SandboxConfig", "SandboxResult"]
