"""Custom tool container management.

Operators can register Docker-image-based tools that the scan orchestrator
can invoke alongside built-in tools.

Endpoints:
  GET    /api/v1/tools/custom              — list custom tools
  POST   /api/v1/tools/custom              — register a new tool
  GET    /api/v1/tools/custom/{tool_id}    — get tool detail
  PUT    /api/v1/tools/custom/{tool_id}    — update tool
  DELETE /api/v1/tools/custom/{tool_id}    — deregister tool
  POST   /api/v1/tools/custom/{tool_id}/test — run a smoke test
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from src.api.v1.pentesting.dependencies import require_pentester
from src.core.domain.entities.user import User

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/tools/custom", tags=["custom-tools"])

UserDep = Annotated[User, Depends(require_pentester)]

# ---------------------------------------------------------------------------
# In-memory store (replace with DB table in production migration)
# ---------------------------------------------------------------------------

_store: dict[str, "CustomTool"] = {}


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class CustomToolCreate(BaseModel):
    name: str
    description: str = ""
    docker_image: str           # e.g. "ghcr.io/myorg/my-scanner:latest"
    entrypoint: list[str] = []  # override container ENTRYPOINT
    default_args: list[str] = []
    env_vars: dict[str, str] = {}
    output_parser: str = "text"  # "text" | "json" | "sarif"
    tags: list[str] = []


class CustomToolUpdate(BaseModel):
    description: str | None = None
    docker_image: str | None = None
    entrypoint: list[str] | None = None
    default_args: list[str] | None = None
    env_vars: dict[str, str] | None = None
    output_parser: str | None = None
    tags: list[str] | None = None


class CustomTool(BaseModel):
    id: str
    name: str
    description: str
    docker_image: str
    entrypoint: list[str]
    default_args: list[str]
    env_vars: dict[str, str]
    output_parser: str
    tags: list[str]
    created_by: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TestRunResult(BaseModel):
    tool_id: str
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("", response_model=list[CustomTool])
async def list_custom_tools(current_user: UserDep) -> list[CustomTool]:  # noqa: ARG001
    return list(_store.values())


@router.post("", response_model=CustomTool, status_code=status.HTTP_201_CREATED)
async def create_custom_tool(body: CustomToolCreate, current_user: UserDep) -> CustomTool:
    now = datetime.now(timezone.utc)
    tool = CustomTool(
        id=str(uuid.uuid4()),
        name=body.name,
        description=body.description,
        docker_image=body.docker_image,
        entrypoint=body.entrypoint,
        default_args=body.default_args,
        env_vars=body.env_vars,
        output_parser=body.output_parser,
        tags=body.tags,
        created_by=str(current_user.id),
        created_at=now,
        updated_at=now,
    )
    _store[tool.id] = tool
    await log.ainfo("custom_tool_created", tool_id=tool.id, image=tool.docker_image)
    return tool


@router.get("/{tool_id}", response_model=CustomTool)
async def get_custom_tool(tool_id: str, current_user: UserDep) -> CustomTool:  # noqa: ARG001
    tool = _store.get(tool_id)
    if tool is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tool not found.")
    return tool


@router.put("/{tool_id}", response_model=CustomTool)
async def update_custom_tool(
    tool_id: str,
    body: CustomToolUpdate,
    current_user: UserDep,  # noqa: ARG001
) -> CustomTool:
    tool = _store.get(tool_id)
    if tool is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tool not found.")
    data = tool.model_dump()
    for field, val in body.model_dump(exclude_none=True).items():
        data[field] = val
    data["updated_at"] = datetime.now(timezone.utc)
    updated = CustomTool(**data)
    _store[tool_id] = updated
    return updated


@router.delete("/{tool_id}", status_code=status.HTTP_200_OK)
async def delete_custom_tool(tool_id: str, current_user: UserDep) -> dict[str, str]:  # noqa: ARG001
    if tool_id not in _store:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tool not found.")
    del _store[tool_id]
    return {"status": "deleted"}


@router.post("/{tool_id}/test", response_model=TestRunResult)
async def test_custom_tool(tool_id: str, current_user: UserDep) -> TestRunResult:  # noqa: ARG001
    """Run the container with --help / --version and return stdout/stderr."""
    tool = _store.get(tool_id)
    if tool is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tool not found.")

    import asyncio
    import time

    cmd = ["docker", "run", "--rm", "--network", "none", tool.docker_image, "--version"]
    start = time.monotonic()
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout_bytes, stderr_bytes = await asyncio.wait_for(proc.communicate(), timeout=30)
        exit_code = proc.returncode or 0
    except asyncio.TimeoutError:
        return TestRunResult(
            tool_id=tool_id, exit_code=124,
            stdout="", stderr="Container timed out after 30s",
            duration_ms=30000,
        )
    except Exception as exc:
        return TestRunResult(
            tool_id=tool_id, exit_code=1,
            stdout="", stderr=str(exc),
            duration_ms=int((time.monotonic() - start) * 1000),
        )

    return TestRunResult(
        tool_id=tool_id,
        exit_code=exit_code,
        stdout=stdout_bytes.decode(errors="replace")[:4096],
        stderr=stderr_bytes.decode(errors="replace")[:4096],
        duration_ms=int((time.monotonic() - start) * 1000),
    )
