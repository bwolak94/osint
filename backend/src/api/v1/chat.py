"""LLM chat assistant endpoints with streaming support."""

import json
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from src.api.v1.auth.dependencies import get_current_user
from src.adapters.ai.llm_adapter import LLMAdapter

log = structlog.get_logger()
router = APIRouter()

_llm: LLMAdapter | None = None


def get_llm() -> LLMAdapter:
    global _llm
    if _llm is None:
        _llm = LLMAdapter()
    return _llm


class ChatMessage(BaseModel):
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str = Field(..., min_length=1, max_length=10000)


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(..., min_length=1, max_length=50)
    investigation_context: str = ""
    stream: bool = False


class ChatResponse(BaseModel):
    content: str
    model: str


@router.post("/chat", response_model=None)
async def chat(
    body: ChatRequest,
    current_user: Any = Depends(get_current_user),
    llm: LLMAdapter = Depends(get_llm),
) -> ChatResponse | StreamingResponse:
    """Chat with the OSINT AI assistant. Supports streaming via stream=true."""
    messages = [{"role": m.role, "content": m.content} for m in body.messages]

    if body.stream:
        async def event_stream():
            async for chunk in llm.stream_chat(messages, context=body.investigation_context):
                yield f"data: {json.dumps({'content': chunk})}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    content = await llm.chat(messages, context=body.investigation_context)
    from src.config import get_settings
    settings = get_settings()
    model = settings.anthropic_model if settings.llm_provider == "anthropic" else settings.openai_model
    return ChatResponse(content=content, model=model)


@router.post("/chat/analyze")
async def analyze_findings(
    body: dict[str, Any],
    current_user: Any = Depends(get_current_user),
    llm: LLMAdapter = Depends(get_llm),
) -> dict[str, str]:
    """Ask the AI to analyze specific scan findings."""
    findings_text = json.dumps(body.get("findings", {}), indent=2)
    question = body.get("question", "Analyze these findings and identify key insights.")

    messages = [{"role": "user", "content": f"{question}\n\nFindings:\n{findings_text}"}]
    result = await llm.chat(messages)
    return {"analysis": result}
