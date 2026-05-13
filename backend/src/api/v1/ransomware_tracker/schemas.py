from __future__ import annotations
from pydantic import BaseModel


class RansomwareTrackerRequest(BaseModel):
    query: str  # company name, domain, or ransomware group name


class RansomwareVictimSchema(BaseModel):
    victim: str
    group: str | None = None
    country: str | None = None
    activity: str | None = None
    discovered: str | None = None
    description: str | None = None
    url: str | None = None
    tags: list[str] = []


class RansomwareGroupSchema(BaseModel):
    name: str
    description: str | None = None
    locations: list[str] = []
    profile_url: str | None = None


class RansomwareTrackerResponse(BaseModel):
    query: str
    total_victims: int
    victims: list[RansomwareVictimSchema] = []
    group_info: RansomwareGroupSchema | None = None
