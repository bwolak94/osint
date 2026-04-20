"""GraphQL schema for the OSINT platform."""
from typing import Any, Optional
from pydantic import BaseModel


class GraphQLQuery(BaseModel):
    query: str
    variables: dict[str, Any] | None = None
    operation_name: str | None = None


class GraphQLResponse(BaseModel):
    data: dict[str, Any] | None = None
    errors: list[dict[str, Any]] | None = None


# Simple query resolver that maps GraphQL queries to REST-like responses
SCHEMA_SDL = """
type Query {
    investigation(id: ID!): Investigation
    investigations(limit: Int = 20, offset: Int = 0, status: String): InvestigationConnection
    scanResult(id: ID!): ScanResult
    searchInvestigations(query: String!): [Investigation]
    me: User
}

type User {
    id: ID!
    email: String!
    role: String!
    subscription_tier: String!
}

type Investigation {
    id: ID!
    title: String!
    description: String
    status: String!
    seed_inputs: [SeedInput]
    tags: [String]
    created_at: String!
    updated_at: String!
    scan_results: [ScanResult]
    identities: [Identity]
}

type InvestigationConnection {
    items: [Investigation]
    total: Int!
    has_next: Boolean!
}

type SeedInput {
    value: String!
    input_type: String!
}

type ScanResult {
    id: ID!
    scanner_name: String!
    input_value: String!
    status: String!
    raw_data: JSON
    extracted_identifiers: [String]
    duration_ms: Int
    created_at: String!
}

type Identity {
    id: ID!
    display_name: String!
    emails: [String]
    phones: [String]
    usernames: [String]
    confidence_score: Float
    sources: [String]
}

scalar JSON
"""


def resolve_query(query_str: str, variables: dict | None = None) -> dict[str, Any]:
    """Simple query resolver - returns placeholder data based on query content."""
    query_lower = query_str.lower()

    if "me" in query_lower and "investigation" not in query_lower:
        return {"data": {"me": None}}

    if "investigations" in query_lower and "investigation(" not in query_lower:
        return {"data": {"investigations": {"items": [], "total": 0, "has_next": False}}}

    if "investigation" in query_lower:
        inv_id = (variables or {}).get("id", "unknown")
        return {"data": {"investigation": None}}

    if "searchinvestigations" in query_lower:
        return {"data": {"searchInvestigations": []}}

    return {"data": None, "errors": [{"message": "Unknown query"}]}
