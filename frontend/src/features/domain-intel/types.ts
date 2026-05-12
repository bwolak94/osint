export interface SourceResult {
  name: string;
  status: "ok" | "error" | "skipped";
  emails_found: number;
  subdomains_found: number;
  ips_found: number;
  urls_found: number;
  employees_found: number;
  error: string | null;
  duration_ms: number;
  requires_key: boolean;
}

export interface AsnInfo {
  ip: string;
  asn: string | null;
  org: string | null;
  country: string | null;
  city: string | null;
}

export interface ShodanHostInfo {
  ip: string;
  org: string | null;
  os: string | null;
  ports: number[];
  vulns: string[];
  hostnames: string[];
  country: string | null;
}

export interface HarvestResult {
  domain: string;
  scan_time: string;
  duration_ms: number;
  emails: string[];
  subdomains: string[];
  ips: string[];
  urls: string[];
  employees: string[];
  asn_info: AsnInfo[];
  shodan_hosts: ShodanHostInfo[];
  dns_brute_found: string[];
  source_results: SourceResult[];
  total_found: number;
}

export interface HarvestRequest {
  domain: string;
  sources: string[];
  limit: number;
  dns_brute: boolean;
  shodan_enrich: boolean;
}

export type SourceCategory = {
  label: string;
  color: string;
  sources: { id: string; label: string; desc: string; requiresKey?: boolean }[];
};

export const SOURCE_CATEGORIES: SourceCategory[] = [
  {
    label: "Certificate / DNS",
    color: "text-cyan-400",
    sources: [
      { id: "crt_sh", label: "crt.sh", desc: "Certificate transparency logs" },
      { id: "certspotter", label: "CertSpotter", desc: "SSL cert monitoring" },
      { id: "hackertarget", label: "HackerTarget", desc: "DNS host search" },
      { id: "dnsdumpster", label: "DNS Dumpster", desc: "DNS record lookup" },
      { id: "dns_resolve", label: "DNS Resolve", desc: "Live DNS resolution" },
      { id: "robtex", label: "Robtex", desc: "DNS/IP relations" },
      { id: "thc", label: "THC", desc: "Free subdomain service" },
    ],
  },
  {
    label: "Subdomain Databases",
    color: "text-purple-400",
    sources: [
      { id: "rapiddns", label: "RapidDNS", desc: "Subdomain enumeration" },
      { id: "subdomaincenter", label: "SubdomainCenter", desc: "Subdomain database" },
      { id: "subdomainfinderc99", label: "c99 Finder", desc: "Subdomain finder" },
      { id: "projectdiscovery", label: "ProjectDiscovery", desc: "Chaos subdomain dataset" },
      { id: "bufferoverun", label: "BufferOverRun", desc: "TLS cert IPv4 scan", requiresKey: true },
      { id: "bevigil", label: "BeVigil", desc: "Mobile app OSINT", requiresKey: true },
      { id: "fullhunt", label: "FullHunt", desc: "Attack surface mapping", requiresKey: true },
      { id: "whoisxml", label: "WhoisXML", desc: "WHOIS subdomain API", requiresKey: true },
    ],
  },
  {
    label: "Search Engines",
    color: "text-yellow-400",
    sources: [
      { id: "bing", label: "Bing", desc: "Email harvesting" },
      { id: "duckduckgo", label: "DuckDuckGo", desc: "Email/subdomain search" },
      { id: "yahoo", label: "Yahoo", desc: "Email search" },
      { id: "baidu", label: "Baidu", desc: "Chinese search engine" },
      { id: "brave", label: "Brave Search", desc: "Brave search API", requiresKey: true },
      { id: "mojeek", label: "Mojeek", desc: "Privacy search", requiresKey: true },
    ],
  },
  {
    label: "Threat Intelligence",
    color: "text-red-400",
    sources: [
      { id: "otx", label: "AlienVault OTX", desc: "Threat intel passive DNS" },
      { id: "threatcrowd", label: "ThreatCrowd", desc: "Threat intelligence" },
      { id: "hudsonrock", label: "HudsonRock", desc: "Infostealer breach data" },
      { id: "urlscan", label: "URLScan.io", desc: "Web page scan database" },
      { id: "leakix", label: "LeakIX", desc: "Leaked data search" },
      { id: "criminalip", label: "CriminalIP", desc: "CTI search engine", requiresKey: true },
      { id: "onyphe", label: "Onyphe", desc: "Cyber defense search", requiresKey: true },
    ],
  },
  {
    label: "Email / People",
    color: "text-green-400",
    sources: [
      { id: "github", label: "GitHub", desc: "Code search for email leaks" },
      { id: "gitlab", label: "GitLab", desc: "GitLab code search" },
      { id: "bitbucket", label: "Bitbucket", desc: "Bitbucket code search" },
      { id: "hunter", label: "Hunter.io", desc: "Email finding", requiresKey: true },
      { id: "tomba", label: "Tomba", desc: "Email finder", requiresKey: true },
      { id: "rocketreach", label: "RocketReach", desc: "Contact information", requiresKey: true },
      { id: "dehashed", label: "DeHashed", desc: "Breach database", requiresKey: true },
      { id: "haveibeenpwned", label: "HIBP", desc: "Breach check for domain", requiresKey: true },
    ],
  },
  {
    label: "Web Archive / History",
    color: "text-blue-400",
    sources: [
      { id: "wayback", label: "Wayback Machine", desc: "Historical URL index" },
      { id: "commoncrawl", label: "Common Crawl", desc: "Massive web crawl index" },
      { id: "builtwith", label: "BuiltWith", desc: "Technology detection", requiresKey: true },
    ],
  },
  {
    label: "Network / Shodan",
    color: "text-orange-400",
    sources: [
      { id: "asn_lookup", label: "ASN Lookup", desc: "IP → ASN / org info" },
      { id: "takeover_check", label: "Takeover Check", desc: "Subdomain takeover detection" },
      { id: "shodan", label: "Shodan", desc: "Hosts/ports for domain", requiresKey: true },
      { id: "securitytrails", label: "SecurityTrails", desc: "DNS history", requiresKey: true },
      { id: "censys", label: "Censys", desc: "TLS cert search", requiresKey: true },
      { id: "netlas", label: "Netlas", desc: "Internet-wide scan", requiresKey: true },
      { id: "fofa", label: "FOFA", desc: "FOFA search engine", requiresKey: true },
      { id: "zoomeye", label: "ZoomEye", desc: "Internet search engine", requiresKey: true },
      { id: "hunterhow", label: "Hunter How", desc: "Internet search", requiresKey: true },
      { id: "securityscorecard", label: "SecurityScorecard", desc: "Risk scoring", requiresKey: true },
      { id: "pentesttools", label: "PentestTools", desc: "Cloud pentest toolkit", requiresKey: true },
    ],
  },
];

export const ALL_SOURCE_IDS = SOURCE_CATEGORIES.flatMap((c) => c.sources.map((s) => s.id));
export const FREE_SOURCE_IDS = SOURCE_CATEGORIES.flatMap((c) =>
  c.sources.filter((s) => !s.requiresKey).map((s) => s.id)
);
