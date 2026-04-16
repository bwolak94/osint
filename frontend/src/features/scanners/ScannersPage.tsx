import {
  Mail, AtSign, Building2, FileSearch, Receipt, Globe, Shield,
  CheckCircle2, Clock, Database, Users, CreditCard, MapPin, Hash,
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
      <div className="grid gap-3 sm:grid-cols-3">
        {[
          { type: "Email", icon: Mail, scanners: ["holehe"], color: "var(--node-email)" },
          { type: "Username", icon: AtSign, scanners: ["maigret"], color: "var(--node-username)" },
          { type: "NIP", icon: Building2, scanners: ["vat_status", "playwright_krs", "playwright_ceidg"], color: "var(--node-company)" },
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
