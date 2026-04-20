"""Ticket creation endpoints (TheHive, Jira, ServiceNow)."""

from typing import Any

import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from src.adapters.integrations.jira_adapter import JiraAdapter
from src.adapters.integrations.thehive_adapter import TheHiveAdapter
from src.api.v1.auth.dependencies import get_current_user

log = structlog.get_logger()
router = APIRouter()

_thehive: TheHiveAdapter | None = None
_jira: JiraAdapter | None = None


def get_thehive() -> TheHiveAdapter:
    global _thehive
    if _thehive is None:
        _thehive = TheHiveAdapter()
    return _thehive


def get_jira() -> JiraAdapter:
    global _jira
    if _jira is None:
        _jira = JiraAdapter()
    return _jira


class TheHiveCaseRequest(BaseModel):
    title: str = Field(..., min_length=1)
    description: str = ""
    severity: int = Field(2, ge=1, le=4)
    tags: list[str] = []


class JiraTicketRequest(BaseModel):
    summary: str = Field(..., min_length=1)
    description: str = ""
    issue_type: str = "Task"
    priority: str = "Medium"
    labels: list[str] = []


class ObservableRequest(BaseModel):
    case_id: str
    data_type: str
    data: str
    message: str = ""


@router.post("/ticketing/thehive/case")
async def create_thehive_case(
    body: TheHiveCaseRequest,
    current_user: Any = Depends(get_current_user),
    thehive: TheHiveAdapter = Depends(get_thehive),
) -> dict[str, Any]:
    return await thehive.create_case(body.title, body.description, body.severity, body.tags)


@router.post("/ticketing/thehive/observable")
async def add_thehive_observable(
    body: ObservableRequest,
    current_user: Any = Depends(get_current_user),
    thehive: TheHiveAdapter = Depends(get_thehive),
) -> dict[str, Any]:
    return await thehive.add_observable(body.case_id, body.data_type, body.data, body.message)


@router.get("/ticketing/thehive/test")
async def test_thehive(
    current_user: Any = Depends(get_current_user),
    thehive: TheHiveAdapter = Depends(get_thehive),
) -> dict[str, Any]:
    return await thehive.test_connection()


@router.post("/ticketing/jira/ticket")
async def create_jira_ticket(
    body: JiraTicketRequest,
    current_user: Any = Depends(get_current_user),
    jira: JiraAdapter = Depends(get_jira),
) -> dict[str, Any]:
    return await jira.create_ticket(body.summary, body.description, body.issue_type, body.priority, body.labels)


@router.get("/ticketing/jira/test")
async def test_jira(
    current_user: Any = Depends(get_current_user),
    jira: JiraAdapter = Depends(get_jira),
) -> dict[str, Any]:
    return await jira.test_connection()
