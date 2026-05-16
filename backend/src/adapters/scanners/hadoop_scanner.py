"""Hadoop / HDFS / YARN — unauthenticated access and data exposure scanner.

Detects exposed Apache Hadoop clusters:
- HDFS NameNode WebUI (ports 50070/9870) — file system browsing, arbitrary read
- YARN ResourceManager API (ports 8088/8090) — job submission, RCE via application master
- MapReduce JobHistory Server (port 19888)
- Hive (port 10000/10002), HBase Master (port 16010), Spark (port 4040/8080/18080)
- CVE-2021-25642 YARN RCE via malicious application submission
"""

from __future__ import annotations

import asyncio
import re
from typing import Any
from urllib.parse import urlparse

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

# HDFS NameNode paths
_HDFS_PATHS: list[tuple[str, str]] = [
    ("/jmx?qry=Hadoop:service=NameNode,name=NameNodeStatus", "namenode_status"),
    ("/jmx?qry=Hadoop:service=NameNode,name=FSNamesystem", "fs_namesystem"),
    ("/webhdfs/v1/?op=LISTSTATUS", "hdfs_root_listing"),
    ("/webhdfs/v1/user?op=LISTSTATUS", "hdfs_user_listing"),
    ("/webhdfs/v1/tmp?op=LISTSTATUS", "hdfs_tmp_listing"),
    ("/dfshealth.html", "dfshealth"),
    ("/explorer.html", "explorer"),
]

# YARN ResourceManager paths
_YARN_PATHS: list[tuple[str, str]] = [
    ("/ws/v1/cluster/info", "cluster_info"),
    ("/ws/v1/cluster/apps", "apps_list"),
    ("/ws/v1/cluster/nodes", "nodes_list"),
    ("/ws/v1/cluster/scheduler", "scheduler"),
    ("/cluster", "cluster_web"),
    ("/conf", "yarn_conf"),
]

# Other Hadoop ecosystem services
_SERVICE_PORTS: list[tuple[int, str, str]] = [
    (50070, "http", "hdfs_namenode_legacy"),
    (9870, "http", "hdfs_namenode_new"),
    (50470, "https", "hdfs_namenode_legacy_ssl"),
    (9871, "https", "hdfs_namenode_new_ssl"),
    (8088, "http", "yarn_rm"),
    (8090, "https", "yarn_rm_ssl"),
    (19888, "http", "mapreduce_history"),
    (10002, "http", "hive_web"),
    (16010, "http", "hbase_master"),
    (16030, "http", "hbase_regionserver"),
    (4040, "http", "spark_driver"),
    (18080, "http", "spark_history"),
    (8080, "http", "spark_master"),
]

_HDFS_INDICATORS = re.compile(
    r'(?i)(hadoop|namenode|datanode|HDFS|hdfsState|webhdfs|"BlocksTotal"|"FilesTotal")',
)
_YARN_INDICATORS = re.compile(
    r'(?i)(YARN|resourceManager|nodeManager|"clusterInfo"|"appsSubmitted"|"totalMB")',
)
_SENSITIVE_DIRS = re.compile(
    r'(?i)(password|secret|credential|key|token|\.aws|\.ssh|private)',
)


class HadoopScanner(BaseOsintScanner):
    """Apache Hadoop ecosystem exposure scanner.

    Probes HDFS NameNode, YARN ResourceManager, Spark, HBase, and Hive
    for unauthenticated access, file system browsing, and RCE via job submission.
    """

    scanner_name = "hadoop"
    supported_input_types = frozenset({ScanInputType.DOMAIN, ScanInputType.URL,
                                        ScanInputType.IP_ADDRESS})
    cache_ttl = 3600
    scan_timeout = 60

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        host = _extract_host(input_value, input_type)
        return await self._manual_scan(host, input_value)

    async def _manual_scan(self, host: str, input_value: str) -> dict[str, Any]:
        vulnerabilities: list[dict[str, Any]] = []
        identifiers: list[str] = []
        cluster_info: dict[str, Any] = {}

        async with httpx.AsyncClient(
            timeout=8,
            follow_redirects=True,
            verify=False,
            headers={"User-Agent": "Mozilla/5.0 (compatible; HadoopScanner/1.0)"},
        ) as client:
            semaphore = asyncio.Semaphore(8)

            # Probe HDFS NameNode
            async def probe_hdfs(port: int, scheme: str, path: str, technique: str) -> None:
                async with semaphore:
                    url = f"{scheme}://{host}:{port}{path}"
                    try:
                        resp = await client.get(url)
                        if resp.status_code != 200:
                            return
                        body = resp.text

                        if not (_HDFS_INDICATORS.search(body) or "webhdfs" in body.lower()):
                            return

                        if technique == "namenode_status":
                            import json as _json
                            try:
                                data = _json.loads(body)
                                beans = data.get("beans", [{}])
                                state = beans[0].get("State", "unknown") if beans else "unknown"
                                cluster_info["hdfs_state"] = state
                                cluster_info["hdfs_url"] = url
                                vulnerabilities.append({
                                    "type": "hadoop_hdfs_exposed",
                                    "severity": "critical",
                                    "url": url,
                                    "state": state,
                                    "description": f"HDFS NameNode JMX API accessible without auth on port {port}",
                                    "remediation": "Enable Hadoop Kerberos authentication; restrict NameNode ports to internal network",
                                })
                                identifiers.append("vuln:hadoop:hdfs_exposed")
                            except Exception:
                                pass

                        elif technique in ("hdfs_root_listing", "hdfs_user_listing", "hdfs_tmp_listing"):
                            import json as _json
                            try:
                                data = _json.loads(body)
                                statuses = data.get("FileStatuses", {}).get("FileStatus", [])
                                sensitive = [s["pathSuffix"] for s in statuses
                                             if _SENSITIVE_DIRS.search(s.get("pathSuffix", ""))]
                                vuln: dict[str, Any] = {
                                    "type": "hdfs_filesystem_exposed",
                                    "severity": "critical",
                                    "url": url,
                                    "file_count": len(statuses),
                                    "description": f"HDFS WebHDFS API allows unauthenticated file system browsing — {len(statuses)} entries visible",
                                    "remediation": "Enable WebHDFS auth; disable unauthenticated access",
                                }
                                if sensitive:
                                    vuln["sensitive_paths"] = sensitive[:5]
                                vulnerabilities.append(vuln)
                                ident = "vuln:hadoop:webhdfs_exposed"
                                if ident not in identifiers:
                                    identifiers.append(ident)
                            except Exception:
                                pass

                    except Exception:
                        pass

            # Probe YARN ResourceManager
            async def probe_yarn(port: int, scheme: str, path: str, technique: str) -> None:
                async with semaphore:
                    url = f"{scheme}://{host}:{port}{path}"
                    try:
                        resp = await client.get(url)
                        if resp.status_code != 200:
                            return
                        body = resp.text

                        if not _YARN_INDICATORS.search(body):
                            return

                        if technique == "cluster_info":
                            import json as _json
                            try:
                                data = _json.loads(body)
                                ci = data.get("clusterInfo", {})
                                cluster_info["yarn_state"] = ci.get("state", "unknown")
                                cluster_info["yarn_url"] = url
                                cluster_info["hadoop_version"] = ci.get("hadoopVersion")
                                vulnerabilities.append({
                                    "type": "yarn_rm_exposed",
                                    "severity": "critical",
                                    "url": url,
                                    "hadoop_version": ci.get("hadoopVersion"),
                                    "state": ci.get("state"),
                                    "cve": "CVE-2021-25642",
                                    "description": f"YARN ResourceManager REST API exposed without auth on port {port} — "
                                                   "malicious application submission → RCE possible",
                                    "remediation": "Enable YARN ACLs; block port 8088 from internet; "
                                                   "enable Kerberos authentication",
                                })
                                identifiers.append("vuln:hadoop:yarn_rce")
                            except Exception:
                                pass

                        elif technique == "apps_list":
                            import json as _json
                            try:
                                data = _json.loads(body)
                                apps = data.get("apps")
                                if apps:
                                    app_list = apps.get("app", [])
                                    vulnerabilities.append({
                                        "type": "yarn_apps_exposed",
                                        "severity": "high",
                                        "url": url,
                                        "app_count": len(app_list),
                                        "sample_apps": [a.get("name") for a in app_list[:5]],
                                        "description": "YARN application history accessible without auth — job names/configs exposed",
                                    })
                                    ident = "vuln:hadoop:yarn_apps"
                                    if ident not in identifiers:
                                        identifiers.append(ident)
                            except Exception:
                                pass

                    except Exception:
                        pass

            # Probe other services (Spark, HBase, Hive)
            async def probe_service(port: int, scheme: str, service: str) -> None:
                async with semaphore:
                    url = f"{scheme}://{host}:{port}/"
                    try:
                        resp = await client.get(url)
                        if resp.status_code not in (200, 302):
                            return
                        body = resp.text.lower()

                        service_map = {
                            "spark_driver": ("Spark", "spark_driver_ui"),
                            "spark_history": ("Spark", "spark_history_server"),
                            "spark_master": ("Spark Master", "spark_master_ui"),
                            "hbase_master": ("HBase", "hbase_master_ui"),
                            "hbase_regionserver": ("HBase", "hbase_region_ui"),
                            "hive_web": ("Hive", "hive_web_ui"),
                            "mapreduce_history": ("JobHistory", "mapreduce_history"),
                        }

                        if service in service_map:
                            indicator, vuln_type = service_map[service]
                            if indicator.lower() in body:
                                vulnerabilities.append({
                                    "type": vuln_type,
                                    "severity": "high",
                                    "url": url,
                                    "service": service,
                                    "description": f"{indicator} UI accessible without auth on port {port}",
                                    "remediation": f"Restrict {indicator} ports to internal network; enable auth",
                                })
                                ident = f"vuln:hadoop:{service}"
                                if ident not in identifiers:
                                    identifiers.append(ident)
                    except Exception:
                        pass

            hdfs_tasks = []
            for port, scheme, svc in _SERVICE_PORTS:
                if "hdfs" in svc:
                    for path, tech in _HDFS_PATHS[:5]:
                        hdfs_tasks.append(probe_hdfs(port, scheme, path, tech))
                elif "yarn" in svc:
                    for path, tech in _YARN_PATHS[:4]:
                        hdfs_tasks.append(probe_yarn(port, scheme, path, tech))
                else:
                    hdfs_tasks.append(probe_service(port, scheme, svc))

            await asyncio.gather(*hdfs_tasks)

        severity_counts: dict[str, int] = {}
        for v in vulnerabilities:
            s = v.get("severity", "info")
            severity_counts[s] = severity_counts.get(s, 0) + 1

        return {
            "input": input_value,
            "scan_mode": "manual_fallback",
            "host": host,
            "cluster_info": cluster_info,
            "vulnerabilities": vulnerabilities,
            "total_found": len(vulnerabilities),
            "severity_summary": severity_counts,
            "extracted_identifiers": identifiers,
        }

    def _extract_identifiers(self, raw_data: dict[str, Any]) -> list[str]:
        return raw_data.get("extracted_identifiers", [])


def _extract_host(value: str, input_type: ScanInputType) -> str:
    if input_type in (ScanInputType.IP_ADDRESS, ScanInputType.DOMAIN):
        return value.strip()
    parsed = urlparse(value if "://" in value else f"https://{value}")
    return parsed.hostname or value.strip()
