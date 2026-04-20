"""Language Stylometrics scanner — analyze writing style for authorship identification.

Module 29 in the SOCMINT domain. Applies statistical stylometric analysis to a user's
public posts to extract linguistic fingerprints: vocabulary richness, average sentence
length, function word frequency, punctuation patterns, and readability metrics.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

# Common English function words — high frequency signals author style
FUNCTION_WORDS = frozenset([
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "up", "about", "into", "through", "during",
    "i", "you", "he", "she", "it", "we", "they", "me", "him", "her", "us",
    "them", "my", "your", "his", "its", "our", "their", "this", "that",
    "these", "those", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "must", "can", "not", "no", "so", "if",
])


def _tokenize(text: str) -> list[str]:
    """Split text into lowercase word tokens."""
    return re.findall(r"\b[a-zA-Z']+\b", text.lower())


def _compute_stylometrics(texts: list[str]) -> dict[str, Any]:
    """Compute stylometric features from a list of text samples."""
    if not texts:
        return {}

    combined = " ".join(texts)
    sentences = re.split(r"[.!?]+", combined)
    sentences = [s.strip() for s in sentences if s.strip()]

    tokens = _tokenize(combined)
    if not tokens:
        return {"error": "Insufficient text data"}

    # Type-token ratio (vocabulary richness)
    unique_tokens = set(tokens)
    ttr = len(unique_tokens) / len(tokens)

    # Average word length
    avg_word_len = sum(len(t) for t in tokens) / len(tokens)

    # Average sentence length (in words)
    sentence_lengths = [len(_tokenize(s)) for s in sentences if _tokenize(s)]
    avg_sentence_len = sum(sentence_lengths) / len(sentence_lengths) if sentence_lengths else 0

    # Function word ratio
    fw_count = sum(1 for t in tokens if t in FUNCTION_WORDS)
    fw_ratio = fw_count / len(tokens)

    # Punctuation frequency per 100 chars
    punct_count = sum(1 for c in combined if c in ".,;:!?-—'\"")
    punct_rate = (punct_count / max(len(combined), 1)) * 100

    # Uppercase ratio (shouting / emphasis)
    upper_count = sum(1 for c in combined if c.isupper())
    upper_ratio = upper_count / max(len(combined), 1)

    # Most distinctive words (excluding function words)
    content_words = [t for t in tokens if t not in FUNCTION_WORDS and len(t) > 3]
    top_content_words = [w for w, _ in Counter(content_words).most_common(15)]

    # Flesch Reading Ease approximation
    syllable_count = sum(_estimate_syllables(t) for t in tokens)
    flesch = 206.835 - (1.015 * avg_sentence_len) - (84.6 * (syllable_count / max(len(tokens), 1)))
    flesch = max(0.0, min(100.0, flesch))

    return {
        "sample_size": len(texts),
        "total_tokens": len(tokens),
        "type_token_ratio": round(ttr, 4),
        "avg_word_length": round(avg_word_len, 2),
        "avg_sentence_length": round(avg_sentence_len, 2),
        "function_word_ratio": round(fw_ratio, 4),
        "punctuation_rate_per_100_chars": round(punct_rate, 2),
        "uppercase_ratio": round(upper_ratio, 4),
        "top_content_words": top_content_words,
        "flesch_reading_ease": round(flesch, 1),
        "readability_level": _flesch_level(flesch),
    }


def _estimate_syllables(word: str) -> int:
    """Rough syllable estimator using vowel group counting."""
    word = word.lower()
    syllables = len(re.findall(r"[aeiou]+", word))
    if word.endswith("e") and len(word) > 2:
        syllables = max(1, syllables - 1)
    return max(1, syllables)


def _flesch_level(score: float) -> str:
    if score >= 90:
        return "Very Easy"
    if score >= 70:
        return "Easy"
    if score >= 50:
        return "Medium"
    if score >= 30:
        return "Difficult"
    return "Very Difficult"


class LanguageStylemetricsScanner(BaseOsintScanner):
    """Analyze writing style fingerprints from a user's public social media posts.

    Fetches up to 100 Reddit comments (no API key required) and applies
    stylometric analysis to build a linguistic profile useful for authorship
    attribution across platforms.
    """

    scanner_name = "language_stylometrics"
    supported_input_types = frozenset({ScanInputType.USERNAME})
    cache_ttl = 7200

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        username = input_value.strip().lstrip("@")
        texts: list[str] = []

        async with httpx.AsyncClient(
            timeout=20,
            headers={"User-Agent": "OSINT-Platform/1.0 Stylometrics"},
        ) as client:
            try:
                resp = await client.get(
                    f"https://www.reddit.com/user/{username}/comments.json",
                    params={"limit": 100},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    for item in data.get("data", {}).get("children", []):
                        body = item.get("data", {}).get("body", "")
                        if body and body != "[deleted]" and body != "[removed]":
                            texts.append(body)
            except Exception as exc:
                log.debug("language_stylometrics: fetch failed", error=str(exc))

        if not texts:
            return {"found": False, "username": username, "reason": "No public text samples found"}

        metrics = _compute_stylometrics(texts)

        return {
            "found": True,
            "username": username,
            "data_source": "reddit_comments",
            **metrics,
        }
