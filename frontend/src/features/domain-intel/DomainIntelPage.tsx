import { useState } from "react";
import {
  AlertTriangle, BarChart3, CheckCircle2, ChevronDown, ChevronUp,
  Clock, Copy, Download, Globe, Key, Link2, Loader2, Mail,
  Network, Search, Server, Settings2, Shield, Users, XCircle, Zap,
} from "lucide-react";
import { useHarvest } from "./hooks";
import {
  ALL_SOURCE_IDS, FREE_SOURCE_IDS, SOURCE_CATEGORIES,
  type AsnInfo, type HarvestResult, type ShodanHostInfo, type SourceResult,
} from "./types";

// ─── Helpers ──────────────────────────────────────────────────────────────────

function copy(text: string) {
  navigator.clipboard.writeText(text).catch(() => {});
}

function exportJson(data: HarvestResult) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  Object.assign(document.createElement("a"), {
    href: url, download: `domain-intel-${data.domain}-${Date.now()}.json`,
  }).click();
  URL.revokeObjectURL(url);
}

function exportCsv(data: HarvestResult) {
  const rows = [["Type", "Value"],
    ...data.emails.map((e) => ["email", e]),
    ...data.subdomains.map((s) => ["subdomain", s]),
    ...data.ips.map((ip) => ["ip", ip]),
    ...data.urls.map((u) => ["url", u]),
    ...data.employees.map((p) => ["employee", p]),
  ];
  const blob = new Blob([rows.map((r) => r.map((c) => `"${c}"`).join(",")).join("\n")], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  Object.assign(document.createElement("a"), {
    href: url, download: `domain-intel-${data.domain}-${Date.now()}.csv`,
  }).click();
  URL.revokeObjectURL(url);
}

// ─── Source selector ──────────────────────────────────────────────────────────

function SourceSelector({
  selected, onChange,
}: { selected: string[]; onChange: (s: string[]) => void }) {
  const toggle = (id: string) =>
    onChange(selected.includes(id) ? selected.filter((s) => s !== id) : [...selected, id]);

  const selectAll = () => onChange(ALL_SOURCE_IDS);
  const selectFree = () => onChange(FREE_SOURCE_IDS);
  const selectNone = () => onChange([]);

  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        <button onClick={selectFree} className="text-xs px-3 py-1.5 rounded-lg bg-blue-700/30 border border-blue-600/50 text-blue-300 hover:bg-blue-700/50 transition-colors">
          Free only ({FREE_SOURCE_IDS.length})
        </button>
        <button onClick={selectAll} className="text-xs px-3 py-1.5 rounded-lg bg-gray-700/50 border border-gray-600 text-gray-300 hover:bg-gray-700 transition-colors">
          All ({ALL_SOURCE_IDS.length})
        </button>
        <button onClick={selectNone} className="text-xs px-3 py-1.5 rounded-lg bg-gray-700/50 border border-gray-600 text-gray-300 hover:bg-gray-700 transition-colors">
          None
        </button>
        <span className="ml-auto text-xs text-gray-500 self-center">
          {selected.length} selected
        </span>
      </div>

      <div className="space-y-3">
        {SOURCE_CATEGORIES.map((cat) => (
          <div key={cat.label}>
            <div className={`text-xs font-semibold uppercase tracking-wider mb-1.5 ${cat.color}`}>
              {cat.label}
            </div>
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-1.5">
              {cat.sources.map((src) => {
                const on = selected.includes(src.id);
                return (
                  <label
                    key={src.id}
                    className={`flex items-start gap-2 p-2 rounded-lg border cursor-pointer transition-colors text-xs ${
                      on
                        ? "border-blue-500/50 bg-blue-900/20"
                        : "border-gray-700/40 bg-gray-800/20 hover:border-gray-600"
                    }`}
                  >
                    <input type="checkbox" checked={on} onChange={() => toggle(src.id)} className="mt-0.5 accent-blue-500 shrink-0" />
                    <div className="min-w-0">
                      <div className="font-medium text-gray-200 flex items-center gap-1">
                        {src.label}
                        {src.requiresKey && <Key className="w-2.5 h-2.5 text-yellow-500 shrink-0" />}
                      </div>
                      <div className="text-gray-500 text-[10px] truncate">{src.desc}</div>
                    </div>
                  </label>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Result list ──────────────────────────────────────────────────────────────

function ResultList({
  icon: Icon, label, items, color, renderItem,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  items: string[];
  color: string;
  renderItem?: (item: string) => React.ReactNode;
}) {
  const [expanded, setExpanded] = useState(false);
  const visible = expanded ? items : items.slice(0, 25);
  if (!items.length) return null;
  return (
    <div className="rounded-lg border border-gray-700/60 overflow-hidden">
      <div className="flex items-center gap-2 px-4 py-2.5 bg-gray-800/50">
        <Icon className={`w-4 h-4 ${color}`} />
        <span className="font-semibold text-sm text-gray-200">{label}</span>
        <span className={`ml-1 text-xs px-1.5 py-0.5 rounded-full bg-gray-700 ${color}`}>{items.length}</span>
        <button onClick={() => copy(items.join("\n"))} className="ml-auto text-gray-500 hover:text-gray-300 transition-colors" title="Copy all">
          <Copy className="w-3.5 h-3.5" />
        </button>
      </div>
      <div className="divide-y divide-gray-800/60 max-h-72 overflow-y-auto">
        {visible.map((item, i) => (
          <div key={i} className="px-4 py-1.5 text-xs font-mono text-gray-300 hover:bg-gray-800/30">
            {renderItem ? renderItem(item) : item}
          </div>
        ))}
      </div>
      {items.length > 25 && (
        <button onClick={() => setExpanded((e) => !e)}
          className="w-full py-2 text-xs text-gray-400 hover:text-gray-200 bg-gray-800/30 hover:bg-gray-800/50 transition-colors flex items-center justify-center gap-1">
          {expanded ? <><ChevronUp className="w-3 h-3" />Show less</> : <><ChevronDown className="w-3 h-3" />Show all {items.length}</>}
        </button>
      )}
    </div>
  );
}

// ─── Source table ─────────────────────────────────────────────────────────────

function SourceTable({ sources }: { sources: SourceResult[] }) {
  const ok = sources.filter((s) => s.status === "ok");
  const skipped = sources.filter((s) => s.status === "skipped");
  const errors = sources.filter((s) => s.status === "error");

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-3 text-xs text-gray-500 mb-1">
        <span className="text-green-400">{ok.length} ok</span>
        <span className="text-yellow-400">{skipped.length} skipped (no API key)</span>
        <span className="text-red-400">{errors.length} errors</span>
      </div>
      <div className="space-y-0.5 max-h-96 overflow-y-auto">
        {sources.map((sr) => {
          const found = sr.emails_found + sr.subdomains_found + sr.ips_found + sr.urls_found + sr.employees_found;
          return (
            <div key={sr.name} className="flex items-center gap-3 px-3 py-1.5 rounded bg-gray-800/40 text-xs">
              {sr.status === "ok" ? (
                <CheckCircle2 className="w-3 h-3 text-green-400 shrink-0" />
              ) : sr.status === "skipped" ? (
                <Key className="w-3 h-3 text-yellow-500 shrink-0" />
              ) : (
                <XCircle className="w-3 h-3 text-red-400 shrink-0" />
              )}
              <span className="font-medium text-gray-300 w-36 shrink-0">{sr.name}</span>
              <span className="flex-1 text-gray-500 truncate">
                {sr.status === "ok" && found > 0 && (
                  <span className="text-green-400 font-semibold">{found} items</span>
                )}
                {sr.status === "ok" && sr.emails_found > 0 && <span className="ml-2 text-cyan-400">{sr.emails_found}✉</span>}
                {sr.status === "ok" && sr.subdomains_found > 0 && <span className="ml-2 text-purple-400">{sr.subdomains_found}⌂</span>}
                {sr.status === "ok" && sr.ips_found > 0 && <span className="ml-2 text-yellow-400">{sr.ips_found}⊕</span>}
                {sr.status === "ok" && sr.urls_found > 0 && <span className="ml-2 text-blue-400">{sr.urls_found}⚓</span>}
                {sr.status === "skipped" && <span className="text-yellow-600">{sr.error}</span>}
                {sr.status === "error" && <span className="text-red-400">{sr.error}</span>}
              </span>
              <span className="text-gray-600">{sr.duration_ms}ms</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── ASN / Shodan panels ──────────────────────────────────────────────────────

function AsnPanel({ items }: { items: AsnInfo[] }) {
  if (!items.length) return null;
  return (
    <div className="rounded-lg border border-gray-700/60 overflow-hidden">
      <div className="flex items-center gap-2 px-4 py-2.5 bg-gray-800/50">
        <Network className="w-4 h-4 text-orange-400" />
        <span className="font-semibold text-sm text-gray-200">ASN Info</span>
        <span className="ml-1 text-xs px-1.5 py-0.5 rounded-full bg-gray-700 text-orange-400">{items.length}</span>
      </div>
      <div className="divide-y divide-gray-800/60">
        {items.map((a) => (
          <div key={a.ip} className="px-4 py-2 text-xs grid grid-cols-4 gap-2">
            <span className="font-mono text-yellow-400">{a.ip}</span>
            <span className="text-gray-400">{a.asn || "—"}</span>
            <span className="text-gray-300 truncate">{a.org || "—"}</span>
            <span className="text-gray-500">{a.city}, {a.country}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function ShodanPanel({ hosts }: { hosts: ShodanHostInfo[] }) {
  if (!hosts.length) return null;
  return (
    <div className="rounded-lg border border-orange-700/40 overflow-hidden">
      <div className="flex items-center gap-2 px-4 py-2.5 bg-orange-900/20">
        <Shield className="w-4 h-4 text-orange-400" />
        <span className="font-semibold text-sm text-gray-200">Shodan Host Enrichment</span>
        <span className="ml-1 text-xs px-1.5 py-0.5 rounded-full bg-orange-900/40 text-orange-400">{hosts.length}</span>
      </div>
      <div className="divide-y divide-gray-800/60">
        {hosts.map((h) => (
          <div key={h.ip} className="px-4 py-3 space-y-1 text-xs">
            <div className="flex items-center gap-3">
              <span className="font-mono text-yellow-400 font-semibold">{h.ip}</span>
              {h.org && <span className="text-gray-300">{h.org}</span>}
              {h.country && <span className="text-gray-500">{h.country}</span>}
              {h.os && <span className="bg-gray-700 px-1.5 py-0.5 rounded text-gray-300">{h.os}</span>}
            </div>
            {h.ports.length > 0 && (
              <div className="flex gap-1 flex-wrap">
                {h.ports.slice(0, 20).map((p) => (
                  <span key={p} className="bg-blue-900/30 border border-blue-700/50 px-1.5 py-0.5 rounded font-mono text-blue-300">{p}</span>
                ))}
              </div>
            )}
            {h.vulns.length > 0 && (
              <div className="flex gap-1 flex-wrap">
                {h.vulns.map((v) => (
                  <span key={v} className="bg-red-900/30 border border-red-700/50 px-1.5 py-0.5 rounded font-mono text-red-300">{v}</span>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Main page ────────────────────────────────────────────────────────────────

type Tab = "results" | "sources" | "enrichment";

export default function DomainIntelPage() {
  const [domain, setDomain] = useState("");
  const [selectedSources, setSelectedSources] = useState<string[]>(FREE_SOURCE_IDS);
  const [limit, setLimit] = useState(100);
  const [dnsBrute, setDnsBrute] = useState(false);
  const [shodanEnrich, setShodanEnrich] = useState(false);
  const [showSourceSelector, setShowSourceSelector] = useState(false);
  const [activeTab, setActiveTab] = useState<Tab>("results");
  const harvest = useHarvest();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!domain.trim()) return;
    harvest.mutate({ domain: domain.trim(), sources: selectedSources, limit, dns_brute: dnsBrute, shodan_enrich: shodanEnrich });
    setActiveTab("results");
  };

  const result = harvest.data;

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-5">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="p-2 bg-blue-500/10 rounded-lg">
          <Search className="w-6 h-6 text-blue-400" />
        </div>
        <div>
          <h1 className="text-xl font-bold text-gray-100">Domain Intel</h1>
          <p className="text-sm text-gray-400">
            {ALL_SOURCE_IDS.length} OSINT sources — emails, subdomains, IPs, URLs, employees, ASN, Shodan enrichment
          </p>
        </div>
      </div>

      {/* Form */}
      <form onSubmit={handleSubmit} className="space-y-3 bg-gray-800/30 rounded-xl p-4 border border-gray-700/50">
        <div className="flex gap-3">
          <div className="relative flex-1">
            <Globe className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input
              value={domain}
              onChange={(e) => setDomain(e.target.value)}
              placeholder="example.com"
              className="w-full bg-gray-900 border border-gray-600 rounded-lg pl-9 pr-4 py-2.5 text-sm text-gray-200 placeholder-gray-500 focus:border-blue-500 outline-none transition-colors"
              disabled={harvest.isPending}
            />
          </div>
          <button
            type="submit"
            disabled={!domain.trim() || harvest.isPending || !selectedSources.length}
            className="flex items-center gap-2 px-5 py-2.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-40 disabled:cursor-not-allowed text-white rounded-lg text-sm font-medium transition-colors"
          >
            {harvest.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Zap className="w-4 h-4" />}
            {harvest.isPending ? "Harvesting…" : "Harvest"}
          </button>
        </div>

        {/* Options row */}
        <div className="flex flex-wrap items-center gap-4 text-sm">
          <label className="flex items-center gap-2 cursor-pointer text-gray-300">
            <input type="checkbox" checked={dnsBrute} onChange={(e) => setDnsBrute(e.target.checked)} className="accent-blue-500" />
            DNS Brute-force
          </label>
          <label className="flex items-center gap-2 cursor-pointer text-gray-300">
            <input type="checkbox" checked={shodanEnrich} onChange={(e) => setShodanEnrich(e.target.checked)} className="accent-orange-500" />
            <Shield className="w-3.5 h-3.5 text-orange-400" />
            Shodan Enrichment
          </label>
          <label className="flex items-center gap-2 cursor-pointer text-gray-300">
            <span className="text-gray-500 text-xs">Limit</span>
            <input
              type="number" min={10} max={500} value={limit}
              onChange={(e) => setLimit(Number(e.target.value))}
              className="w-16 bg-gray-900 border border-gray-600 rounded px-2 py-1 text-xs text-gray-200 focus:border-blue-500 outline-none"
            />
          </label>
          <button
            type="button"
            onClick={() => setShowSourceSelector((s) => !s)}
            className="ml-auto flex items-center gap-1.5 text-xs text-gray-400 hover:text-gray-200 transition-colors"
          >
            <Settings2 className="w-3.5 h-3.5" />
            {selectedSources.length}/{ALL_SOURCE_IDS.length} sources
            {showSourceSelector ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
          </button>
        </div>

        {showSourceSelector && (
          <div className="border-t border-gray-700/60 pt-3">
            <SourceSelector selected={selectedSources} onChange={setSelectedSources} />
          </div>
        )}
      </form>

      {/* Error */}
      {harvest.isError && (
        <div className="flex items-center gap-2 p-3 bg-red-900/30 border border-red-700/50 rounded-lg text-red-300 text-sm">
          <AlertTriangle className="w-4 h-4 shrink-0" />
          {(harvest.error as Error)?.message}
        </div>
      )}

      {/* Loading */}
      {harvest.isPending && (
        <div className="flex items-center gap-3 p-4 bg-gray-800/50 rounded-lg border border-gray-700/50">
          <Loader2 className="w-5 h-5 animate-spin text-blue-400 shrink-0" />
          <div>
            <p className="text-sm font-medium text-gray-200">
              Querying {selectedSources.length} sources in parallel…
            </p>
            <p className="text-xs text-gray-500 mt-0.5">
              crt.sh · HackerTarget · OTX · URLScan · Wayback · Bing · GitHub · DuckDuckGo · and more
              {dnsBrute && " · DNS brute-force"}
              {shodanEnrich && " · Shodan enrichment"}
            </p>
          </div>
        </div>
      )}

      {/* Results */}
      {result && (
        <div className="space-y-4">
          {/* Summary bar */}
          <div className="flex items-center gap-3 p-3 bg-gray-800/50 rounded-lg border border-gray-700/60">
            <CheckCircle2 className="w-5 h-5 text-green-400 shrink-0" />
            <div className="flex-1 min-w-0">
              <span className="font-semibold text-gray-200">{result.domain}</span>
              <span className="ml-2 text-sm text-gray-400">
                {result.total_found} items · {(result.duration_ms / 1000).toFixed(1)}s
              </span>
            </div>
            <div className="flex gap-2">
              <button onClick={() => exportCsv(result)}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-gray-700 hover:bg-gray-600 rounded-lg transition-colors text-gray-200">
                <Download className="w-3.5 h-3.5" /> CSV
              </button>
              <button onClick={() => exportJson(result)}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-gray-700 hover:bg-gray-600 rounded-lg transition-colors text-gray-200">
                <Download className="w-3.5 h-3.5" /> JSON
              </button>
            </div>
          </div>

          {/* Stats */}
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-2">
            {[
              { icon: Mail, label: "Emails", val: result.emails.length, color: "text-cyan-400" },
              { icon: Network, label: "Subdomains", val: result.subdomains.length, color: "text-purple-400" },
              { icon: Server, label: "IPs", val: result.ips.length, color: "text-yellow-400" },
              { icon: Link2, label: "URLs", val: result.urls.length, color: "text-blue-400" },
              { icon: Users, label: "Employees", val: result.employees.length, color: "text-green-400" },
            ].map(({ icon: Icon, label, val, color }) => (
              <div key={label} className="bg-gray-800/50 rounded-lg p-3 flex items-center gap-2">
                <Icon className={`w-4 h-4 ${color} shrink-0`} />
                <div>
                  <p className="text-lg font-bold text-gray-100">{val}</p>
                  <p className="text-xs text-gray-500">{label}</p>
                </div>
              </div>
            ))}
          </div>

          {/* Tabs */}
          <div className="flex gap-1 bg-gray-800/50 rounded-lg p-1 w-fit">
            {(["results", "sources", "enrichment"] as Tab[]).map((t) => (
              <button key={t} onClick={() => setActiveTab(t)}
                className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors capitalize ${
                  activeTab === t ? "bg-gray-700 text-gray-100" : "text-gray-400 hover:text-gray-200"
                }`}>
                {t}
                {t === "sources" && (
                  <span className="ml-1.5 text-xs text-gray-500">({result.source_results.length})</span>
                )}
              </button>
            ))}
          </div>

          {/* Tab: Results */}
          {activeTab === "results" && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <ResultList icon={Mail} label="Email Addresses" items={result.emails} color="text-cyan-400" />
              <ResultList icon={Network} label="Subdomains" items={result.subdomains} color="text-purple-400" />
              <ResultList icon={Server} label="IP Addresses" items={result.ips} color="text-yellow-400" />
              <ResultList icon={Link2} label="URLs" items={result.urls} color="text-blue-400"
                renderItem={(url) => (
                  <a href={url} target="_blank" rel="noopener noreferrer" className="text-blue-400 hover:underline truncate block">{url}</a>
                )} />
              {result.employees.length > 0 && (
                <ResultList icon={Users} label="Employees / People" items={result.employees} color="text-green-400" />
              )}
              {result.dns_brute_found.length > 0 && (
                <ResultList icon={Zap} label="DNS Brute-force Found" items={result.dns_brute_found} color="text-pink-400" />
              )}
            </div>
          )}

          {/* Tab: Sources */}
          {activeTab === "sources" && (
            <div className="space-y-2">
              <div className="flex items-center gap-2 mb-2">
                <BarChart3 className="w-4 h-4 text-gray-400" />
                <span className="text-sm font-semibold text-gray-200">Source Breakdown</span>
              </div>
              <SourceTable sources={result.source_results} />
            </div>
          )}

          {/* Tab: Enrichment */}
          {activeTab === "enrichment" && (
            <div className="space-y-4">
              {!result.asn_info.length && !result.shodan_hosts.length && (
                <div className="p-4 bg-gray-800/30 rounded-lg border border-gray-700/40 text-sm text-gray-400">
                  <p className="font-medium text-gray-300 mb-1">No enrichment data</p>
                  <p>Enable <strong>ASN Lookup</strong> (source selector) and/or <strong>Shodan Enrichment</strong> (requires <code className="bg-gray-800 px-1 rounded">SHODAN_API_KEY</code>) before running the harvest.</p>
                </div>
              )}
              <AsnPanel items={result.asn_info} />
              <ShodanPanel hosts={result.shodan_hosts} />
            </div>
          )}
        </div>
      )}
    </div>
  );
}
