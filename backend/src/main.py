"""FastAPI application entry point."""

import importlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from src.adapters.db.database import engine
from src.api.middleware.correlation import CorrelationIdMiddleware
from src.api.middleware.rate_limit import RateLimitMiddleware
from src.api.middleware.security import RequestLoggingMiddleware, SecurityHeadersMiddleware
from src.config import get_settings

log = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Router auto-discovery
# ---------------------------------------------------------------------------

_ROUTER_REGISTRY: list[tuple[str, str, str, list[str]]] = [
    # (module_path, attr_name, prefix, tags)

    # ── Infrastructure ────────────────────────────────────────────────────────
    ("src.api.v1.health", "router", "/health", ["health"]),
    ("src.api.v1.metrics", "router", "/metrics", ["metrics"]),

    # ── Auth & sessions ───────────────────────────────────────────────────────
    ("src.api.v1.auth.router", "router", "/api/v1/auth", ["auth"]),
    ("src.api.v1.investigations.router", "router", "/api/v1/investigations", ["investigations"]),
    ("src.api.v1.investigations.websocket", "router", "/api/v1/investigations", ["websocket"]),
    ("src.api.v1.investigations.graph_router", "router", "/api/v1/investigations", ["graph"]),
    ("src.api.v1.graph.router", "router", "/api/v1/graph", ["graph"]),
    ("src.api.v1.settings.router", "router", "/api/v1/settings", ["settings"]),
    ("src.api.v1.payments.router", "router", "/api/v1/payments", ["payments"]),
    ("src.api.v1.admin.router", "router", "/api/v1/admin", ["admin"]),
    ("src.api.v1.auth.totp", "router", "/api/v1/auth", ["2fa"]),
    ("src.api.v1.auth.webauthn", "router", "/api/v1/auth", ["webauthn"]),
    ("src.api.v1.auth.sessions", "router", "/api/v1/auth", ["sessions"]),
    ("src.api.v1.auth.tos", "router", "/api/v1/auth", ["auth-tos"]),
    ("src.api.v1.auth.sso", "router", "/api/v1", ["sso"]),

    # ── Investigations ────────────────────────────────────────────────────────
    ("src.api.v1.investigations.report", "router", "/api/v1/investigations", ["reports"]),
    ("src.api.v1.investigations.comments", "router", "/api/v1/investigations", ["comments"]),
    ("src.api.v1.investigations.fork", "router", "/api/v1/investigations", ["investigations"]),
    ("src.api.v1.investigations.summarize", "router", "/api/v1/investigations", ["ai"]),
    ("src.api.v1.settings.webhooks", "router", "/api/v1/settings", ["webhooks"]),
    # ── Core platform ─────────────────────────────────────────────────────────
    ("src.api.v1.search", "router", "/api/v1", ["search"]),
    ("src.api.v1.search_fulltext", "router", "/api/v1", ["search"]),
    ("src.api.v1.workspaces", "router", "/api/v1/workspaces", ["workspaces"]),
    ("src.api.v1.public_api", "router", "/api/v1/public", ["public-api"]),
    ("src.api.v1.playbooks", "router", "/api/v1/playbooks", ["playbooks"]),
    ("src.api.v1.playbook_conditions", "router", "/api/v1", ["playbooks"]),
    ("src.api.v1.maltego", "router", "/api/v1", ["maltego"]),
    ("src.api.v1.chat", "router", "/api/v1", ["ai"]),
    ("src.api.v1.nl_query", "router", "/api/v1", ["ai"]),
    ("src.api.v1.watchlist", "router", "/api/v1", ["watchlist"]),
    ("src.api.v1.webhook_triggers", "router", "/api/v1", ["webhooks"]),
    ("src.api.v1.presence", "router", "/api/v1", ["collaboration"]),
    ("src.api.v1.mentions", "router", "/api/v1", ["collaboration"]),
    ("src.api.v1.report_schedules", "router", "/api/v1", ["reports"]),
    ("src.api.v1.report_builder", "router", "/api/v1", ["reports"]),
    ("src.api.v1.task_board", "router", "/api/v1", ["tasks"]),
    ("src.api.v1.templates", "router", "/api/v1", ["templates"]),
    ("src.api.v1.integrations", "router", "/api/v1", ["integrations"]),
    ("src.api.v1.ticketing", "router", "/api/v1", ["ticketing"]),
    ("src.api.v1.graph_analytics", "router", "/api/v1", ["graph"]),
    ("src.api.v1.evidence.router", "router", "/api/v1", ["evidence"]),
    ("src.api.v1.investigation_diff", "router", "/api/v1", ["investigations"]),
    ("src.api.v1.saved_searches", "router", "/api/v1", ["saved-searches"]),
    ("src.api.v1.lineage", "router", "/api/v1", ["lineage"]),
    ("src.api.v1.versioning", "router", "/api/v1", ["versioning"]),
    ("src.api.v1.redaction", "router", "/api/v1", ["redaction"]),
    ("src.api.v1.report_narrative", "router", "/api/v1", ["reports"]),
    ("src.api.v1.email_ingestion", "router", "/api/v1", ["ingestion"]),
    ("src.api.v1.browser_extension", "router", "/api/v1", ["extension"]),
    ("src.api.graphql.router", "router", "/api", ["graphql"]),
    ("src.api.v1.api_versions", "router", "/api/v1", ["api-versions"]),
    ("src.api.v1.ml", "router", "/api/v1", ["ml"]),
    ("src.api.v1.bulk_actions", "router", "/api/v1", ["bulk"]),
    ("src.api.v1.campaigns", "router", "/api/v1/campaigns", ["campaigns"]),
    ("src.api.v1.annotations", "router", "/api/v1", ["annotations"]),
    ("src.api.v1.scan_profiles", "router", "/api/v1/scan-profiles", ["scan-profiles"]),
    ("src.api.v1.share_links", "router", "/api/v1", ["share-links"]),
    ("src.api.v1.activity_feed", "router", "/api/v1", ["activity"]),
    ("src.api.v1.sse", "router", "/api/v1", ["streaming"]),
    ("src.api.v1.investigation_merge", "router", "/api/v1/investigations", ["investigations"]),
    ("src.api.v1.ioc_feed", "router", "/api/v1", ["ioc-feed"]),
    ("src.api.v1.attack_surface", "router", "/api/v1", ["attack-surface"]),
    ("src.api.v1.forensic_timeline", "router", "/api/v1", ["forensic-timeline"]),
    ("src.api.v1.multi_investigation_graph", "router", "/api/v1", ["multi-graph"]),
    ("src.api.v1.tlp", "router", "/api/v1", ["tlp"]),
    ("src.api.v1.retention", "router", "/api/v1/retention", ["retention"]),
    ("src.api.v1.image_checker.router", "router", "/api/v1/image-checker", ["image-checker"]),
    ("src.api.v1.doc_metadata.router", "router", "/api/v1/doc-metadata", ["doc-metadata"]),
    ("src.api.v1.email_headers.router", "router", "/api/v1/email-headers", ["email-headers"]),
    ("src.api.v1.mac_lookup.router", "router", "/api/v1/mac-lookup", ["mac-lookup"]),
    ("src.api.v1.domain_permutation.router", "router", "/api/v1/domain-permutation", ["domain-permutation"]),
    ("src.api.v1.cloud_exposure.router", "router", "/api/v1/cloud-exposure", ["cloud-exposure"]),
    ("src.api.v1.stealer_logs.router", "router", "/api/v1/stealer-logs", ["stealer-logs"]),
    ("src.api.v1.supply_chain.router", "router", "/api/v1/supply-chain", ["supply-chain"]),
    ("src.api.v1.fediverse.router", "router", "/api/v1/fediverse", ["fediverse"]),
    ("src.api.v1.facebook_intel.router", "router", "/api/v1/facebook-intel", ["facebook-intel"]),
    ("src.api.v1.instagram_intel.router", "router", "/api/v1/instagram-intel", ["instagram-intel"]),
    ("src.api.v1.linkedin_intel.router", "router", "/api/v1/linkedin-intel", ["linkedin-intel"]),
    ("src.api.v1.github_intel.router", "router", "/api/v1/github-intel", ["github-intel"]),
    ("src.api.v1.vehicle_osint.router", "router", "/api/v1/vehicle-osint", ["vehicle-osint"]),
    ("src.api.v1.wigle.router", "router", "/api/v1/wigle", ["wigle"]),
    ("src.api.v1.tech_recon.router", "router", "/api/v1/tech-recon", ["tech-recon"]),
    ("src.api.v1.socmint.router", "router", "/api/v1/socmint", ["socmint"]),
    ("src.api.v1.credential_intel.router", "router", "/api/v1/credential-intel", ["credential-intel"]),
    ("src.api.v1.imint.router", "router", "/api/v1/imint", ["imint"]),
    # ── Pentesting platform ───────────────────────────────────────────────────
    ("src.api.v1.pentesting.router", "router", "/api/v1/pentesting", ["pentesting"]),
    ("src.api.v1.redteam.router", "router", "/api/v1/redteam", ["red-team"]),
    ("src.api.v1.engagements.router", "router", "/api/v1/engagements", ["pentest-engagements"]),
    ("src.api.v1.pentest_scans.router", "router", "/api/v1/scans", ["pentest-scans"]),
    ("src.api.v1.pentest_scans.llm_router", "router", "/api/v1/scans", ["pentest-llm"]),
    ("src.api.v1.pentest_scans.cvss_router", "router", "/api/v1", ["cvss"]),
    ("src.api.v1.pentest_findings.router", "router", "/api/v1/findings", ["pentest-findings"]),
    ("src.api.v1.pentest_findings.dedup_router", "router", "/api/v1", ["pentest-findings-dedup"]),
    ("src.api.v1.pentest_reports.router", "router", "/api/v1", ["pentest-reports"]),
    ("src.api.v1.pentest_audit.router", "router", "/api/v1/audit-log", ["pentest-audit"]),
    ("src.api.v1.hitl.router", "router", "/api/v1/hitl", ["pentest-hitl"]),
    ("src.api.v1.attack_chains.router", "router", "/api/v1/scans", ["pentest-attack-chains"]),
    ("src.api.v1.rag.router", "router", "/api/v1", ["rag"]),
    ("src.api.v1.ai_planner.router", "router", "/api/v1", ["ai-planner"]),
    ("src.api.v1.test_catalog.router", "router", "/api/v1", ["test-catalog"]),
    ("src.api.v1.bas.router", "router", "/api/v1/bas", ["bas"]),
    ("src.api.v1.sarif.router", "router", "/api/v1", ["pentest-export"]),
    ("src.api.v1.finding_library.router", "router", "/api/v1/finding-library", ["finding-library"]),
    ("src.api.v1.retest.router", "router", "/api/v1", ["retest"]),
    ("src.api.v1.notifications.router", "router", "/api/v1/notifications", ["notifications"]),
    ("src.api.v1.api_keys.router", "router", "/api/v1/api-keys", ["api-keys"]),
    ("src.api.v1.pentest_integrations.jira_router", "router", "/api/v1/integrations", ["integrations"]),
    ("src.api.v1.pentest_integrations.siem_router", "router", "/api/v1/integrations", ["integrations-siem"]),
    ("src.api.v1.team.router", "router", "/api/v1", ["team"]),
    ("src.api.v1.assets.router", "router", "/api/v1", ["assets"]),
    ("src.api.v1.phishing.router", "router", "/api/v1", ["phishing"]),
    ("src.api.v1.peer_review.router", "router", "/api/v1", ["peer-review"]),
    ("src.api.v1.agent.router", "router", "/api/v1", ["agent"]),
    ("src.api.v1.hub.router", "router", "/api/v1", ["hub"]),
    ("src.api.v1.hub_tasks.router", "router", "/api/v1", ["hub-tasks"]),
    ("src.api.v1.knowledge.router", "router", "/api/v1", ["knowledge"]),
    ("src.api.v1.threat_actors", "router", "/api/v1", ["threat-actors"]),
    # ── Web Attack Tools (Batch 1) ────────────────────────────────────────────
    ("src.api.v1.web_attack_tools.router", "router", "/api/v1/web-attack-tools", ["web-attack-tools"]),
    # ── Auth & Vuln Tools (Batch 2) ───────────────────────────────────────────
    ("src.api.v1.auth_vuln_tools.router", "router", "/api/v1/auth-vuln-tools", ["auth-vuln-tools"]),
    # ── AD & Infrastructure Tools (Batch 3) ──────────────────────────────────
    ("src.api.v1.ad_infra_tools.router", "router", "/api/v1/ad-infra-tools", ["ad-infra-tools"]),
    # ── Advanced Scanners (Batch 4 — Improvement 1) ───────────────────────────
    ("src.api.v1.advanced_scanners.router", "router", "", ["advanced-scanners"]),
    # ── AD Credential Attacks (Batch 4 — Improvement 4) ──────────────────────
    ("src.api.v1.ad_cred_attacks.router", "router", "", ["ad-cred-attacks"]),
    # ── Web Exploit Tools (New Batch Features 1–7) ────────────────────────────
    ("src.api.v1.web_exploit.router", "router", "", ["web-exploit"]),
    # ── Post-Exploit Tools (New Batch Features 8–10) ─────────────────────────
    ("src.api.v1.post_exploit.router", "router", "", ["post-exploit"]),
    # ── Exploit Tools (Features 11-14: OAuth, Atomic, XXE/SSRF, AdaptixC2) ──
    ("src.api.v1.exploit_tools.router", "router", "", ["exploit-tools"]),
    # ── AD Attack Tools (Features 15-19: LDAP, Ligolo, ACL, PtH, ADCS) ──────
    ("src.api.v1.ad_attack.router", "router", "", ["ad-attack"]),
    # ── Batch 3: Cloud Pentest (Features 21-25) ───────────────────────────────
    ("src.api.v1.cloud_pentest.router", "router", "", ["cloud-pentest"]),
    # ── Batch 3: Wireless Pentest (Features 26-28) ────────────────────────────
    ("src.api.v1.wireless_pentest.router", "router", "", ["wireless-pentest"]),
    # ── Batch 3: Reporting Tools (Features 29-30) ─────────────────────────────
    ("src.api.v1.reporting_tools.router", "router", "", ["reporting-tools"]),
    # ── OSINT scanners & analysis ─────────────────────────────────────────────
    ("src.api.v1.scanner_health", "router", "/api/v1", ["scanners"]),
    ("src.api.v1.dark_web", "router", "", ["dark-web"]),
    ("src.api.v1.passive_dns", "router", "", ["passive-dns"]),
    ("src.api.v1.footprint", "router", "", ["footprint"]),
    ("src.api.v1.cert_transparency", "router", "", ["cert-transparency"]),
    ("src.api.v1.crypto_trace", "router", "", ["crypto-trace"]),
    ("src.api.v1.corporate_intel", "router", "", ["corporate-intel"]),
    ("src.api.v1.deep_research", "router", "", ["deep-research"]),
    ("src.api.v1.phone_intel", "router", "", ["phone-intel"]),
    ("src.api.v1.social_graph", "router", "", ["social-graph"]),
    ("src.api.v1.brand_protection", "router", "", ["brand-protection"]),
    ("src.api.v1.correlation", "router", "", ["correlation"]),
    ("src.api.v1.evidence_locker", "router", "", ["evidence-locker"]),
    ("src.api.v1.vuln_management", "router", "", ["vuln-management"]),
    ("src.api.v1.phishing_campaigns", "router", "", ["phishing-campaigns"]),
    ("src.api.v1.exploit_chain", "router", "", ["exploit-chain"]),
    ("src.api.v1.c2_integration", "router", "", ["c2-integration"]),
    ("src.api.v1.network_topology", "router", "", ["network-topology"]),
    ("src.api.v1.wireless_auditor", "router", "", ["wireless-auditor"]),
    ("src.api.v1.domain_intel", "router", "", ["domain-intel"]),
    ("src.api.v1.methodology", "router", "", ["methodology"]),
    ("src.api.v1.collaboration", "router", "", ["collaboration"]),
    ("src.api.v1.retest_engine", "router", "", ["retest-engine"]),
    ("src.api.v1.client_portal", "router", "", ["client-portal"]),
    ("src.api.v1.secure_notes", "router", "", ["secure-notes"]),
    ("src.api.v1.time_tracking", "router", "", ["time-tracking"]),
    ("src.api.v1.sla", "router", "", ["sla"]),
    ("src.api.v1.ai_debrief", "router", "", ["ai-debrief"]),
    ("src.api.v1.threat_feed", "router", "", ["threat-feed"]),
    ("src.api.v1.canary", "router", "", ["canary"]),
    ("src.api.v1.custom_scanner", "router", "", ["custom-scanner"]),
    ("src.api.v1.knowledge_base", "router", "", ["knowledge-base"]),
    ("src.api.v1.client_handoff", "router", "", ["client-handoff"]),
    ("src.api.v1.scenarios.marketplace_router", "router", "/api/v1", ["scenario-marketplace"]),
    ("src.api.v1.workflows.n8n_router", "router", "/api/v1", ["n8n-workflows"]),
    ("src.api.v1.tools.custom_tools_router", "router", "/api/v1", ["custom-tools"]),
    ("src.api.v1.rbac.router", "router", "/api/v1", ["rbac"]),
    ("src.api.v1.gdpr.router", "router", "/api/v1", ["gdpr-compliance"]),
    # OSINT ↔ Pentest integration bridge
    ("src.api.v1.investigations.pentest_integration", "investigations_router", "/api/v1/investigations", ["osint-pentest-integration"]),
    ("src.api.v1.investigations.pentest_integration", "scans_router", "/api/v1/scans", ["osint-pentest-integration"]),
    # ── WorldMonitor ──────────────────────────────────────────────────────────
    ("src.api.v1.worldmonitor.router", "router", "/worldmonitor/api", ["world-monitor"]),

    # ── New features (batch 2) ────────────────────────────────────────────────
    ("src.api.v1.investigation_risk_score", "router", "/api/v1", ["risk-score"]),
    ("src.api.v1.stix_export", "router", "/api/v1", ["stix-export"]),
    ("src.api.v1.investigation_acl", "router", "/api/v1", ["investigation-acl"]),
    ("src.api.v1.scanner_quota", "router", "/api/v1", ["scanner-quota"]),
    ("src.api.v1.scheduled_rescan", "router", "/api/v1", ["scheduled-rescan"]),
    ("src.api.v1.pivot_recommendations", "router", "/api/v1", ["pivot-recommendations"]),
    ("src.api.v1.attack_flow", "router", "/api/v1", ["attack-flow"]),

    # ── New features (batch 4 — 30-feature expansion) ────────────────────────
    ("src.api.v1.iab_monitor", "router", "/api/v1", ["iab-monitor"]),
    ("src.api.v1.ransomware_attribution", "router", "/api/v1", ["ransomware-attribution"]),
    ("src.api.v1.credential_risk_scoring", "router", "/api/v1", ["credential-risk"]),
    ("src.api.v1.shadow_it", "router", "/api/v1", ["shadow-it"]),
    ("src.api.v1.nuclei_generator", "router", "/api/v1", ["nuclei-generator"]),
    ("src.api.v1.ad_attack_path", "router", "/api/v1", ["ad-attack-path"]),
    ("src.api.v1.cib_detector", "router", "/api/v1", ["cib-detector"]),
    ("src.api.v1.geolocation_triangulation", "router", "/api/v1", ["geolocation"]),

    # ── New OSINT tools (batch 3) ────────────────────────────────────────────
    ("src.api.v1.malware_hash.router", "router", "/api/v1/malware-hash", ["malware-hash"]),
    ("src.api.v1.asn_intel.router", "router", "/api/v1/asn-intel", ["asn-intel"]),
    ("src.api.v1.email_pivot.router", "router", "/api/v1/email-pivot", ["email-pivot"]),
    ("src.api.v1.http_fingerprint.router", "router", "/api/v1/http-fingerprint", ["http-fingerprint"]),
    ("src.api.v1.exploit_intel.router", "router", "/api/v1/exploit-intel", ["exploit-intel"]),
    ("src.api.v1.subdomain_takeover.router", "router", "/api/v1/subdomain-takeover", ["subdomain-takeover"]),
    ("src.api.v1.paste_monitor.router", "router", "/api/v1/paste-monitor", ["paste-monitor"]),
    ("src.api.v1.ransomware_tracker.router", "router", "/api/v1/ransomware-tracker", ["ransomware-tracker"]),
    ("src.api.v1.username_scanner.router", "router", "/api/v1/username-scanner", ["username-scanner"]),

    # ── Batch 25 — Platform infrastructure ───────────────────────────────────
    ("src.api.v1.risk_scoring", "router", "/api/v1", ["risk-scoring"]),
    ("src.api.v1.bulk_scan", "router", "/api/v1", ["bulk-scan"]),
    ("src.api.v1.report_generator", "router", "/api/v1", ["reports"]),
    ("src.api.v1.preservation", "router", "/api/v1", ["evidence"]),

    # ── Batch 26 — Core intelligence & analysis ───────────────────────────────
    ("src.api.v1.person_dossier", "router", "/api/v1", ["dossier"]),
    ("src.api.v1.confidence_scoring", "router", "/api/v1", ["confidence"]),
    ("src.api.v1.cross_investigation_dedup", "router", "/api/v1", ["dedup"]),
    ("src.api.v1.geo_clustering", "router", "/api/v1", ["geo"]),
    ("src.api.v1.behavioral_fingerprint", "router", "/api/v1", ["behavioral"]),

    # ── Batch 26 — Platform & UX features ────────────────────────────────────
    ("src.api.v1.investigation_templates", "router", "/api/v1", ["investigation-templates"]),
    ("src.api.v1.scanner_comparison", "router", "/api/v1", ["scanner-compare"]),
    ("src.api.v1.data_export", "router", "/api/v1", ["export"]),
    ("src.api.v1.ip_reputation", "router", "/api/v1", ["ip-reputation"]),
    ("src.api.v1.whois_pivot", "router", "/api/v1", ["whois-pivot"]),

    # ── Batch 26 — Security, Ops & Performance ────────────────────────────────
    ("src.api.v1.scanner_rate_monitor", "router", "/api/v1", ["scanner-monitoring"]),
    ("src.api.v1.finding_search", "router", "/api/v1", ["finding-search"]),
    ("src.api.v1.entity_resolution", "router", "/api/v1", ["entity-resolution"]),
    ("src.api.v1.scan_scheduler", "router", "/api/v1", ["scan-scheduler"]),
    ("src.api.v1.investigation_score", "router", "/api/v1", ["investigation-completeness"]),
    ("src.api.v1.relationship_strength", "router", "/api/v1", ["graph-relationships"]),

    # ── Batch 27 — Timeline & Attack Surface analysis ─────────────────────────
    ("src.api.v1.timeline_anomaly", "router", "/api/v1", ["timeline-anomaly"]),
    ("src.api.v1.attack_surface_score", "router", "/api/v1", ["attack-surface-score"]),

    # ── Batch 26 — Performance & Infrastructure (items 41-50) ─────────────────
    ("src.api.v1.scanner_telemetry", "router", "/api/v1", ["telemetry"]),
    ("src.api.v1.cache_ttl", "router", "/api/v1", ["cache-management"]),
    ("src.api.v1.compression_stats", "router", "/api/v1", ["storage"]),
    ("src.api.v1.registry_prewarm", "router", "/api/v1", ["registry"]),
    ("src.api.v1.queue_monitor", "router", "/api/v1", ["queue-monitor"]),
    ("src.api.v1.db_pool_monitor", "router", "/api/v1", ["db-monitoring"]),
    ("src.api.v1.scanner_benchmark", "router", "/api/v1", ["benchmark"]),
    ("src.api.v1.cache_stats", "router", "/api/v1", ["cache-stats"]),
    ("src.api.v1.health_dashboard", "router", "/api/v1", ["health-dashboard"]),
    ("src.api.v1.finding_dedup_cleaner", "router", "/api/v1", ["dedup-cleaner"]),
]


def _import_router_module(module_path: str, attr_name: str) -> tuple[str, str, Any, Exception | None]:
    """Import a single router module — safe to call from a worker thread."""
    try:
        module = importlib.import_module(module_path)
        router_obj = getattr(module, attr_name)
        return module_path, attr_name, router_obj, None
    except (ImportError, AttributeError) as exc:
        return module_path, attr_name, None, exc


def _include_all_routers(application: FastAPI) -> None:
    """Register all routers from the registry.

    In production (debug=False) any router that fails to import raises immediately
    so a misconfigured deployment is caught at startup rather than silently serving
    incomplete endpoints.  In debug mode, the error is logged and skipped so
    developers can work with partially-installed optional modules.

    Two-phase design (#29):
    - Phase 1: Import all modules in parallel via ThreadPoolExecutor (I/O-bound .pyc reads).
    - Phase 2: Mount routers in registry order (must be sequential for deterministic routing).

    Deduplication check: same module+attr mounted twice raises at startup. (#16)
    Prefix guard: routers with unversioned prefixes raise in production. (#8)
    """
    settings = get_settings()

    # Deduplication check (before parallel import — fast, no I/O)
    seen: set[tuple[str, str]] = set()
    for module_path, attr_name, _prefix, _tags in _ROUTER_REGISTRY:
        key = (module_path, attr_name)
        if key in seen:
            raise RuntimeError(
                f"Duplicate router registration detected: '{module_path}.{attr_name}'. "
                "Remove the duplicate entry from _ROUTER_REGISTRY."
            )
        seen.add(key)

    # Phase 1: parallel import (worker threads — Python import lock ensures safety)
    import_results: dict[tuple[str, str], tuple[Any, Exception | None]] = {}
    with ThreadPoolExecutor(max_workers=min(32, len(_ROUTER_REGISTRY))) as pool:
        futures = {
            pool.submit(_import_router_module, mp, an): (mp, an)
            for mp, an, _, _ in _ROUTER_REGISTRY
        }
        for future in as_completed(futures):
            mp, an, router_obj, exc = future.result()
            import_results[(mp, an)] = (router_obj, exc)

    # Phase 2: mount in registry order (sequential — preserves route priority)
    for module_path, attr_name, prefix, tags in _ROUTER_REGISTRY:
        router_obj, exc = import_results[(module_path, attr_name)]

        if exc is not None:
            if settings.debug:
                log.warning("router_load_failed", module=module_path, attr=attr_name, error=str(exc))
                continue
            raise RuntimeError(
                f"Failed to load router '{module_path}.{attr_name}': {exc}. "
                "Fix the import error or set DEBUG=true to skip missing routers."
            ) from exc

        # Empty-prefix guard using the imported router object's own prefix
        if prefix == "":
            router_own_prefix: str = getattr(router_obj, "prefix", "") or ""
            if not router_own_prefix.startswith("/api/v"):
                msg = (
                    f"Router '{module_path}' has no /api/vN prefix — routes may be unversioned. "
                    f"Set an explicit prefix in _ROUTER_REGISTRY or in the APIRouter() definition."
                )
                if not settings.debug:
                    raise RuntimeError(f"{msg} Set DEBUG=true to suppress this error.")
                log.warning("router_has_no_prefix", module=module_path, tags=tags)

        application.include_router(router_obj, prefix=prefix, tags=tags)


# ---------------------------------------------------------------------------
# Structured logging
# ---------------------------------------------------------------------------

def configure_logging() -> None:
    """Initialize structured logging with structlog.

    Uses ConsoleRenderer in debug mode for human-readable output, and
    JSONRenderer in production for structured log aggregation.
    """
    import os
    debug = os.getenv("DEBUG", "false").lower() in ("1", "true", "yes")

    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    renderer = (
        structlog.dev.ConsoleRenderer(colors=True)
        if debug
        else structlog.processors.JSONRenderer()
    )

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application startup and shutdown lifecycle."""
    import time
    startup_start = time.perf_counter()
    await log.ainfo("Starting OSINT platform backend")

    settings = get_settings()

    # Redis — fail gracefully: rate limiting and watchlist degrade without it. (#9)
    t0 = time.perf_counter()
    try:
        import redis.asyncio as aioredis
        app.state.redis = aioredis.from_url(settings.redis_url, decode_responses=True)
        await app.state.redis.ping()
        await log.ainfo("Redis connection established", elapsed_ms=int((time.perf_counter() - t0) * 1000))
    except Exception as exc:
        log.warning("redis_unavailable", error=str(exc), elapsed_ms=int((time.perf_counter() - t0) * 1000))
        app.state.redis = None

    # Elasticsearch — fail gracefully: full-text search degrades without it. (#9)
    t0 = time.perf_counter()
    try:
        from src.adapters.search.elasticsearch_store import ElasticsearchStore
        es = ElasticsearchStore()
        await es.ensure_indices()
        app.state.elasticsearch = es
        await log.ainfo("Elasticsearch indices ensured", elapsed_ms=int((time.perf_counter() - t0) * 1000))
    except Exception as exc:
        log.warning("elasticsearch_unavailable", error=str(exc), elapsed_ms=int((time.perf_counter() - t0) * 1000))
        app.state.elasticsearch = None

    from src.adapters.db.audit_models import AuditLogModel  # noqa: F401

    # MinIO — use shared adapter factory rather than inline construction. (#10)
    t0 = time.perf_counter()
    try:
        from src.adapters.storage.minio_client import build_minio_client, ensure_bucket
        _minio = build_minio_client(settings)
        await ensure_bucket(_minio, settings.minio_bucket)
        await log.ainfo("MinIO ready", bucket=settings.minio_bucket, elapsed_ms=int((time.perf_counter() - t0) * 1000))
    except Exception as exc:
        log.warning("minio_unavailable", error=str(exc), elapsed_ms=int((time.perf_counter() - t0) * 1000))

    # WorldMonitor background scheduler (RSS aggregation every 5 min). (#9)
    # Use specific ImportError catch for missing module; let other errors propagate
    # to ERROR level so ops teams are alerted about partial initialisation.
    try:
        from src.worldmonitor.scheduler import scheduler as wm_scheduler
        if app.state.redis is not None:
            await wm_scheduler.start(app.state.redis)
            await log.ainfo("WorldMonitor scheduler started")
    except ImportError:
        log.warning("worldmonitor_scheduler_unavailable", reason="module not installed")
    except (RuntimeError, ValueError, OSError) as exc:
        log.error(
            "worldmonitor_scheduler_failed",
            error=str(exc),
            message="WorldMonitor scheduler raised after partial initialisation — feed aggregation is DOWN",
        )

    if not settings.debug and settings.proxy_mode == "direct":
        log.warning(
            "opsec_warning",
            message=(
                "proxy_mode is 'direct': all scanner traffic originates from this server's real IP. "
                "Set PROXY_MODE=tor or PROXY_MODE=socks5 in production to protect investigator identity."
            ),
        )

    # Pre-warm scanner registry and log construction time (#87)
    t0 = time.perf_counter()
    try:
        from src.adapters.scanners.registry import get_default_registry
        registry = get_default_registry()
        registry_ms = int((time.perf_counter() - t0) * 1000)
        await log.ainfo(
            "scanner_registry_ready",
            scanner_count=len(registry.all_scanners),
            elapsed_ms=registry_ms,
        )
    except Exception as exc:
        log.error("scanner_registry_failed", error=str(exc))

    total_startup_ms = int((time.perf_counter() - startup_start) * 1000)
    await log.ainfo("OSINT platform backend started", total_startup_ms=total_startup_ms)  # (#23)

    yield

    await log.ainfo("Shutting down OSINT platform backend")
    try:
        from src.worldmonitor.scheduler import scheduler as wm_scheduler
        await wm_scheduler.stop()
    except ImportError:
        pass
    except Exception as exc:
        log.error("worldmonitor_scheduler_stop_failed", error=str(exc))
    if getattr(app.state, "elasticsearch", None) is not None:
        await app.state.elasticsearch.close()
    if getattr(app.state, "redis", None) is not None:
        await app.state.redis.close()
    # Release the shared scanner HTTP client connection pool (#18)
    try:
        from src.adapters.scanners.http_client import close_scanner_client
        await close_scanner_client()
    except Exception:
        pass
    await engine.dispose()
    await log.ainfo("Database pool disposed")


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    configure_logging()
    settings = get_settings()

    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.debug,
        lifespan=lifespan,
    )

    from src.adapters.telemetry import setup_telemetry
    setup_telemetry(application)

    # Middleware (outermost first)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=settings.cors_allow_methods,
        allow_headers=settings.cors_allow_headers,
    )
    application.add_middleware(CorrelationIdMiddleware)
    application.add_middleware(RateLimitMiddleware)
    application.add_middleware(SecurityHeadersMiddleware)
    application.add_middleware(RequestLoggingMiddleware)

    try:
        from src.api.middleware.locale import LocaleMiddleware
        application.add_middleware(LocaleMiddleware)
    except ImportError:
        pass

    # Global exception handlers
    @application.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.detail,
                "code": f"HTTP_{exc.status_code}",
                "details": None,
            },
        )

    @application.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        def _sanitize(obj: object) -> object:
            if isinstance(obj, bytes):
                return obj.decode("utf-8", errors="replace")
            if isinstance(obj, dict):
                return {k: _sanitize(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [_sanitize(i) for i in obj]
            return obj

        return JSONResponse(
            status_code=422,
            content={
                "error": "Validation error",
                "code": "VALIDATION_ERROR",
                "details": _sanitize(exc.errors()),
            },
        )

    _include_all_routers(application)

    return application


app = create_app()
