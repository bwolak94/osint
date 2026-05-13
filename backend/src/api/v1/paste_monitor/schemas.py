from __future__ import annotations
from pydantic import BaseModel


class PasteMonitorRequest(BaseModel):
    query: str  # email, domain, username, or keyword


class PasteMentionSchema(BaseModel):
    id: str
    title: str | None = None
    snippet: str | None = None
    url: str | None = None
    date: str | None = None
    source: str = "pastebin"
    tags: list[str] = []


class PasteMonitorResponse(BaseModel):
    query: str
    total: int
    mentions: list[PasteMentionSchema] = []
