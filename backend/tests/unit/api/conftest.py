"""Shared test fixtures for API unit tests.

Stubs optional third-party packages (jose, pyotp, etc.) so that API modules
can be imported without installing every dependency locally.
"""

import sys
import types
from unittest.mock import MagicMock


def _ensure_module(name: str) -> types.ModuleType:
    if name in sys.modules:
        return sys.modules[name]
    mod = MagicMock()
    mod.__name__ = name
    mod.__package__ = name.rsplit(".", 1)[0] if "." in name else name
    mod.__path__ = []
    mod.__spec__ = None
    sys.modules[name] = mod
    return mod


for _pkg in [
    "jose", "jose.jwt", "pyotp", "asyncpg", "redis", "redis.asyncio",
    "bcrypt", "neo4j", "qrcode", "holehe", "holehe.core", "holehe.modules",
    "celery", "openai", "anthropic",
]:
    _ensure_module(_pkg)

# Stub database module to prevent real DB connections
_db_mod_name = "src.adapters.db.database"
if _db_mod_name not in sys.modules:
    _db_mod = types.ModuleType(_db_mod_name)
    _db_mod.engine = MagicMock()  # type: ignore[attr-defined]
    _db_mod.async_session_factory = MagicMock()  # type: ignore[attr-defined]
    sys.modules[_db_mod_name] = _db_mod
