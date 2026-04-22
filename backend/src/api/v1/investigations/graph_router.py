"""Graph endpoints scoped to an investigation.

Builds the knowledge graph dynamically from PostgreSQL scan results,
removing the hard dependency on Neo4j.
"""

from collections import deque
from typing import Annotated, Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.db.scan_result_repository import SqlAlchemyScanResultRepository
from src.api.v1.auth.dependencies import get_current_user
from src.api.v1.investigations.schemas import (
    AddEdgeRequest,
    AddNodeRequest,
    GraphEdgeSchema,
    GraphMetaSchema,
    GraphNodeSchema,
    GraphResponse,
    PathsResponse,
)
from src.core.domain.entities.scan_result import ScanResult
from src.core.domain.entities.user import User
from src.dependencies import get_db

router = APIRouter()


# ---------------------------------------------------------------------------
# Graph builder helpers
# ---------------------------------------------------------------------------

def _build_graph_from_scan_results(scan_results: list[ScanResult]) -> GraphResponse:
    """Construct a graph of nodes and edges from raw scan result data.

    Each scan result's *raw_data* is inspected for known fields and
    corresponding graph nodes / edges are emitted.  Supports all scanner
    types: NIP, holehe, maigret, shodan, dns, whois, subdomain, cert,
    virustotal, geoip, breach, github, reddit, telegram, tiktok, youtube,
    asn, wayback, phone, darkweb, google, linkedin, twitter, facebook,
    instagram, paste_sites, and generic social scanners.
    """
    nodes: dict[str, GraphNodeSchema] = {}
    edges: dict[str, GraphEdgeSchema] = {}

    def _add_node(
        node_id: str,
        node_type: str,
        label: str,
        properties: dict[str, Any] | None = None,
        confidence: float = 0.9,
        sources: list[str] | None = None,
    ) -> str:
        """Insert a node (de-duplicated by id) and return its id."""
        if node_id not in nodes:
            nodes[node_id] = GraphNodeSchema(
                id=node_id,
                type=node_type,
                label=label,
                properties=properties or {},
                confidence=confidence,
                sources=sources or [],
            )
        else:
            # Merge sources
            existing = nodes[node_id]
            for src in (sources or []):
                if src not in existing.sources:
                    existing.sources.append(src)
        return node_id

    def _add_edge(
        source: str,
        target: str,
        edge_type: str,
        label: str = "",
        confidence: float = 0.9,
    ) -> None:
        edge_id = f"{source}-{edge_type}-{target}"
        if edge_id not in edges:
            edges[edge_id] = GraphEdgeSchema(
                id=edge_id,
                source=source,
                target=target,
                type=edge_type,
                label=label,
                confidence=confidence,
            )

    def _ensure_root(
        raw: dict[str, Any],
        input_value: str,
        scanner: str,
    ) -> str:
        """Create the root/seed node and return its id."""
        root_id = f"input:{input_value}"
        nip = raw.get("nip")
        if nip:
            _add_node(root_id, "nip", f"NIP {nip}",
                      properties={"nip": nip}, sources=[scanner])
        else:
            _add_node(root_id, "input", input_value,
                      properties={"value": input_value}, sources=[scanner])
        return root_id

    # --- Per-scanner handlers -----------------------------------------------

    def _handle_nip(raw: dict[str, Any], input_value: str, scanner: str) -> None:
        """Handle NIP / KRS company-registry results."""
        root_id = _ensure_root(raw, input_value, scanner)

        name = raw.get("name")
        if name:
            entity_id = f"entity:{name}"
            entity_type = "company" if raw.get("nip") else "person"
            _add_node(entity_id, entity_type, name,
                      properties={"name": name, "status_vat": raw.get("status_vat", "")},
                      sources=[scanner])
            _add_edge(root_id, entity_id, "IDENTIFIES", "identifies")

        regon = raw.get("regon")
        if regon:
            regon_id = f"regon:{regon}"
            _add_node(regon_id, "regon", f"REGON {regon}",
                      properties={"regon": regon}, sources=[scanner])
            parent = f"entity:{name}" if name else root_id
            _add_edge(parent, regon_id, "HAS_REGON", "has REGON")

        for addr_key in ("working_address", "residence_address"):
            address = raw.get(addr_key)
            if address:
                addr_id = f"address:{address}"
                _add_node(addr_id, "address", address,
                          properties={"address": address, "address_type": addr_key},
                          sources=[scanner])
                parent = f"entity:{name}" if name else root_id
                edge_label = "registered at" if addr_key == "working_address" else "resides at"
                _add_edge(parent, addr_id, "HAS_ADDRESS", edge_label)

        bank_accounts = raw.get("bank_accounts")
        if bank_accounts and isinstance(bank_accounts, list):
            parent = f"entity:{name}" if name else root_id
            for account in bank_accounts:
                acc_id = f"bank:{account}"
                _add_node(acc_id, "bank_account", account,
                          properties={"account_number": account}, sources=[scanner])
                _add_edge(parent, acc_id, "HAS_BANK_ACCOUNT", "bank account")

        reg_date = raw.get("registration_date")
        if reg_date and name and f"entity:{name}" in nodes:
            nodes[f"entity:{name}"].properties["registration_date"] = reg_date

    def _handle_holehe(raw: dict[str, Any], input_value: str, scanner: str) -> None:
        """Handle holehe email-checker results."""
        root_id = _ensure_root(raw, input_value, scanner)
        registered_on = raw.get("registered_on")
        if not registered_on or not isinstance(registered_on, list):
            return

        email_id = f"email:{input_value}"
        _add_node(email_id, "email", input_value,
                  properties={"email": input_value}, sources=[scanner])
        if root_id != email_id:
            _add_edge(root_id, email_id, "IDENTIFIES", "identifies")

        for svc_name in registered_on:
            svc_id = f"service:{svc_name}"
            _add_node(svc_id, "online_service", svc_name,
                      properties={"service": svc_name}, sources=[scanner])
            _add_edge(email_id, svc_id, "REGISTERED_ON", "registered on")

        backup = raw.get("backup_email")
        if backup:
            backup_id = f"email:{backup}"
            _add_node(backup_id, "email", backup,
                      properties={"email": backup, "type": "backup"}, sources=[scanner])
            _add_edge(email_id, backup_id, "HAS_BACKUP", "backup email")

    def _handle_maigret(raw: dict[str, Any], input_value: str, scanner: str) -> None:
        """Handle maigret username-search results."""
        root_id = _ensure_root(raw, input_value, scanner)
        claimed_profiles = raw.get("claimed_profiles")
        if not claimed_profiles or not isinstance(claimed_profiles, list):
            return

        username_id = f"username:{input_value}"
        _add_node(username_id, "username", input_value,
                  properties={"username": input_value}, sources=[scanner])
        if root_id != username_id:
            _add_edge(root_id, username_id, "IDENTIFIES", "identifies")

        for profile in claimed_profiles[:30]:
            site = profile.get("site", "") or profile.get("site_name", "")
            url = profile.get("url", "") or profile.get("url_user", "")
            if site:
                svc_id = f"service:{site}"
                _add_node(svc_id, "online_service", site,
                          properties={"service": site, "url": url}, sources=[scanner])
                _add_edge(username_id, svc_id, "HAS_PROFILE", "has profile")

    def _handle_shodan(raw: dict[str, Any], input_value: str, scanner: str) -> None:
        """Handle Shodan scan results."""
        root_id = _ensure_root(raw, input_value, scanner)

        ip = raw.get("ip", input_value)
        ip_id = f"ip:{ip}"
        ip_props: dict[str, Any] = {"ip": ip}
        if raw.get("isp"):
            ip_props["isp"] = raw["isp"]
        if raw.get("country"):
            ip_props["country"] = raw["country"]
        if raw.get("org"):
            ip_props["org"] = raw["org"]
        if raw.get("os"):
            ip_props["os"] = raw["os"]
        _add_node(ip_id, "ip", ip, properties=ip_props, sources=[scanner])
        if root_id != ip_id:
            _add_edge(root_id, ip_id, "IDENTIFIES", "identifies")

        # Ports
        ports = raw.get("ports", [])
        if isinstance(ports, list):
            for port in ports:
                port_id = f"port:{ip}:{port}"
                _add_node(port_id, "port", str(port),
                          properties={"port": port, "ip": ip}, sources=[scanner])
                _add_edge(ip_id, port_id, "HAS_PORT", f"port {port}")

        # Services
        services = raw.get("services", [])
        if isinstance(services, list):
            for svc in services:
                svc_name = svc if isinstance(svc, str) else svc.get("product", svc.get("name", str(svc)))
                svc_port = svc.get("port", "") if isinstance(svc, dict) else ""
                svc_id = f"service:{ip}:{svc_name}:{svc_port}"
                svc_props: dict[str, Any] = {"name": svc_name}
                if isinstance(svc, dict):
                    svc_props.update({k: v for k, v in svc.items() if k in ("port", "transport", "version", "banner")})
                _add_node(svc_id, "service", str(svc_name), properties=svc_props, sources=[scanner])
                _add_edge(ip_id, svc_id, "RUNS_SERVICE", f"runs {svc_name}")

        # Vulnerabilities
        vulns = raw.get("vulns", [])
        if isinstance(vulns, list):
            for vuln in vulns:
                vuln_name = vuln if isinstance(vuln, str) else vuln.get("cve", str(vuln))
                vuln_id = f"vuln:{vuln_name}"
                vuln_props: dict[str, Any] = {"cve": vuln_name}
                if isinstance(vuln, dict):
                    vuln_props.update({k: v for k, v in vuln.items() if k in ("cvss", "summary", "references")})
                _add_node(vuln_id, "vulnerability", vuln_name, properties=vuln_props, sources=[scanner])
                _add_edge(ip_id, vuln_id, "HAS_VULNERABILITY", f"vuln {vuln_name}")

    def _handle_dns(raw: dict[str, Any], input_value: str, scanner: str) -> None:
        """Handle DNS scan results."""
        root_id = _ensure_root(raw, input_value, scanner)

        domain = raw.get("domain", input_value)
        domain_id = f"domain:{domain}"
        _add_node(domain_id, "domain", domain,
                  properties={"domain": domain}, sources=[scanner])
        if root_id != domain_id:
            _add_edge(root_id, domain_id, "IDENTIFIES", "identifies")

        records = raw.get("records", raw)
        if not isinstance(records, dict):
            return

        # A / AAAA records -> IP nodes
        for rtype in ("A", "AAAA", "a", "aaaa"):
            for addr in _ensure_list(records.get(rtype)):
                ip_id = f"ip:{addr}"
                _add_node(ip_id, "ip", addr, properties={"ip": addr}, sources=[scanner])
                _add_edge(domain_id, ip_id, "RESOLVES_TO", f"{rtype} record")

        # MX records
        for mx in _ensure_list(records.get("MX", records.get("mx"))):
            mx_val = mx if isinstance(mx, str) else mx.get("exchange", str(mx))
            mx_id = f"domain:{mx_val}"
            _add_node(mx_id, "domain", mx_val,
                      properties={"domain": mx_val, "record_type": "MX"}, sources=[scanner])
            _add_edge(domain_id, mx_id, "HAS_MX", f"MX {mx_val}")

        # NS records
        for ns in _ensure_list(records.get("NS", records.get("ns"))):
            ns_val = ns if isinstance(ns, str) else str(ns)
            ns_id = f"domain:{ns_val}"
            _add_node(ns_id, "domain", ns_val,
                      properties={"domain": ns_val, "record_type": "NS"}, sources=[scanner])
            _add_edge(domain_id, ns_id, "HAS_NS", f"NS {ns_val}")

        # CNAME records
        for cname in _ensure_list(records.get("CNAME", records.get("cname"))):
            cname_val = cname if isinstance(cname, str) else str(cname)
            cname_id = f"domain:{cname_val}"
            _add_node(cname_id, "domain", cname_val,
                      properties={"domain": cname_val, "record_type": "CNAME"}, sources=[scanner])
            _add_edge(domain_id, cname_id, "HAS_CNAME", f"CNAME {cname_val}")

        # TXT records (store as properties on domain node)
        txt_records = _ensure_list(records.get("TXT", records.get("txt")))
        if txt_records and domain_id in nodes:
            nodes[domain_id].properties["txt_records"] = txt_records

    def _handle_whois(raw: dict[str, Any], input_value: str, scanner: str) -> None:
        """Handle WHOIS scan results."""
        root_id = _ensure_root(raw, input_value, scanner)

        domain = raw.get("domain", raw.get("domain_name", input_value))
        if isinstance(domain, list):
            domain = domain[0] if domain else input_value
        domain_id = f"domain:{domain}"
        domain_props: dict[str, Any] = {"domain": domain}
        for key in ("creation_date", "expiration_date", "updated_date", "status"):
            val = raw.get(key)
            if val is not None:
                domain_props[key] = str(val) if not isinstance(val, str) else val
        _add_node(domain_id, "domain", str(domain), properties=domain_props, sources=[scanner])
        if root_id != domain_id:
            _add_edge(root_id, domain_id, "IDENTIFIES", "identifies")

        # Registrar
        registrar = raw.get("registrar")
        if registrar:
            reg_id = f"registrar:{registrar}"
            _add_node(reg_id, "registrar", registrar,
                      properties={"registrar": registrar}, sources=[scanner])
            _add_edge(domain_id, reg_id, "REGISTERED_WITH", f"registrar {registrar}")

        # Nameservers
        nameservers = _ensure_list(raw.get("name_servers", raw.get("nameservers")))
        for ns in nameservers:
            ns_val = ns if isinstance(ns, str) else str(ns)
            ns_id = f"nameserver:{ns_val}"
            _add_node(ns_id, "nameserver", ns_val,
                      properties={"nameserver": ns_val}, sources=[scanner])
            _add_edge(domain_id, ns_id, "USES_NAMESERVER", f"NS {ns_val}")

    def _handle_subdomain(raw: dict[str, Any], input_value: str, scanner: str) -> None:
        """Handle subdomain enumeration results."""
        root_id = _ensure_root(raw, input_value, scanner)

        parent_domain = raw.get("domain", input_value)
        parent_id = f"domain:{parent_domain}"
        _add_node(parent_id, "domain", parent_domain,
                  properties={"domain": parent_domain}, sources=[scanner])
        if root_id != parent_id:
            _add_edge(root_id, parent_id, "IDENTIFIES", "identifies")

        subdomains = _ensure_list(raw.get("subdomains", raw.get("results")))
        for sub in subdomains:
            sub_val = sub if isinstance(sub, str) else sub.get("subdomain", sub.get("host", str(sub)))
            sub_id = f"subdomain:{sub_val}"
            sub_props: dict[str, Any] = {"subdomain": sub_val}
            if isinstance(sub, dict):
                for key in ("ip", "status_code", "title"):
                    if sub.get(key):
                        sub_props[key] = sub[key]
            _add_node(sub_id, "subdomain", str(sub_val), properties=sub_props, sources=[scanner])
            _add_edge(parent_id, sub_id, "HAS_SUBDOMAIN", f"subdomain {sub_val}")

    def _handle_cert(raw: dict[str, Any], input_value: str, scanner: str) -> None:
        """Handle certificate transparency results."""
        root_id = _ensure_root(raw, input_value, scanner)

        domain = raw.get("domain", input_value)
        domain_id = f"domain:{domain}"
        _add_node(domain_id, "domain", domain,
                  properties={"domain": domain}, sources=[scanner])
        if root_id != domain_id:
            _add_edge(root_id, domain_id, "IDENTIFIES", "identifies")

        certs = _ensure_list(raw.get("certificates", raw.get("certs", raw.get("results"))))
        for cert in certs:
            if isinstance(cert, dict):
                cert_label = cert.get("subject", cert.get("common_name", cert.get("serial", str(uuid4())[:8])))
                cert_id = f"cert:{cert_label}"
                cert_props: dict[str, Any] = {}
                for key in ("issuer", "subject", "common_name", "serial", "not_before", "not_after", "fingerprint"):
                    if cert.get(key):
                        cert_props[key] = str(cert[key])
                _add_node(cert_id, "certificate", str(cert_label), properties=cert_props, sources=[scanner])
                _add_edge(domain_id, cert_id, "HAS_CERTIFICATE", f"cert {cert_label}")
            elif isinstance(cert, str):
                cert_id = f"cert:{cert}"
                _add_node(cert_id, "certificate", cert,
                          properties={"subject": cert}, sources=[scanner])
                _add_edge(domain_id, cert_id, "HAS_CERTIFICATE", f"cert {cert}")

    def _handle_virustotal(raw: dict[str, Any], input_value: str, scanner: str) -> None:
        """Handle VirusTotal scan results."""
        root_id = _ensure_root(raw, input_value, scanner)

        # Add threat score as property on root node
        threat_score = raw.get("threat_score", raw.get("positives", raw.get("malicious")))
        if threat_score is not None and root_id in nodes:
            nodes[root_id].properties["threat_score"] = threat_score

        total = raw.get("total", 0)
        if total and root_id in nodes:
            nodes[root_id].properties["vt_total_engines"] = total

        # Detection nodes for malicious findings
        detections = _ensure_list(raw.get("detections", raw.get("scans")))
        if isinstance(raw.get("scans"), dict):
            detections = [
                {"engine": k, **v} for k, v in raw["scans"].items()
                if isinstance(v, dict) and v.get("detected")
            ]
        for det in detections:
            if isinstance(det, dict):
                engine = det.get("engine", det.get("name", "unknown"))
                det_id = f"detection:{input_value}:{engine}"
                _add_node(det_id, "detection", f"{engine} detection",
                          properties={k: v for k, v in det.items() if isinstance(v, (str, int, float, bool))},
                          sources=[scanner])
                _add_edge(root_id, det_id, "DETECTED_BY", f"detected by {engine}")

    def _handle_geoip(raw: dict[str, Any], input_value: str, scanner: str) -> None:
        """Handle GeoIP lookup results."""
        root_id = _ensure_root(raw, input_value, scanner)

        ip = raw.get("ip", input_value)
        ip_id = f"ip:{ip}"
        _add_node(ip_id, "ip", ip, properties={"ip": ip}, sources=[scanner])
        if root_id != ip_id:
            _add_edge(root_id, ip_id, "IDENTIFIES", "identifies")

        city = raw.get("city", "")
        country = raw.get("country", raw.get("country_name", ""))
        location_label = ", ".join(filter(None, [city, country]))
        if location_label:
            loc_id = f"location:{location_label}"
            loc_props: dict[str, Any] = {}
            for key in ("city", "country", "country_name", "country_code", "region",
                        "latitude", "longitude", "lat", "lon", "timezone"):
                val = raw.get(key)
                if val is not None:
                    loc_props[key] = val
            _add_node(loc_id, "location", location_label, properties=loc_props, sources=[scanner])
            _add_edge(ip_id, loc_id, "LOCATED_IN", f"located in {location_label}")

    def _handle_breach(raw: dict[str, Any], input_value: str, scanner: str) -> None:
        """Handle breach/HIBP scan results."""
        root_id = _ensure_root(raw, input_value, scanner)

        email_id = f"email:{input_value}"
        _add_node(email_id, "email", input_value,
                  properties={"email": input_value}, sources=[scanner])
        if root_id != email_id:
            _add_edge(root_id, email_id, "IDENTIFIES", "identifies")

        breaches = _ensure_list(raw.get("breaches", raw.get("results")))
        for breach in breaches:
            if isinstance(breach, dict):
                breach_name = breach.get("Name", breach.get("name", breach.get("title", str(uuid4())[:8])))
                breach_id = f"breach:{breach_name}"
                breach_props: dict[str, Any] = {"name": breach_name}
                for key in ("Domain", "domain", "BreachDate", "breach_date", "PwnCount",
                            "pwn_count", "DataClasses", "data_classes", "Description", "description"):
                    val = breach.get(key)
                    if val is not None:
                        breach_props[key.lower()] = str(val) if not isinstance(val, (str, int, float)) else val
                _add_node(breach_id, "breach", breach_name, properties=breach_props, sources=[scanner])
                _add_edge(email_id, breach_id, "EXPOSED_IN", f"exposed in {breach_name}")
            elif isinstance(breach, str):
                breach_id = f"breach:{breach}"
                _add_node(breach_id, "breach", breach,
                          properties={"name": breach}, sources=[scanner])
                _add_edge(email_id, breach_id, "EXPOSED_IN", f"exposed in {breach}")

    def _handle_github(raw: dict[str, Any], input_value: str, scanner: str) -> None:
        """Handle GitHub profile results."""
        root_id = _ensure_root(raw, input_value, scanner)

        username_id = f"username:{input_value}"
        _add_node(username_id, "username", input_value,
                  properties={"username": input_value}, sources=[scanner])
        if root_id != username_id:
            _add_edge(root_id, username_id, "IDENTIFIES", "identifies")

        login = raw.get("login", raw.get("username", input_value))
        profile_id = f"github:{login}"
        profile_props: dict[str, Any] = {"platform": "github", "username": login}
        for key in ("name", "bio", "company", "location", "email", "blog",
                     "public_repos", "public_gists", "followers", "following",
                     "created_at", "html_url", "avatar_url"):
            val = raw.get(key)
            if val is not None:
                profile_props[key] = val
        _add_node(profile_id, "profile", f"GitHub: {login}", properties=profile_props, sources=[scanner])
        _add_edge(username_id, profile_id, "HAS_PROFILE", "GitHub profile")

    def _handle_social_profile(
        raw: dict[str, Any],
        input_value: str,
        scanner: str,
        platform: str,
    ) -> None:
        """Generic handler for social media profile scanners."""
        root_id = _ensure_root(raw, input_value, scanner)

        username_id = f"username:{input_value}"
        _add_node(username_id, "username", input_value,
                  properties={"username": input_value}, sources=[scanner])
        if root_id != username_id:
            _add_edge(root_id, username_id, "IDENTIFIES", "identifies")

        username = raw.get("username", raw.get("login", input_value))
        profile_id = f"{platform}:{username}"
        profile_props: dict[str, Any] = {"platform": platform, "username": username}
        # Gather all scalar properties from raw data
        for key, val in raw.items():
            if key.startswith("_") or key in ("found", "_stub"):
                continue
            if isinstance(val, (str, int, float, bool)):
                profile_props[key] = val
        _add_node(profile_id, "profile", f"{platform.title()}: {username}",
                  properties=profile_props, sources=[scanner])
        _add_edge(username_id, profile_id, "HAS_PROFILE", f"{platform} profile")

    def _handle_asn(raw: dict[str, Any], input_value: str, scanner: str) -> None:
        """Handle ASN lookup results."""
        root_id = _ensure_root(raw, input_value, scanner)

        ip = raw.get("ip", input_value)
        ip_id = f"ip:{ip}"
        _add_node(ip_id, "ip", ip, properties={"ip": ip}, sources=[scanner])
        if root_id != ip_id:
            _add_edge(root_id, ip_id, "IDENTIFIES", "identifies")

        asn = raw.get("asn", raw.get("asn_number"))
        if asn:
            asn_label = str(asn)
            asn_id = f"asn:{asn_label}"
            asn_props: dict[str, Any] = {"asn": asn_label}
            for key in ("asn_name", "name", "org", "organization", "country", "registry",
                        "cidr", "prefix", "description"):
                val = raw.get(key)
                if val is not None:
                    asn_props[key] = val
            _add_node(asn_id, "asn", f"AS{asn_label}",
                      properties=asn_props, sources=[scanner])
            _add_edge(ip_id, asn_id, "BELONGS_TO_ASN", f"AS{asn_label}")

    def _handle_wayback(raw: dict[str, Any], input_value: str, scanner: str) -> None:
        """Handle Wayback Machine results."""
        root_id = _ensure_root(raw, input_value, scanner)

        snapshot_count = raw.get("snapshot_count", raw.get("total", raw.get("count")))
        if snapshot_count is not None and root_id in nodes:
            nodes[root_id].properties["wayback_snapshots"] = snapshot_count

        first_seen = raw.get("first_seen", raw.get("oldest"))
        last_seen = raw.get("last_seen", raw.get("newest"))
        if first_seen and root_id in nodes:
            nodes[root_id].properties["wayback_first_seen"] = str(first_seen)
        if last_seen and root_id in nodes:
            nodes[root_id].properties["wayback_last_seen"] = str(last_seen)

    def _handle_phone(raw: dict[str, Any], input_value: str, scanner: str) -> None:
        """Handle phone number lookup results."""
        root_id = _ensure_root(raw, input_value, scanner)

        phone_id = f"phone:{input_value}"
        phone_props: dict[str, Any] = {"phone": input_value}
        for key in ("carrier", "location", "country", "country_code", "line_type",
                     "valid", "formatted", "international_format", "local_format"):
            val = raw.get(key)
            if val is not None:
                phone_props[key] = val
        _add_node(phone_id, "phone", input_value, properties=phone_props, sources=[scanner])
        if root_id != phone_id:
            _add_edge(root_id, phone_id, "IDENTIFIES", "identifies")

    def _handle_darkweb(raw: dict[str, Any], input_value: str, scanner: str) -> None:
        """Handle dark web mention results."""
        root_id = _ensure_root(raw, input_value, scanner)

        mentions = _ensure_list(raw.get("mentions", raw.get("results")))
        for mention in mentions:
            if isinstance(mention, dict):
                source_name = mention.get("source", mention.get("site", str(uuid4())[:8]))
                mention_id = f"darkweb:{source_name}:{input_value}"
                mention_props: dict[str, Any] = {"source": source_name}
                for key in ("title", "url", "date", "snippet", "content"):
                    val = mention.get(key)
                    if val is not None:
                        mention_props[key] = str(val)
                _add_node(mention_id, "dark_web_mention", f"DarkWeb: {source_name}",
                          properties=mention_props, sources=[scanner])
                _add_edge(root_id, mention_id, "MENTIONED_ON", f"mentioned on {source_name}")
            elif isinstance(mention, str):
                mention_id = f"darkweb:{mention}:{input_value}"
                _add_node(mention_id, "dark_web_mention", f"DarkWeb: {mention}",
                          properties={"source": mention}, sources=[scanner])
                _add_edge(root_id, mention_id, "MENTIONED_ON", f"mentioned on {mention}")

    def _handle_paste_sites(raw: dict[str, Any], input_value: str, scanner: str) -> None:
        """Handle paste site results."""
        root_id = _ensure_root(raw, input_value, scanner)

        pastes = _ensure_list(raw.get("pastes", raw.get("results")))
        for paste in pastes:
            if isinstance(paste, dict):
                paste_title = paste.get("title", paste.get("id", str(uuid4())[:8]))
                paste_id = f"paste:{paste_title}"
                paste_props: dict[str, Any] = {}
                for key in ("title", "id", "source", "url", "date", "size", "author"):
                    val = paste.get(key)
                    if val is not None:
                        paste_props[key] = str(val)
                _add_node(paste_id, "paste", f"Paste: {paste_title}",
                          properties=paste_props, sources=[scanner])
                _add_edge(root_id, paste_id, "FOUND_IN_PASTE", f"found in {paste_title}")
            elif isinstance(paste, str):
                paste_id = f"paste:{paste}"
                _add_node(paste_id, "paste", f"Paste: {paste}",
                          properties={"title": paste}, sources=[scanner])
                _add_edge(root_id, paste_id, "FOUND_IN_PASTE", f"found in {paste}")

    # --- Utility ------------------------------------------------------------

    def _ensure_list(val: Any) -> list[Any]:
        """Coerce a value to a list if it is not already one."""
        if val is None:
            return []
        if isinstance(val, list):
            return val
        return [val]

    # --- Scanner dispatch map -----------------------------------------------
    SOCIAL_SCANNERS = {
        "reddit", "telegram", "tiktok", "youtube", "twitter",
        "facebook", "instagram", "linkedin", "google",
    }

    # --- Main loop ----------------------------------------------------------
    for result in scan_results:
        raw = result.raw_data
        if not raw:
            continue
        if raw.get("_stub"):
            continue
        has_data = (
            raw.get("found")
            or raw.get("registered_count", 0) > 0
            or raw.get("claimed_count", 0) > 0
            # Allow scanners that don't use these conventions through
            or raw.get("ip")
            or raw.get("records")
            or raw.get("domain")
            or raw.get("domain_name")
            or raw.get("subdomains")
            or raw.get("results")
            or raw.get("certificates")
            or raw.get("certs")
            or raw.get("breaches")
            or raw.get("asn")
            or raw.get("asn_number")
            or raw.get("mentions")
            or raw.get("pastes")
            or raw.get("login")
            or raw.get("username")
            or raw.get("threat_score") is not None
            or raw.get("positives") is not None
            or raw.get("malicious") is not None
            or raw.get("carrier")
            or raw.get("snapshot_count") is not None
            or raw.get("total") is not None
            or raw.get("ports")
            or raw.get("services")
            or raw.get("vulns")
            or raw.get("scans")
            or raw.get("city")
            or raw.get("country")
            or raw.get("registrar")
            or raw.get("name_servers")
            or raw.get("nameservers")
            # Existing NIP checks
            or raw.get("nip")
            or raw.get("name")
            or raw.get("regon")
        )
        if not has_data:
            continue

        scanner = result.scanner_name
        input_value = result.input_value

        if scanner == "holehe":
            _handle_holehe(raw, input_value, scanner)
        elif scanner == "maigret":
            _handle_maigret(raw, input_value, scanner)
        elif scanner == "shodan":
            _handle_shodan(raw, input_value, scanner)
        elif scanner == "dns":
            _handle_dns(raw, input_value, scanner)
        elif scanner == "whois":
            _handle_whois(raw, input_value, scanner)
        elif scanner == "subdomain":
            _handle_subdomain(raw, input_value, scanner)
        elif scanner == "cert":
            _handle_cert(raw, input_value, scanner)
        elif scanner == "virustotal":
            _handle_virustotal(raw, input_value, scanner)
        elif scanner == "geoip":
            _handle_geoip(raw, input_value, scanner)
        elif scanner == "breach":
            _handle_breach(raw, input_value, scanner)
        elif scanner == "github":
            _handle_github(raw, input_value, scanner)
        elif scanner == "asn":
            _handle_asn(raw, input_value, scanner)
        elif scanner == "wayback":
            _handle_wayback(raw, input_value, scanner)
        elif scanner == "phone":
            _handle_phone(raw, input_value, scanner)
        elif scanner == "darkweb":
            _handle_darkweb(raw, input_value, scanner)
        elif scanner == "paste_sites":
            _handle_paste_sites(raw, input_value, scanner)
        elif scanner in SOCIAL_SCANNERS:
            _handle_social_profile(raw, input_value, scanner, scanner)
        else:
            # Fallback: handle NIP/company results and any unknown scanners
            _handle_nip(raw, input_value, scanner)

    node_list = list(nodes.values())
    n = len(node_list)
    max_edges = n * (n - 1) if n > 1 else 1
    density = len(edges) / max_edges if max_edges else 0.0

    return GraphResponse(
        nodes=node_list,
        edges=list(edges.values()),
        meta=GraphMetaSchema(
            node_count=len(node_list),
            edge_count=len(edges),
            density=round(density, 4),
        ),
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/{investigation_id}/graph", response_model=GraphResponse)
async def get_graph(
    investigation_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    depth: int = Query(default=3, ge=1, le=5),
) -> GraphResponse:
    """Return the full knowledge graph for an investigation.

    The graph is built dynamically from scan results stored in PostgreSQL,
    so Neo4j is not required.
    """
    scan_repo = SqlAlchemyScanResultRepository(db)
    results = await scan_repo.get_by_investigation(investigation_id)
    return _build_graph_from_scan_results(results)


@router.get("/{investigation_id}/graph/nodes", response_model=list[GraphNodeSchema])
async def get_graph_nodes(
    investigation_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    node_type: str | None = Query(default=None),
    limit: int = Query(default=100, le=1000),
) -> list[GraphNodeSchema]:
    """List graph nodes with optional type filter."""
    scan_repo = SqlAlchemyScanResultRepository(db)
    results = await scan_repo.get_by_investigation(investigation_id)
    graph = _build_graph_from_scan_results(results)
    filtered = graph.nodes
    if node_type:
        filtered = [n for n in filtered if n.type == node_type]
    return filtered[:limit]


@router.get("/{investigation_id}/graph/edges", response_model=list[GraphEdgeSchema])
async def get_graph_edges(
    investigation_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    edge_type: str | None = Query(default=None),
    limit: int = Query(default=100, le=1000),
) -> list[GraphEdgeSchema]:
    """List graph edges with optional type filter."""
    scan_repo = SqlAlchemyScanResultRepository(db)
    results = await scan_repo.get_by_investigation(investigation_id)
    graph = _build_graph_from_scan_results(results)
    edge_list = graph.edges
    if edge_type:
        edge_list = [e for e in edge_list if e.type == edge_type]
    return edge_list[:limit]


@router.post("/{investigation_id}/graph/nodes", response_model=GraphNodeSchema, status_code=status.HTTP_201_CREATED)
async def add_graph_node(
    investigation_id: UUID,
    body: AddNodeRequest,
    current_user: Annotated[User, Depends(get_current_user)],
) -> GraphNodeSchema:
    """Manually add a node to the investigation graph."""
    return GraphNodeSchema(
        id=str(uuid4()), type=body.type, label=body.label,
        properties=body.properties, confidence=1.0, sources=["manual"],
    )


@router.post("/{investigation_id}/graph/edges", response_model=GraphEdgeSchema, status_code=status.HTTP_201_CREATED)
async def add_graph_edge(
    investigation_id: UUID,
    body: AddEdgeRequest,
    current_user: Annotated[User, Depends(get_current_user)],
) -> GraphEdgeSchema:
    """Manually add an edge between two nodes."""
    return GraphEdgeSchema(
        id=str(uuid4()), source=body.source_node_id, target=body.target_node_id,
        type=body.type, label=body.label, confidence=1.0,
    )


@router.delete("/{investigation_id}/graph/nodes/{node_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_graph_node(
    investigation_id: UUID,
    node_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    """Remove a node and its edges from the graph."""
    pass


@router.get("/{investigation_id}/graph/paths", response_model=PathsResponse)
async def find_paths(
    investigation_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    from_node: str = Query(..., alias="from"),
    to_node: str = Query(..., alias="to"),
    max_depth: int = Query(default=5, ge=1, le=10),
) -> PathsResponse:
    """Find shortest paths between two nodes using BFS."""
    scan_repo = SqlAlchemyScanResultRepository(db)
    results = await scan_repo.get_by_investigation(investigation_id)
    graph = _build_graph_from_scan_results(results)

    # Build adjacency list (undirected)
    adj: dict[str, list[str]] = {}
    for edge in graph.edges:
        adj.setdefault(edge.source, []).append(edge.target)
        adj.setdefault(edge.target, []).append(edge.source)

    # Quick exit if either node is absent from the graph
    node_ids = {n.id for n in graph.nodes}
    if from_node not in node_ids or to_node not in node_ids:
        return PathsResponse(paths=[], path_count=0)

    # BFS to find shortest path(s)
    queue: deque[tuple[str, list[str]]] = deque([(from_node, [from_node])])
    visited: set[str] = {from_node}
    found_paths: list[list[GraphNodeSchema]] = []
    shortest_len: int | None = None

    while queue and len(found_paths) < 5:
        current, path = queue.popleft()

        if len(path) > max_depth + 1:
            break

        if current == to_node:
            path_nodes = [n for n in graph.nodes if n.id in path]
            # Preserve path ordering
            node_map = {n.id: n for n in path_nodes}
            ordered = [node_map[nid] for nid in path if nid in node_map]
            found_paths.append(ordered)
            if shortest_len is None:
                shortest_len = len(path)
            continue

        # Once we found a shortest path, don't explore longer ones
        if shortest_len is not None and len(path) >= shortest_len:
            continue

        for neighbor in adj.get(current, []):
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append((neighbor, path + [neighbor]))

    return PathsResponse(paths=found_paths, path_count=len(found_paths))


@router.post("/{investigation_id}/graph/nodes/{node_id}/expand", response_model=GraphResponse)
async def expand_node(
    investigation_id: UUID,
    node_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> GraphResponse:
    """Expand a node by returning its 1-hop neighborhood (Maltego-style transform)."""
    scan_repo = SqlAlchemyScanResultRepository(db)
    results = await scan_repo.get_by_investigation(investigation_id)
    graph = _build_graph_from_scan_results(results)

    # Verify the node exists
    target_node = next((n for n in graph.nodes if n.id == node_id), None)
    if not target_node:
        raise HTTPException(status_code=404, detail="Node not found")

    # Collect 1-hop neighborhood
    connected_edge_ids: set[str] = set()
    connected_node_ids: set[str] = {node_id}
    for edge in graph.edges:
        if edge.source == node_id or edge.target == node_id:
            connected_edge_ids.add(edge.id)
            connected_node_ids.add(edge.source)
            connected_node_ids.add(edge.target)

    sub_nodes = [n for n in graph.nodes if n.id in connected_node_ids]
    sub_edges = [e for e in graph.edges if e.id in connected_edge_ids]

    return GraphResponse(
        nodes=sub_nodes,
        edges=sub_edges,
        meta=GraphMetaSchema(
            node_count=len(sub_nodes),
            edge_count=len(sub_edges),
            density=0.0,
        ),
    )


@router.get("/{investigation_id}/graph/statistics")
async def get_graph_statistics(
    investigation_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get detailed graph statistics like Maltego's graph info."""
    scan_repo = SqlAlchemyScanResultRepository(db)
    results = await scan_repo.get_by_investigation(investigation_id)
    graph = _build_graph_from_scan_results(results)

    # Node type counts
    type_counts: dict[str, int] = {}
    for node in graph.nodes:
        type_counts[node.type] = type_counts.get(node.type, 0) + 1

    # Edge type counts
    edge_type_counts: dict[str, int] = {}
    for edge in graph.edges:
        edge_type_counts[edge.type] = edge_type_counts.get(edge.type, 0) + 1

    # Degree distribution
    degree: dict[str, int] = {}
    for edge in graph.edges:
        degree[edge.source] = degree.get(edge.source, 0) + 1
        degree[edge.target] = degree.get(edge.target, 0) + 1

    degrees = list(degree.values()) if degree else [0]

    # Top connected nodes
    top_nodes = sorted(degree.items(), key=lambda x: x[1], reverse=True)[:10]
    top_connected: list[dict[str, Any]] = []
    for nid, deg in top_nodes:
        node = next((n for n in graph.nodes if n.id == nid), None)
        if node:
            top_connected.append({
                "id": nid,
                "label": node.label,
                "type": node.type,
                "degree": deg,
            })

    return {
        "node_count": len(graph.nodes),
        "edge_count": len(graph.edges),
        "density": graph.meta.density,
        "node_types": type_counts,
        "edge_types": edge_type_counts,
        "avg_degree": sum(degrees) / len(degrees) if degrees else 0,
        "max_degree": max(degrees) if degrees else 0,
        "top_connected_nodes": top_connected,
        "scanners_contributing": list(set(s for n in graph.nodes for s in n.sources)),
    }
