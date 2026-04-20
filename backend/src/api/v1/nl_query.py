"""Natural language query parsing endpoint."""

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from src.adapters.ai.nl_query_parser import extract_entities_from_text, parse_nl_query
from src.api.v1.auth.dependencies import get_current_user

router = APIRouter()


class NLQueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)


class NLQueryResponse(BaseModel):
    seed_inputs: list[dict[str, str]]
    suggested_scanners: list[str]
    intent: str
    confidence: float
    raw_query: str


class EntityExtractionRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=50000)


class EntityExtractionResponse(BaseModel):
    entities: list[dict[str, str]]
    count: int


@router.post("/nl-query/parse", response_model=NLQueryResponse)
async def parse_query(
    body: NLQueryRequest,
    current_user: Any = Depends(get_current_user),
) -> NLQueryResponse:
    """Parse a natural language query into investigation parameters."""
    result = parse_nl_query(body.query)
    return NLQueryResponse(
        seed_inputs=result.seed_inputs,
        suggested_scanners=result.suggested_scanners,
        intent=result.intent,
        confidence=result.confidence,
        raw_query=result.raw_query,
    )


@router.post("/nl-query/extract-entities", response_model=EntityExtractionResponse)
async def extract_entities(
    body: EntityExtractionRequest,
    current_user: Any = Depends(get_current_user),
) -> EntityExtractionResponse:
    """Extract OSINT-relevant entities from arbitrary text."""
    entities = extract_entities_from_text(body.text)
    return EntityExtractionResponse(entities=entities, count=len(entities))
