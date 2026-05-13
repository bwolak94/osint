import { useState } from "react";
import { FileText, Search, ExternalLink, Clock } from "lucide-react";
import { usePasteMonitor } from "./hooks";
import type { PasteMention } from "./types";
import { Button } from "@/shared/components/Button";
import { Input } from "@/shared/components/Input";
import { Card, CardBody } from "@/shared/components/Card";
import { Badge } from "@/shared/components/Badge";

function MentionCard({ mention }: { mention: PasteMention }) {
  return (
    <div className="rounded-xl border p-4 space-y-2" style={{ background: "var(--bg-surface)", borderColor: "var(--border-subtle)" }}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-1">
            <Badge variant="neutral" size="sm">{mention.source}</Badge>
            {mention.tags.map((t) => <Badge key={t} variant={t === "credentials" ? "danger" : t === "api-key" ? "warning" : "neutral"} size="sm">{t}</Badge>)}
          </div>
          <p className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>{mention.title ?? `Paste ${mention.id}`}</p>
        </div>
        {mention.url && (
          <a href={mention.url} target="_blank" rel="noopener noreferrer" className="flex items-center gap-1 text-xs shrink-0 hover:underline" style={{ color: "var(--brand-400)" }}>
            <ExternalLink className="h-3 w-3" /> View
          </a>
        )}
      </div>
      {mention.snippet && (
        <div className="rounded-md px-3 py-2 font-mono text-xs" style={{ background: "var(--bg-overlay)", color: "var(--text-secondary)" }}>
          {mention.snippet}
        </div>
      )}
      {mention.date && (
        <div className="flex items-center gap-1 text-xs" style={{ color: "var(--text-tertiary)" }}>
          <Clock className="h-3 w-3" />
          {mention.date}
        </div>
      )}
    </div>
  );
}

export function PasteMonitorPage() {
  const [query, setQuery] = useState("");
  const search = usePasteMonitor();

  const handleSearch = () => {
    if (query.trim()) search.mutate(query.trim());
  };

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3">
        <FileText className="h-6 w-6" style={{ color: "var(--warning-400)" }} />
        <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>Paste Monitor</h1>
      </div>

      <Card>
        <CardBody>
          <div className="flex gap-3">
            <div className="flex-1">
              <Input
                placeholder="Email, domain, username, or keyword..."
                prefixIcon={<Search className="h-4 w-4" />}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleSearch()}
              />
            </div>
            <Button onClick={handleSearch} disabled={!query.trim() || search.isPending} leftIcon={<FileText className="h-4 w-4" />}>
              {search.isPending ? "Searching..." : "Search Pastes"}
            </Button>
          </div>
          <p className="mt-2 text-xs" style={{ color: "var(--text-tertiary)" }}>
            Searches paste sites for leaked emails, credentials, and sensitive data.
          </p>
        </CardBody>
      </Card>

      {search.data && (
        <div className="space-y-3">
          <p className="text-sm" style={{ color: "var(--text-tertiary)" }}>
            {search.data.total} mention{search.data.total !== 1 ? "s" : ""} found for "{search.data.query}"
          </p>
          {search.data.mentions.length === 0 ? (
            <div className="rounded-xl border py-10 text-center" style={{ borderColor: "var(--border-subtle)" }}>
              <p className="text-sm" style={{ color: "var(--text-secondary)" }}>No paste mentions found.</p>
            </div>
          ) : (
            search.data.mentions.map((m) => <MentionCard key={m.id} mention={m} />)
          )}
        </div>
      )}

      {!search.data && !search.isPending && (
        <div className="rounded-xl border py-16 text-center" style={{ borderColor: "var(--border-subtle)" }}>
          <FileText className="mx-auto h-10 w-10 mb-3" style={{ color: "var(--text-tertiary)" }} />
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>Enter a search term to monitor paste sites for leaked data</p>
        </div>
      )}
    </div>
  );
}
