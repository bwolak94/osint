"""Report redaction endpoints."""
from typing import Any

import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from src.adapters.security.pii_encryption import PIIEncryptor
from src.api.v1.auth.dependencies import get_current_user

log = structlog.get_logger()
router = APIRouter()

_encryptor: PIIEncryptor | None = None


def get_encryptor() -> PIIEncryptor:
    global _encryptor
    if _encryptor is None:
        _encryptor = PIIEncryptor()
    return _encryptor


class RedactRequest(BaseModel):
    data: dict[str, Any]
    mode: str = Field("mask", pattern="^(mask|hash|encrypt|remove)$")
    custom_fields: list[str] = []


class RedactResponse(BaseModel):
    data: dict[str, Any]
    mode: str
    fields_processed: int


class RedactionRuleCreate(BaseModel):
    name: str = Field(..., min_length=1)
    field_patterns: list[str] = []
    redaction_mode: str = "mask"
    applies_to: str = "all"  # all, export, report


class RedactionRuleResponse(BaseModel):
    id: str
    name: str
    field_patterns: list[str]
    redaction_mode: str
    applies_to: str


@router.post("/redaction/apply", response_model=RedactResponse)
async def apply_redaction(
    body: RedactRequest,
    current_user: Any = Depends(get_current_user),
    encryptor: PIIEncryptor = Depends(get_encryptor),
) -> RedactResponse:
    if body.custom_fields:
        encryptor_copy = PIIEncryptor(encryptor._key)
        encryptor_copy.PII_FIELDS = set(body.custom_fields) | encryptor.PII_FIELDS

    if body.mode == "mask":
        result = encryptor.redact_pii_in_dict(body.data)
    elif body.mode == "hash":
        result = {}
        for k, v in body.data.items():
            if isinstance(v, str) and k.lower() in encryptor.PII_FIELDS:
                result[k] = encryptor.hash_field(v)
            else:
                result[k] = v
    elif body.mode == "encrypt":
        result = encryptor.encrypt_pii_in_dict(body.data)
    else:  # remove
        result = {k: v for k, v in body.data.items() if k.lower() not in encryptor.PII_FIELDS}

    return RedactResponse(data=result, mode=body.mode, fields_processed=len(body.data))


@router.get("/redaction/rules")
async def list_redaction_rules(current_user: Any = Depends(get_current_user)) -> dict[str, Any]:
    return {"rules": [], "pii_fields": sorted(PIIEncryptor.PII_FIELDS)}


@router.post("/redaction/rules", status_code=201)
async def create_redaction_rule(
    body: RedactionRuleCreate,
    current_user: Any = Depends(get_current_user),
) -> dict[str, str]:
    import secrets

    return {"status": "created", "id": secrets.token_hex(16)}
