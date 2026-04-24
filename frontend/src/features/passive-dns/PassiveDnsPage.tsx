import { useState } from "react";
import { Globe, Search, Clock, Database } from "lucide-react";
import { usePassiveDnsLookup } from "./hooks";
import { Button } from "@/shared/components/Button";
import { Input } from "@/shared/components/Input";
import { Card, CardBody, CardHeader } from "@/shared/components/Card";

const typeColors: Record<string, string> = {
  A: "var(--success-400)",
  AAAA: "var(--brand-400)",
  MX: "var(--warning-400)",
  NS: "var(--info-400)",
  CNAME: "var(--text-secondary)",
  TXT: "var(--text-tertiary)",
};

const RECORD_TYPES = ["ALL", "A", "AAAA", "MX", "NS", "CNAME", "TXT"] as const;

export function PassiveDnsPage() {
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("ALL");
  const lookup = usePassiveDnsLookup();

  const handleLookup = () => {
    if (query.trim())
      lookup.mutate({
        query: query.trim(),
        ...(filter !== "ALL" ? { recordType: filter } : {}),
      });
  };

  const filtered =
    lookup.data?.records.filter(
      (r) => filter === "ALL" || r.record_type === filter
    ) ?? [];

  const sortedFiltered = filtered
    .slice()
    .sort(
      (a, b) =>
        new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
    );

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3">
        <Database className="h-6 w-6" style={{ color: "var(--brand-500)" }} />
        <h1
          className="text-xl font-semibold"
          style={{ color: "var(--text-primary)" }}
        >
          Passive DNS Timeline
        </h1>
      </div>

      <Card>
        <CardBody>
          <div className="flex gap-3 flex-wrap">
            <div className="flex-1">
              <Input
                placeholder="Domain or IP address..."
                prefixIcon={<Globe className="h-4 w-4" />}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleLookup()}
              />
            </div>
            <select
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              className="rounded-md border px-3 py-2 text-sm"
              style={{
                background: "var(--bg-surface)",
                borderColor: "var(--border-default)",
                color: "var(--text-primary)",
              }}
            >
              {RECORD_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
            <Button
              onClick={handleLookup}
              disabled={!query.trim() || lookup.isPending}
              leftIcon={<Search className="h-4 w-4" />}
            >
              {lookup.isPending ? "Looking up..." : "Lookup"}
            </Button>
          </div>
        </CardBody>
      </Card>

      {lookup.data && (
        <div className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-3">
            {[
              { label: "Total Records", value: lookup.data.total_records },
              { label: "Unique IPs", value: lookup.data.unique_ips },
              { label: "Filtered", value: filtered.length },
            ].map(({ label, value }) => (
              <div
                key={label}
                className="rounded-xl border p-4 text-center"
                style={{
                  background: "var(--bg-surface)",
                  borderColor: "var(--border-subtle)",
                }}
              >
                <p
                  className="text-3xl font-bold"
                  style={{ color: "var(--text-primary)" }}
                >
                  {value}
                </p>
                <p
                  className="text-xs mt-1"
                  style={{ color: "var(--text-tertiary)" }}
                >
                  {label}
                </p>
              </div>
            ))}
          </div>

          <Card>
            <CardHeader>
              <h3
                className="text-sm font-semibold"
                style={{ color: "var(--text-primary)" }}
              >
                DNS Records Timeline
              </h3>
            </CardHeader>
            <div
              className="divide-y"
              style={{ borderColor: "var(--border-subtle)" }}
            >
              {sortedFiltered.map((r) => (
                <div key={r.id} className="px-4 py-3 flex items-center gap-4">
                  <span
                    className="w-12 text-xs font-bold font-mono"
                    style={{
                      color: typeColors[r.record_type] ?? "var(--text-secondary)",
                    }}
                  >
                    {r.record_type}
                  </span>
                  <div className="flex-1 min-w-0">
                    <p
                      className="text-sm font-mono truncate"
                      style={{ color: "var(--text-primary)" }}
                    >
                      {r.value}
                    </p>
                    <p
                      className="text-xs"
                      style={{ color: "var(--text-tertiary)" }}
                    >
                      {r.source} · TTL {r.ttl}s · {r.count} observations
                    </p>
                  </div>
                  <div className="text-right shrink-0">
                    <p
                      className="text-xs"
                      style={{ color: "var(--text-tertiary)" }}
                    >
                      <Clock className="inline h-3 w-3 mr-1" />
                      {new Date(r.first_seen).toLocaleDateString()} –{" "}
                      {new Date(r.last_seen).toLocaleDateString()}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </div>
      )}

      {!lookup.data && !lookup.isPending && (
        <div
          className="rounded-xl border py-16 text-center"
          style={{ borderColor: "var(--border-subtle)" }}
        >
          <Database
            className="mx-auto h-10 w-10 mb-3"
            style={{ color: "var(--text-tertiary)" }}
          />
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
            Enter a domain or IP to view passive DNS history
          </p>
        </div>
      )}
    </div>
  );
}
