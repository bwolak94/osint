import { useState } from "react";
import { Lock, Search, Target, ChevronDown, ChevronUp } from "lucide-react";
import { useMutation } from "@tanstack/react-query";
import apiClient from "@/shared/api/client";
import { Button } from "@/shared/components/Button";
import { Input } from "@/shared/components/Input";
import { Card, CardBody, CardHeader } from "@/shared/components/Card";
import { Badge } from "@/shared/components/Badge";
import { ScanResultErrorBoundary } from "@/shared/components/osint/ScanResultErrorBoundary";

interface TTPMatch {
  technique_id: string;
  technique_name: string;
  tactic: string;
  confidence: number;
}

interface GroupProfile {
  group_name: string;
  also_known_as: string[];
  attribution_confidence: number;
  active_since: string;
  last_activity: string;
  avg_ransom_demand_usd: number;
  victim_count_total: number;
  ttp_matches: TTPMatch[];
  known_extensions: string[];
  encryption_algorithm: string;
  double_extortion: boolean;
  affiliate_program: boolean;
  negotiation_style: string;
  ioc_overlap_count: number;
}

interface AttributionResult {
  query_indicators: number;
  top_match: GroupProfile | null;
  all_candidates: GroupProfile[];
  attribution_summary: string;
}

function ConfidenceBar({ value }: { value: number }) {
  const color = value >= 0.7 ? "var(--danger-500)" : value >= 0.5 ? "var(--warning-500)" : "var(--success-500)";
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-2 rounded-full overflow-hidden" style={{ background: "var(--bg-raised)" }}>
        <div className="h-full rounded-full transition-all" style={{ width: `${value * 100}%`, background: color }} />
      </div>
      <span className="text-xs font-mono w-10 text-right" style={{ color: "var(--text-secondary)" }}>
        {(value * 100).toFixed(0)}%
      </span>
    </div>
  );
}

function GroupCard({ group, isTop }: { group: GroupProfile; isTop: boolean }) {
  const [expanded, setExpanded] = useState(isTop);

  return (
    <div
      className="rounded-xl border p-4 space-y-3"
      style={{ background: "var(--bg-surface)", borderColor: isTop ? "var(--danger-500)" : "var(--border-subtle)" }}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="font-semibold" style={{ color: "var(--text-primary)" }}>{group.group_name}</span>
            {isTop && <Badge variant="danger" size="sm">Top Match</Badge>}
            {group.double_extortion && <Badge variant="warning" size="sm">Double Extortion</Badge>}
          </div>
          <p className="text-xs mt-0.5" style={{ color: "var(--text-tertiary)" }}>
            {group.also_known_as.join(", ")}
          </p>
        </div>
        <button onClick={() => setExpanded((e) => !e)} style={{ color: "var(--text-tertiary)" }}>
          {expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
        </button>
      </div>

      <div>
        <p className="text-xs mb-1" style={{ color: "var(--text-tertiary)" }}>Attribution Confidence</p>
        <ConfidenceBar value={group.attribution_confidence} />
      </div>

      {expanded && (
        <div className="space-y-3 pt-2 border-t" style={{ borderColor: "var(--border-subtle)" }}>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 text-xs">
            <div>
              <p style={{ color: "var(--text-tertiary)" }}>Avg Ransom</p>
              <p className="font-medium" style={{ color: "var(--warning-400)" }}>
                ${group.avg_ransom_demand_usd.toLocaleString()}
              </p>
            </div>
            <div>
              <p style={{ color: "var(--text-tertiary)" }}>Total Victims</p>
              <p className="font-medium" style={{ color: "var(--text-primary)" }}>{group.victim_count_total}</p>
            </div>
            <div>
              <p style={{ color: "var(--text-tertiary)" }}>IOC Overlaps</p>
              <p className="font-medium" style={{ color: group.ioc_overlap_count > 0 ? "var(--danger-400)" : "var(--text-primary)" }}>
                {group.ioc_overlap_count}
              </p>
            </div>
            <div>
              <p style={{ color: "var(--text-tertiary)" }}>Active Since</p>
              <p className="font-medium" style={{ color: "var(--text-primary)" }}>{group.active_since}</p>
            </div>
            <div>
              <p style={{ color: "var(--text-tertiary)" }}>Last Activity</p>
              <p className="font-medium" style={{ color: "var(--text-primary)" }}>{group.last_activity}</p>
            </div>
            <div>
              <p style={{ color: "var(--text-tertiary)" }}>Encryption</p>
              <p className="font-medium text-xs" style={{ color: "var(--text-primary)" }}>{group.encryption_algorithm}</p>
            </div>
          </div>

          <div>
            <p className="text-xs mb-1" style={{ color: "var(--text-tertiary)" }}>Known Extensions</p>
            <div className="flex gap-1 flex-wrap">
              {group.known_extensions.map((ext) => (
                <code key={ext} className="text-xs px-1.5 py-0.5 rounded" style={{ background: "var(--bg-raised)", color: "var(--text-secondary)" }}>
                  {ext}
                </code>
              ))}
            </div>
          </div>

          {group.ttp_matches.length > 0 && (
            <div>
              <p className="text-xs mb-1" style={{ color: "var(--text-tertiary)" }}>TTP Matches ({group.ttp_matches.length})</p>
              <div className="space-y-1">
                {group.ttp_matches.slice(0, 5).map((ttp) => (
                  <div key={ttp.technique_id} className="flex items-center gap-2 text-xs">
                    <code className="px-1.5 py-0.5 rounded shrink-0" style={{ background: "var(--bg-raised)", color: "var(--brand-400)" }}>
                      {ttp.technique_id}
                    </code>
                    <span style={{ color: "var(--text-secondary)" }}>{ttp.technique_name}</span>
                    <span className="ml-auto shrink-0" style={{ color: "var(--text-tertiary)" }}>{ttp.tactic}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          <p className="text-xs" style={{ color: "var(--text-secondary)" }}>
            <strong style={{ color: "var(--text-primary)" }}>Negotiation:</strong> {group.negotiation_style}
          </p>
        </div>
      )}
    </div>
  );
}

export function RansomwareAttributionPage() {
  const [indicators, setIndicators] = useState("");
  const [mutationError, setMutationError] = useState<string | null>(null);
  const [extension, setExtension] = useState("");
  const [ransomnote, setRansomnote] = useState("");

  const analyze = useMutation({
    mutationFn: (data: { indicators: string[]; file_extension?: string; ransom_note_snippet?: string }) =>
      apiClient.post<AttributionResult>("/api/v1/ransomware-attribution/analyze", data).then((r) => r.data),
  });

  const handleAnalyze = () => {
    const inds = indicators.split("\n").map((s) => s.trim()).filter(Boolean);
    if (!inds.length) return;
    analyze.mutate({
      indicators: inds,
      file_extension: extension.trim() || undefined,
      ransom_note_snippet: ransomnote.trim() || undefined,
    });
  };

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3">
        <Target className="h-6 w-6" style={{ color: "var(--danger-400)" }} />
        <div>
          <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>Ransomware Attribution</h1>
          <p className="text-xs mt-0.5" style={{ color: "var(--text-tertiary)" }}>TTP correlation engine for RaaS group attribution</p>
        </div>
      </div>

      <Card>
        <CardHeader>
          <p className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>Submit Incident Indicators</p>
        </CardHeader>
        <CardBody className="space-y-3">
          <div>
            <label className="text-xs mb-1 block" style={{ color: "var(--text-tertiary)" }}>
              IOCs / Indicators (one per line — hashes, IPs, domains)
            </label>
            <textarea
              className="w-full rounded-lg border px-3 py-2 text-xs font-mono resize-none h-24"
              style={{ background: "var(--bg-surface)", borderColor: "var(--border-subtle)", color: "var(--text-primary)" }}
              placeholder={"d41d8cd98f00b204e9800998ecf8427e\n45.33.32.156\nmalware.example.com"}
              value={indicators}
              onChange={(e) => setIndicators(e.target.value)}
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs mb-1 block" style={{ color: "var(--text-tertiary)" }}>File Extension</label>
              <Input placeholder=".lockbit" value={extension} onChange={(e) => setExtension(e.target.value)} />
            </div>
            <div>
              <label className="text-xs mb-1 block" style={{ color: "var(--text-tertiary)" }}>Ransom Note Snippet</label>
              <Input placeholder="Your files have been..." value={ransomnote} onChange={(e) => setRansomnote(e.target.value)} />
            </div>
          </div>

          <Button
            onClick={handleAnalyze}
            disabled={!indicators.trim() || analyze.isPending}
            leftIcon={<Target className="h-4 w-4" />}
          >
            {analyze.isPending ? "Analyzing..." : "Attribute Group"}
          </Button>
        </CardBody>
      </Card>

      {analyze.data && (
        <div className="space-y-4">
          <div className="rounded-xl border p-4" style={{ background: "var(--bg-surface)", borderColor: "var(--border-subtle)" }}>
            <p className="text-xs" style={{ color: "var(--text-secondary)" }}>{analyze.data.attribution_summary}</p>
          </div>

          <div className="space-y-3">
            <p className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
              Attribution Candidates ({analyze.data.all_candidates.length})
            </p>
            {analyze.data.all_candidates.map((g, i) => (
              <GroupCard key={g.group_name} group={g} isTop={i === 0} />
            ))}
          </div>
        </div>
      )}

      {!analyze.data && !analyze.isPending && (
        <div className="rounded-xl border py-16 text-center" style={{ borderColor: "var(--border-subtle)" }}>
          <Target className="mx-auto h-10 w-10 mb-3" style={{ color: "var(--text-tertiary)" }} />
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>Submit IOCs and TTPs to attribute ransomware to known groups</p>
        </div>
      )}
    </div>
  );
}
