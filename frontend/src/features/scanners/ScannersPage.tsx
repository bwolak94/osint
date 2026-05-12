import {
  Mail, AtSign, Building2, FileSearch, Receipt, Globe, Shield,
  CheckCircle2, Clock, Users, MapPin, Search,
  Wifi, Phone, Lock, AlertTriangle, Chrome, Linkedin, Twitter, Facebook, Instagram,
} from "lucide-react";
import { Card, CardBody } from "@/shared/components/Card";
import { Badge } from "@/shared/components/Badge";

interface Scanner {
  id: string;
  name: string;
  description: string;
  longDescription: string;
  inputTypes: { type: string; label: string }[];
  dataFound: string[];
  source: string;
  icon: typeof Mail;
  color: string;
  requiresPro: boolean;
  speed: "fast" | "medium" | "slow";
}

const scanners: Scanner[] = [
  {
    id: "holehe",
    name: "Holehe",
    description: "Email registration checker across 120+ online services",
    longDescription:
      "Holehe checks if an email address is registered on popular online services by probing their password recovery endpoints. It does NOT send any alerts or notifications to the email owner. This is a passive reconnaissance technique.",
    inputTypes: [{ type: "email", label: "Email" }],
    dataFound: [
      "Registered services (Instagram, Twitter, Spotify, etc.)",
      "Partial phone number (if available from recovery)",
      "Backup email address (if available)",
      "Account existence confirmation",
    ],
    source: "Password recovery endpoints",
    icon: Mail,
    color: "var(--node-email)",
    requiresPro: false,
    speed: "fast",
  },
  {
    id: "maigret",
    name: "Maigret",
    description: "Username presence search across 3000+ websites",
    longDescription:
      "Maigret checks if a username exists on thousands of websites and social media platforms. It builds a profile of online presence by checking profile URLs. Results include direct links to found profiles.",
    inputTypes: [{ type: "username", label: "Username" }],
    dataFound: [
      "Social media profiles (with direct URLs)",
      "Forum accounts",
      "Developer platforms (GitHub, GitLab, etc.)",
      "Gaming profiles",
      "Dating site presence",
      "Claimed profile count across platforms",
    ],
    source: "Direct URL probing",
    icon: AtSign,
    color: "var(--node-username)",
    requiresPro: false,
    speed: "slow",
  },
  {
    id: "vat_status",
    name: "VAT Status (Biała Lista)",
    description: "Polish VAT registration status and bank account verification",
    longDescription:
      "Queries the official Polish Ministry of Finance API (Biała Lista / White List) to verify VAT registration status, retrieve registered bank accounts, and get basic company information. This is a public, free API with real-time data.",
    inputTypes: [{ type: "nip", label: "NIP" }],
    dataFound: [
      "Company legal name",
      "VAT registration status (Active/Inactive)",
      "REGON number",
      "KRS number (if applicable)",
      "Registered office address",
      "Working address",
      "All registered bank accounts",
      "Registration date",
    ],
    source: "wl-api.mf.gov.pl (Ministry of Finance)",
    icon: Receipt,
    color: "var(--warning-500)",
    requiresPro: false,
    speed: "fast",
  },
  {
    id: "playwright_krs",
    name: "KRS Registry",
    description: "Polish National Court Register — company registration data",
    longDescription:
      "Scrapes the official KRS (Krajowy Rejestr Sądowy) electronic portal to retrieve detailed company registration data including board members, shareholders, beneficial owners, and registration history. Uses a headless browser to navigate the portal.",
    inputTypes: [{ type: "nip", label: "NIP" }],
    dataFound: [
      "Full company name and legal form",
      "Board members (zarząd)",
      "Shareholders / partners",
      "Beneficial owners",
      "Share capital",
      "Registration history",
      "Business activity codes (PKD)",
      "Company status (active/liquidation/bankruptcy)",
    ],
    source: "ekrs.ms.gov.pl (Ministry of Justice)",
    icon: Building2,
    color: "var(--node-company)",
    requiresPro: true,
    speed: "slow",
  },
  {
    id: "playwright_ceidg",
    name: "CEIDG Registry",
    description: "Polish Central Register of Business Activity — sole proprietorship data",
    longDescription:
      "Searches the CEIDG (Centralna Ewidencja i Informacja o Działalności Gospodarczej) registry for sole proprietorship (JDG) data. Retrieves business owner details, registered address, business status, and activity codes.",
    inputTypes: [{ type: "nip", label: "NIP" }],
    dataFound: [
      "Business owner full name",
      "Business name (firma)",
      "Registered and business address",
      "Business status (active/suspended/closed)",
      "Registration and closure dates",
      "Business activity codes (PKD)",
      "REGON number",
    ],
    source: "aplikacja.ceidg.gov.pl",
    icon: FileSearch,
    color: "var(--node-company)",
    requiresPro: true,
    speed: "medium",
  },
  {
    id: "whois",
    name: "WHOIS Lookup",
    description: "Domain ownership, registrar, nameservers, and registration dates",
    longDescription:
      "Queries RDAP/WHOIS data for a domain to retrieve registrant information, registrar details, nameservers, domain status, and key dates (registration, expiration, last update). Uses the public RDAP protocol for structured responses.",
    inputTypes: [{ type: "domain", label: "Domain" }],
    dataFound: [
      "Domain registrar",
      "Nameservers",
      "Registration date",
      "Expiration date",
      "Domain status flags",
      "Last update timestamp",
    ],
    source: "rdap.org (RDAP protocol)",
    icon: Globe,
    color: "var(--node-domain)",
    requiresPro: false,
    speed: "fast",
  },
  {
    id: "dns_lookup",
    name: "DNS Records",
    description: "A, MX, NS, TXT records and IP resolution",
    longDescription:
      "Resolves DNS records for a domain using Google DNS-over-HTTPS. Returns A records (IP addresses), MX records (mail servers), NS records (nameservers), and TXT records (SPF, DKIM, verification entries). Extracted IPs and mail domains are added as identifiers for further investigation.",
    inputTypes: [{ type: "domain", label: "Domain" }],
    dataFound: [
      "A records (IPv4 addresses)",
      "MX records (mail servers with priority)",
      "NS records (authoritative nameservers)",
      "TXT records (SPF, DKIM, verification)",
      "Resolved IP addresses",
      "Mail server domains",
    ],
    source: "dns.google (DNS-over-HTTPS)",
    icon: Search,
    color: "var(--node-domain)",
    requiresPro: false,
    speed: "fast",
  },
  {
    id: "shodan",
    name: "Shodan",
    description: "Open ports, services, vulnerabilities, and host intelligence",
    longDescription:
      "Queries the Shodan search engine for Internet-connected devices. Returns open ports, running services with banners, known vulnerabilities (CVEs), hostnames, OS detection, ISP, and country. Supports both IP addresses and domains (resolved to IP). Falls back to the free InternetDB endpoint when no API key is configured.",
    inputTypes: [{ type: "ip_address", label: "IP Address" }, { type: "domain", label: "Domain" }],
    dataFound: [
      "Open ports and protocols",
      "Running services and banners",
      "Known vulnerabilities (CVEs)",
      "Hostnames and reverse DNS",
      "Operating system detection",
      "ISP and country information",
    ],
    source: "api.shodan.io / internetdb.shodan.io",
    icon: Wifi,
    color: "var(--danger-500)",
    requiresPro: false,
    speed: "fast",
  },
  {
    id: "geoip",
    name: "IP Geolocation",
    description: "Geographic location, ISP, and ASN data for IP addresses",
    longDescription:
      "Resolves an IP address to its geographic location using the free ip-api.com service. Returns country, city, latitude/longitude coordinates, ISP name, organization, ASN, and timezone. Useful for mapping infrastructure and identifying hosting providers.",
    inputTypes: [{ type: "ip_address", label: "IP Address" }],
    dataFound: [
      "Country and city",
      "Latitude and longitude coordinates",
      "ISP name",
      "Organization",
      "Autonomous System Number (ASN)",
      "Timezone",
    ],
    source: "ip-api.com",
    icon: MapPin,
    color: "var(--success-500)",
    requiresPro: false,
    speed: "fast",
  },
  {
    id: "cert_transparency",
    name: "Certificate Transparency",
    description: "Subdomain discovery via SSL/TLS certificate logs",
    longDescription:
      "Queries crt.sh Certificate Transparency logs to discover subdomains associated with a domain. Extracts unique subdomains from certificate common names and subject alternative names. Effective for mapping an organization's attack surface and finding hidden services.",
    inputTypes: [{ type: "domain", label: "Domain" }],
    dataFound: [
      "Subdomains from certificate common names",
      "Subdomains from subject alternative names",
      "Total certificate count",
      "Unique subdomain count",
    ],
    source: "crt.sh (Certificate Transparency)",
    icon: Lock,
    color: "var(--brand-500)",
    requiresPro: false,
    speed: "medium",
  },
  {
    id: "hibp",
    name: "Have I Been Pwned",
    description: "Data breach exposure check for email addresses",
    longDescription:
      "Checks if an email address has been involved in known data breaches using the Have I Been Pwned v3 API. Returns breach names, dates, exposed data types (passwords, emails, phone numbers, etc.), and verification status. Requires a paid HIBP API key.",
    inputTypes: [{ type: "email", label: "Email" }],
    dataFound: [
      "Breach names and titles",
      "Breach dates",
      "Exposed data types (passwords, emails, etc.)",
      "Number of accounts affected per breach",
      "Breach verification status",
      "Breach sensitivity flag",
    ],
    source: "haveibeenpwned.com (HIBP v3 API)",
    icon: AlertTriangle,
    color: "var(--warning-500)",
    requiresPro: true,
    speed: "fast",
  },
  {
    id: "phone_lookup",
    name: "Phone Lookup",
    description: "Phone number validation, carrier, and line type detection",
    longDescription:
      "Parses and validates phone numbers using the phonenumbers library (pure Python, no API key needed). Extracts country, carrier name, line type (mobile, landline, VoIP), timezone, and formats the number in E.164 and international formats. Works offline with no external API calls.",
    inputTypes: [{ type: "phone", label: "Phone" }],
    dataFound: [
      "Validation status (valid/invalid)",
      "Country and region",
      "Carrier name",
      "Line type (mobile, landline, VoIP)",
      "Timezone",
      "E.164 and international format",
    ],
    source: "phonenumbers library (offline)",
    icon: Phone,
    color: "var(--node-phone, var(--brand-400))",
    requiresPro: false,
    speed: "fast",
  },
  {
    id: "virustotal",
    name: "VirusTotal",
    description: "Threat intelligence for domains, IPs, and URLs via VirusTotal",
    longDescription:
      "Queries the VirusTotal API v3 for threat intelligence data. Returns malicious/suspicious detection counts from 70+ antivirus engines, reputation score, and content categories. Useful for identifying malicious infrastructure, phishing domains, and compromised hosts. Free tier allows 4 requests per minute.",
    inputTypes: [{ type: "domain", label: "Domain" }, { type: "ip_address", label: "IP Address" }, { type: "url", label: "URL" }],
    dataFound: [
      "Malicious detection count",
      "Suspicious detection count",
      "Harmless/undetected counts",
      "Reputation score",
      "Content categories",
      "Total engines scanned",
    ],
    source: "virustotal.com (API v3)",
    icon: Shield,
    color: "var(--danger-500)",
    requiresPro: false,
    speed: "fast",
  },
  {
    id: "google_account",
    name: "Google Account",
    description: "Google services discovery for email addresses (Calendar, Workspace, Gravatar)",
    longDescription:
      "Probes public Google endpoints to discover services linked to an email address. Checks for Gravatar profile photo, public Google Calendar, and Google Workspace usage via DMARC DNS records. For Gmail addresses, confirms the Gmail service association. No API key required.",
    inputTypes: [{ type: "email", label: "Email" }],
    dataFound: [
      "Gravatar profile photo",
      "Google Calendar (public)",
      "Google Workspace detection (via DMARC)",
      "Gmail account confirmation",
      "Registered service count",
    ],
    source: "Google public endpoints / Gravatar / DNS",
    icon: Chrome,
    color: "var(--node-email)",
    requiresPro: false,
    speed: "fast",
  },
  {
    id: "linkedin",
    name: "LinkedIn",
    description: "LinkedIn profile discovery via direct URL check and Google dork search",
    longDescription:
      "Searches for LinkedIn profiles matching a username or email address. Performs a direct profile URL check for usernames and uses Google search dorks to find LinkedIn profile pages. Returns profile URLs and basic metadata. Results may be limited by LinkedIn's anti-scraping protections.",
    inputTypes: [{ type: "username", label: "Username" }, { type: "email", label: "Email" }],
    dataFound: [
      "LinkedIn profile URL",
      "Profile existence confirmation",
      "Multiple profile matches (via Google dork)",
      "Profile count",
    ],
    source: "linkedin.com / Google Search",
    icon: Linkedin,
    color: "var(--brand-500)",
    requiresPro: false,
    speed: "medium",
  },
  {
    id: "twitter",
    name: "Twitter/X",
    description: "Twitter/X profile existence check and metadata extraction",
    longDescription:
      "Checks if a username has an active Twitter/X profile by probing the public profile URL. Extracts basic metadata from page meta tags including profile description and display name. Also attempts lookup via Nitter instances as a fallback for better data extraction.",
    inputTypes: [{ type: "username", label: "Username" }],
    dataFound: [
      "Profile existence confirmation",
      "Profile URL",
      "Profile description (from meta tags)",
      "Display name / title",
    ],
    source: "x.com / Nitter instances",
    icon: Twitter,
    color: "var(--brand-400)",
    requiresPro: false,
    speed: "fast",
  },
  {
    id: "facebook",
    name: "Facebook",
    description: "Facebook profile existence check via public profile URL",
    longDescription:
      "Checks if a username has a Facebook profile by probing the public profile URL. Facebook heavily restricts scraping, so results are limited to profile existence confirmation. Detects redirects to login pages as indicators of non-existent profiles.",
    inputTypes: [{ type: "username", label: "Username" }],
    dataFound: [
      "Profile existence confirmation",
      "Profile URL",
    ],
    source: "facebook.com",
    icon: Facebook,
    color: "var(--brand-500)",
    requiresPro: false,
    speed: "fast",
  },
  {
    id: "instagram",
    name: "Instagram",
    description: "Instagram profile data extraction — bio, followers, posts from public API",
    longDescription:
      "Queries the Instagram web API to extract public profile data for a username. Returns full name, biography, follower/following counts, post count, privacy status, and profile picture URL. Falls back to a simple URL existence check if the API is unavailable.",
    inputTypes: [{ type: "username", label: "Username" }],
    dataFound: [
      "Full name",
      "Biography / bio text",
      "Follower and following counts",
      "Post count",
      "Privacy status (public/private)",
      "Profile picture URL",
    ],
    source: "instagram.com (Web API)",
    icon: Instagram,
    color: "var(--warning-500)",
    requiresPro: false,
    speed: "fast",
  },
];

const speedConfig = {
  fast: { label: "Fast", color: "var(--success-500)", desc: "< 2 seconds" },
  medium: { label: "Medium", color: "var(--warning-500)", desc: "2–10 seconds" },
  slow: { label: "Slow", color: "var(--danger-500)", desc: "10–120 seconds" },
};

export function ScannersPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>
          Scanners
        </h1>
        <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
          Available OSINT scanners and what data they discover. Scanners are automatically selected based on your seed input types when creating an investigation.
        </p>
      </div>

      {/* Scanner type overview */}
      <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-7">
        {[
          { type: "Email", icon: Mail, scanners: ["holehe", "hibp", "google_account", "linkedin"], color: "var(--node-email)" },
          { type: "Username", icon: AtSign, scanners: ["maigret", "linkedin", "twitter", "facebook", "instagram"], color: "var(--node-username)" },
          { type: "NIP", icon: Building2, scanners: ["vat_status", "playwright_krs", "playwright_ceidg"], color: "var(--node-company)" },
          { type: "Domain", icon: Globe, scanners: ["whois", "dns_lookup", "shodan", "cert_transparency", "virustotal"], color: "var(--node-domain)" },
          { type: "IP Address", icon: Wifi, scanners: ["shodan", "geoip", "virustotal"], color: "var(--danger-500)" },
          { type: "Phone", icon: Phone, scanners: ["phone_lookup"], color: "var(--brand-400)" },
          { type: "Social Media", icon: Users, scanners: ["linkedin", "twitter", "facebook", "instagram"], color: "var(--brand-500)" },
        ].map((g) => (
          <Card key={g.type}>
            <CardBody className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg" style={{ background: `${g.color}15` }}>
                <g.icon className="h-5 w-5" style={{ color: g.color }} />
              </div>
              <div>
                <p className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
                  {g.type} Input
                </p>
                <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>
                  {g.scanners.length} scanner{g.scanners.length > 1 ? "s" : ""} available
                </p>
              </div>
            </CardBody>
          </Card>
        ))}
      </div>

      {/* Scanner cards */}
      <div className="space-y-4">
        {scanners.map((scanner) => {
          const speed = speedConfig[scanner.speed];
          return (
            <Card key={scanner.id}>
              <CardBody className="space-y-4">
                {/* Header */}
                <div className="flex items-start justify-between">
                  <div className="flex items-start gap-3">
                    <div
                      className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg"
                      style={{ background: `${scanner.color}15` }}
                    >
                      <scanner.icon className="h-5 w-5" style={{ color: scanner.color }} />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
                          {scanner.name}
                        </h3>
                        <Badge variant="neutral" size="sm">
                          <code className="text-[10px]">{scanner.id}</code>
                        </Badge>
                        {scanner.requiresPro && (
                          <Badge variant="brand" size="sm">PRO</Badge>
                        )}
                      </div>
                      <p className="mt-0.5 text-sm" style={{ color: "var(--text-secondary)" }}>
                        {scanner.description}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-1.5 shrink-0">
                    <div className="h-2 w-2 rounded-full" style={{ background: speed.color }} />
                    <span className="text-xs" style={{ color: "var(--text-tertiary)" }}>
                      {speed.label} ({speed.desc})
                    </span>
                  </div>
                </div>

                {/* Description */}
                <p className="text-xs leading-relaxed" style={{ color: "var(--text-tertiary)" }}>
                  {scanner.longDescription}
                </p>

                {/* Meta */}
                <div className="grid gap-4 sm:grid-cols-3">
                  {/* Input types */}
                  <div>
                    <p className="mb-1.5 text-xs font-medium uppercase tracking-wide" style={{ color: "var(--text-tertiary)" }}>
                      Accepts
                    </p>
                    <div className="flex flex-wrap gap-1">
                      {scanner.inputTypes.map((t) => (
                        <Badge key={t.type} variant="neutral" size="sm">{t.label}</Badge>
                      ))}
                    </div>
                  </div>

                  {/* Source */}
                  <div>
                    <p className="mb-1.5 text-xs font-medium uppercase tracking-wide" style={{ color: "var(--text-tertiary)" }}>
                      Data Source
                    </p>
                    <p className="text-xs font-mono" style={{ color: "var(--text-secondary)" }}>
                      {scanner.source}
                    </p>
                  </div>

                  {/* Speed */}
                  <div>
                    <p className="mb-1.5 text-xs font-medium uppercase tracking-wide" style={{ color: "var(--text-tertiary)" }}>
                      Speed
                    </p>
                    <div className="flex items-center gap-1.5">
                      <Clock className="h-3 w-3" style={{ color: speed.color }} />
                      <span className="text-xs" style={{ color: speed.color }}>{speed.label}</span>
                    </div>
                  </div>
                </div>

                {/* Data found */}
                <div>
                  <p className="mb-2 text-xs font-medium uppercase tracking-wide" style={{ color: "var(--text-tertiary)" }}>
                    Data Discovered
                  </p>
                  <div className="grid gap-1 sm:grid-cols-2">
                    {scanner.dataFound.map((item) => (
                      <div key={item} className="flex items-start gap-1.5">
                        <CheckCircle2 className="mt-0.5 h-3 w-3 shrink-0" style={{ color: "var(--brand-500)" }} />
                        <span className="text-xs" style={{ color: "var(--text-secondary)" }}>{item}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </CardBody>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
