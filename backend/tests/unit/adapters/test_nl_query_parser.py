"""Tests for the natural language query parser."""

import pytest

from src.adapters.ai.nl_query_parser import extract_entities_from_text, parse_nl_query


class TestNLQueryParser:
    def test_parse_email_query(self) -> None:
        """Should extract email and suggest breach scanners."""
        result = parse_nl_query("Check if john@example.com has been in any breach")
        assert len(result.seed_inputs) >= 1
        emails = [s for s in result.seed_inputs if s["input_type"] == "email"]
        assert any(e["value"] == "john@example.com" for e in emails)
        assert result.intent == "breach"

    def test_parse_domain_query(self) -> None:
        """Should extract domain and suggest infra scanners."""
        result = parse_nl_query(
            "Scan the infrastructure for example.com including DNS and subdomains"
        )
        domains = [s for s in result.seed_inputs if s["input_type"] == "domain"]
        assert any(d["value"] == "example.com" for d in domains)
        assert result.intent == "infrastructure"

    def test_parse_ip_query(self) -> None:
        """Should extract IP address."""
        result = parse_nl_query("What services are running on 192.168.1.1")
        ips = [s for s in result.seed_inputs if s["input_type"] == "ip_address"]
        assert any(ip["value"] == "192.168.1.1" for ip in ips)

    def test_parse_social_media_query(self) -> None:
        """Should detect social media intent."""
        result = parse_nl_query("Find all social media accounts for @johndoe")
        assert result.intent == "social"
        usernames = [s for s in result.seed_inputs if s["input_type"] == "username"]
        assert any(u["value"] == "johndoe" for u in usernames)

    def test_parse_company_query(self) -> None:
        """Should detect company/NIP intent."""
        result = parse_nl_query("Look up the company with NIP 1234567890")
        assert result.intent == "company"
        nips = [s for s in result.seed_inputs if s["input_type"] == "nip"]
        assert any(n["value"] == "1234567890" for n in nips)

    def test_parse_url_query(self) -> None:
        """Should extract URLs."""
        result = parse_nl_query(
            "Check https://suspicious-site.com/page for threats"
        )
        urls = [s for s in result.seed_inputs if s["input_type"] == "url"]
        assert len(urls) >= 1

    def test_parse_multi_entity_query(self) -> None:
        """Should extract multiple entities from one query."""
        result = parse_nl_query(
            "Investigate john@example.com and their domain example.com"
        )
        assert len(result.seed_inputs) >= 2

    def test_confidence_increases_with_entities(self) -> None:
        """More entities should increase confidence."""
        r1 = parse_nl_query("hello")
        r2 = parse_nl_query("check john@example.com for breach")
        assert r2.confidence > r1.confidence

    def test_deep_intent(self) -> None:
        """Deep/complete queries should match deep intent."""
        result = parse_nl_query(
            "Do a complete deep scan of everything for john@example.com"
        )
        assert result.intent == "deep"


class TestEntityExtraction:
    def test_extract_emails(self) -> None:
        """Should extract email addresses."""
        entities = extract_entities_from_text(
            "Contact us at info@company.com or sales@company.com"
        )
        emails = [e for e in entities if e["input_type"] == "email"]
        assert len(emails) == 2

    def test_extract_ips(self) -> None:
        """Should extract valid IPs."""
        entities = extract_entities_from_text(
            "The server at 10.0.0.1 responded with data from 192.168.1.100"
        )
        ips = [e for e in entities if e["input_type"] == "ip_address"]
        assert len(ips) == 2

    def test_extract_mixed(self) -> None:
        """Should extract mixed entity types."""
        text = "User @hacker from 1.2.3.4 registered hacker@evil.com on evil.com"
        entities = extract_entities_from_text(text)
        types = {e["input_type"] for e in entities}
        assert "username" in types
        assert "email" in types
        assert "ip_address" in types
