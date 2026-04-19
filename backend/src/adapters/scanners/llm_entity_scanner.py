"""LLM entity extractor scanner — extract OSINT entities from unstructured text using LLM or regex."""

import html
import json
import re
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urlparse

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.config import get_settings
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

_MAX_TEXT_CHARS = 4000

_PATTERNS: dict[str, re.Pattern[str]] = {
    "emails": re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"),
    "phone_numbers": re.compile(r"\+?[\d\s\-().]{7,15}\d"),
    "ip_addresses": re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
    "domains": re.compile(r"\b(?:[a-zA-Z0-9\-]+\.)+[a-zA-Z]{2,}\b"),
    "crypto_addresses": re.compile(r"0x[0-9a-fA-F]{40}|[13][a-km-zA-HJ-NP-Z1-9]{25,34}"),
    "urls": re.compile(r"https?://[^\s\"'<>]+"),
}

_LLM_PROMPT = (
    "Extract all OSINT entities from this text. Return JSON with keys: "
    "emails, phone_numbers, ip_addresses, domains, person_names, organizations, "
    "crypto_addresses, social_handles, urls, locations. Text:\n\n{text}"
)


class _HTMLStripper(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self._parts.append(data)

    def get_text(self) -> str:
        return " ".join(self._parts)


def _strip_html(raw: str) -> str:
    stripper = _HTMLStripper()
    stripper.feed(html.unescape(raw))
    return stripper.get_text()


class LLMEntityScanner(BaseOsintScanner):
    scanner_name = "llm_entity_extractor"
    supported_input_types = frozenset({ScanInputType.URL, ScanInputType.DOMAIN})
    cache_ttl = 86400

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        settings = get_settings()
        text = await self._fetch_text(input_value, input_type)
        if not text:
            return {
                "input": input_value,
                "found": False,
                "error": "Could not fetch or extract text",
                "extracted_identifiers": [],
            }

        text = text[:_MAX_TEXT_CHARS]

        entities: dict[str, list[str]] = {}
        model_used = ""
        extraction_method = "regex"

        if settings.anthropic_api_key:
            entities, model_used, extraction_method = await self._extract_anthropic(text, settings)
        elif settings.openai_api_key:
            entities, model_used, extraction_method = await self._extract_openai(text, settings)

        if extraction_method == "regex" or not entities:
            entities = self._regex_extract(text)
            extraction_method = "regex"
            model_used = "none"

        total_entities = sum(len(v) for v in entities.values())
        identifiers = self._build_identifiers(entities)

        return {
            "input": input_value,
            "entities_by_type": entities,
            "total_entities": total_entities,
            "model_used": model_used,
            "extraction_method": extraction_method,
            "extracted_identifiers": list(dict.fromkeys(identifiers)),
        }

    async def _fetch_text(self, input_value: str, input_type: ScanInputType) -> str:
        if input_type == ScanInputType.DOMAIN:
            url = f"https://{input_value.strip().lstrip('https://').lstrip('http://')}"
        else:
            url = input_value.strip()
        try:
            async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
                resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
                if resp.status_code == 200:
                    return _strip_html(resp.text)
        except Exception as exc:
            log.debug("LLM entity scanner fetch failed", url=input_value, error=str(exc))
        return ""

    async def _extract_anthropic(
        self, text: str, settings: Any
    ) -> tuple[dict[str, list[str]], str, str]:
        model = "claude-haiku-4-5-20251001"
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": settings.anthropic_api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json={
                        "model": model,
                        "max_tokens": 1024,
                        "messages": [
                            {"role": "user", "content": _LLM_PROMPT.format(text=text)}
                        ],
                    },
                )
                if resp.status_code == 200:
                    data = resp.json()
                    content = data.get("content", [{}])[0].get("text", "")
                    entities = self._parse_llm_json(content)
                    return entities, model, "llm"
        except Exception as exc:
            log.debug("Anthropic LLM extraction failed", error=str(exc))
        return {}, model, "regex"

    async def _extract_openai(
        self, text: str, settings: Any
    ) -> tuple[dict[str, list[str]], str, str]:
        model = "gpt-4o-mini"
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {settings.openai_api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model,
                        "max_tokens": 1024,
                        "messages": [
                            {"role": "user", "content": _LLM_PROMPT.format(text=text)}
                        ],
                    },
                )
                if resp.status_code == 200:
                    data = resp.json()
                    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                    entities = self._parse_llm_json(content)
                    return entities, model, "llm"
        except Exception as exc:
            log.debug("OpenAI LLM extraction failed", error=str(exc))
        return {}, model, "regex"

    def _parse_llm_json(self, raw: str) -> dict[str, list[str]]:
        # Strip markdown code fences if present
        cleaned = re.sub(r"```(?:json)?\s*", "", raw).strip().rstrip("`").strip()
        try:
            data = json.loads(cleaned)
            if isinstance(data, dict):
                return {k: [str(v) for v in vs] if isinstance(vs, list) else [] for k, vs in data.items()}
        except json.JSONDecodeError:
            pass
        return {}

    def _regex_extract(self, text: str) -> dict[str, list[str]]:
        return {
            entity_type: list(dict.fromkeys(pattern.findall(text)))
            for entity_type, pattern in _PATTERNS.items()
        }

    def _build_identifiers(self, entities: dict[str, list[str]]) -> list[str]:
        identifiers: list[str] = []
        for email in entities.get("emails", []):
            identifiers.append(f"email:{email}")
        for phone in entities.get("phone_numbers", []):
            identifiers.append(f"phone:{phone}")
        for ip in entities.get("ip_addresses", []):
            identifiers.append(f"ip:{ip}")
        for domain in entities.get("domains", []):
            identifiers.append(f"domain:{domain}")
        for name in entities.get("person_names", []):
            identifiers.append(f"person:{name}")
        for url in entities.get("urls", [])[:10]:
            identifiers.append(f"url:{url}")
        return identifiers
