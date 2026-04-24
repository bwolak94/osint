import { useState } from "react";
import { Radio, Plus, Download, Shield, AlertTriangle } from "lucide-react";
import { Badge } from "@/shared/components/Badge";
import { Button } from "@/shared/components/Button";
import { Card, CardHeader, CardBody } from "@/shared/components/Card";
import { Input } from "@/shared/components/Input";
import { useThreatFeeds, useCreateFeed, useExportFeed } from "./hooks";
import type { ThreatFeed, ThreatIndicator } from "./types";

const TLP_COLORS: Record<string, string> = {
  WHITE: "var(--text-secondary)",
  GREEN: "var(--success-400)",
  AMBER: "var(--warning-400)",
  RED: "var(--danger-400)",
};

const SEV_VARIANT: Record<string, "danger" | "warning" | "info"> = {
  critical: "danger",
  high: "danger",
  medium: "warning",
};

function IndicatorRow({ ind }: { ind: ThreatIndicator }) {
  return (
    <tr className="border-b" style={{ borderColor: "var(--border-subtle)" }}>
      <td className="px-4 py-2">
        <Badge variant="neutral" size="sm">{ind.type}</Badge>
      </td>
      <td className="px-4 py-2 font-mono text-xs" style={{ color: "var(--text-primary)" }}>{ind.value}</td>
      <td className="px-4 py-2">
        <Badge variant={SEV_VARIANT[ind.severity] ?? "neutral"} size="sm">{ind.severity}</Badge>
      </td>
      <td className="px-4 py-2 text-sm" style={{ color: "var(--text-secondary)" }}>{ind.confidence}%</td>
      <td className="px-4 py-2">
        <span className="text-xs font-bold" style={{ color: TLP_COLORS[ind.tlp] }}>TLP:{ind.tlp}</span>
      </td>
      <td className="px-4 py-2">
        <div className="flex flex-wrap gap-1">
          {ind.tags.map((t) => <Badge key={t} variant="neutral" size="sm">{t}</Badge>)}
        </div>
      </td>
    </tr>
  );
}

function FeedCard({ feed, onExport }: { feed: ThreatFeed; onExport: (id: string) => void }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <Radio className="h-4 w-4 shrink-0" style={{ color: "var(--brand-500)" }} />
              <span className="font-semibold text-sm" style={{ color: "var(--text-primary)" }}>{feed.name}</span>
              <Badge variant="neutral" size="sm">{feed.format}</Badge>
              <Badge variant="success" size="sm" dot>{feed.status}</Badge>
            </div>
            <p className="mt-1 text-xs" style={{ color: "var(--text-tertiary)" }}>{feed.description}</p>
          </div>
          <div className="flex gap-2 shrink-0">
            <Button size="sm" variant="ghost" leftIcon={<Download className="h-3.5 w-3.5" />} onClick={() => onExport(feed.id)}>
              Export
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setExpanded((p) => !p)}>
              {expanded ? "Hide" : "Show"} indicators
            </Button>
          </div>
        </div>
        <div className="mt-2 flex gap-4 text-xs" style={{ color: "var(--text-tertiary)" }}>
          <span>{feed.indicator_count} indicators</span>
          <span>{feed.subscribers} subscribers</span>
          <span>Updated {new Date(feed.last_updated).toLocaleDateString()}</span>
        </div>
      </CardHeader>
      {expanded && feed.indicators.length > 0 && (
        <CardBody className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b text-left text-xs font-medium" style={{ borderColor: "var(--border-subtle)", color: "var(--text-tertiary)" }}>
                  <th className="px-4 py-2">Type</th>
                  <th className="px-4 py-2">Value</th>
                  <th className="px-4 py-2">Severity</th>
                  <th className="px-4 py-2">Confidence</th>
                  <th className="px-4 py-2">TLP</th>
                  <th className="px-4 py-2">Tags</th>
                </tr>
              </thead>
              <tbody>
                {feed.indicators.map((ind) => <IndicatorRow key={ind.id} ind={ind} />)}
              </tbody>
            </table>
          </div>
        </CardBody>
      )}
    </Card>
  );
}

export function ThreatFeedPage() {
  const { data: feeds = [], isLoading } = useThreatFeeds();
  const createFeed = useCreateFeed();
  const exportFeed = useExportFeed();
  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [desc, setDesc] = useState("");
  const [format, setFormat] = useState("JSON");

  const handleCreate = () => {
    if (!name.trim()) return;
    createFeed.mutate({ name: name.trim(), description: desc.trim(), format }, {
      onSuccess: () => { setShowForm(false); setName(""); setDesc(""); },
    });
  };

  const handleExport = (feedId: string) => {
    exportFeed.mutate({ feedId, format: "json" });
  };

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Shield className="h-6 w-6" style={{ color: "var(--brand-500)" }} />
          <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>Threat Intelligence Feeds</h1>
          <Badge variant="neutral" size="sm">{feeds.length}</Badge>
        </div>
        <Button leftIcon={<Plus className="h-4 w-4" />} onClick={() => setShowForm((p) => !p)}>
          New Feed
        </Button>
      </div>

      {showForm && (
        <Card>
          <CardBody className="space-y-3">
            <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Create Threat Feed</h3>
            <Input placeholder="Feed name" value={name} onChange={(e) => setName(e.target.value)} />
            <Input placeholder="Description" value={desc} onChange={(e) => setDesc(e.target.value)} />
            <div className="flex gap-2">
              {["JSON", "STIX", "MISP", "CSV"].map((f) => (
                <button
                  key={f}
                  onClick={() => setFormat(f)}
                  className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${format === f ? "bg-brand-900 text-brand-400" : "text-text-secondary hover:bg-bg-overlay"}`}
                >{f}</button>
              ))}
            </div>
            <div className="flex gap-2">
              <Button size="sm" onClick={handleCreate} loading={createFeed.isPending}>Create</Button>
              <Button size="sm" variant="ghost" onClick={() => setShowForm(false)}>Cancel</Button>
            </div>
          </CardBody>
        </Card>
      )}

      {isLoading ? (
        <div className="flex justify-center py-12"><AlertTriangle className="h-5 w-5 animate-pulse" style={{ color: "var(--text-tertiary)" }} /></div>
      ) : feeds.length === 0 ? (
        <Card><CardBody><p className="text-center text-sm" style={{ color: "var(--text-tertiary)" }}>No feeds yet. Create your first threat intelligence feed.</p></CardBody></Card>
      ) : (
        <div className="space-y-3">
          {feeds.map((feed) => <FeedCard key={feed.id} feed={feed} onExport={handleExport} />)}
        </div>
      )}
    </div>
  );
}
