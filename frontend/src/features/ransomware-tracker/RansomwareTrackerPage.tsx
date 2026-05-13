import { useState } from "react";
import { Lock, Search, Building2, ExternalLink, Calendar } from "lucide-react";
import { useRansomwareTracker } from "./hooks";
import type { RansomwareVictim, RansomwareTrackerResult } from "./types";
import { Button } from "@/shared/components/Button";
import { Input } from "@/shared/components/Input";
import { Card, CardBody } from "@/shared/components/Card";
import { Badge } from "@/shared/components/Badge";

function VictimCard({ victim }: { victim: RansomwareVictim }) {
  return (
    <div className="rounded-xl border p-4 space-y-2" style={{ background: "var(--bg-surface)", borderColor: "var(--border-subtle)" }}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 flex-wrap mb-1">
            <span className="font-medium text-sm" style={{ color: "var(--text-primary)" }}>{victim.victim}</span>
            {victim.group && <Badge variant="danger" size="sm">{victim.group}</Badge>}
            {victim.country && <Badge variant="neutral" size="sm">{victim.country}</Badge>}
          </div>
          {victim.activity && <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>{victim.activity}</p>}
        </div>
        {victim.url && (
          <a href={victim.url} target="_blank" rel="noopener noreferrer" className="flex items-center gap-1 text-xs shrink-0 hover:underline" style={{ color: "var(--brand-400)" }}>
            <ExternalLink className="h-3 w-3" />
          </a>
        )}
      </div>
      {victim.description && (
        <p className="text-xs line-clamp-2" style={{ color: "var(--text-secondary)" }}>{victim.description}</p>
      )}
      {victim.discovered && (
        <div className="flex items-center gap-1 text-xs" style={{ color: "var(--text-tertiary)" }}>
          <Calendar className="h-3 w-3" />{victim.discovered}
        </div>
      )}
    </div>
  );
}

function TrackerResults({ data }: { data: RansomwareTrackerResult }) {
  return (
    <div className="space-y-4">
      {data.group_info && (
        <div className="rounded-xl border p-4 space-y-2" style={{ background: "var(--bg-surface)", borderColor: "var(--danger-500)" }}>
          <div className="flex items-center gap-2">
            <Lock className="h-4 w-4" style={{ color: "var(--danger-400)" }} />
            <span className="text-sm font-semibold" style={{ color: "var(--danger-400)" }}>{data.group_info.name}</span>
          </div>
          {data.group_info.description && <p className="text-sm" style={{ color: "var(--text-secondary)" }}>{data.group_info.description}</p>}
          {data.group_info.locations.length > 0 && (
            <div className="flex flex-wrap gap-1">{data.group_info.locations.map((l) => <Badge key={l} variant="neutral" size="sm">{l}</Badge>)}</div>
          )}
        </div>
      )}

      <div className="grid gap-3 sm:grid-cols-2">
        {[
          { label: "Total Victims Found", value: data.total_victims, color: data.total_victims > 0 ? "var(--danger-400)" : "var(--text-primary)" },
        ].map(({ label, value, color }) => (
          <div key={label} className="rounded-xl border p-4 text-center" style={{ background: "var(--bg-surface)", borderColor: "var(--border-subtle)" }}>
            <p className="text-3xl font-bold" style={{ color }}>{value}</p>
            <p className="text-xs mt-1" style={{ color: "var(--text-tertiary)" }}>{label}</p>
          </div>
        ))}
      </div>

      {data.victims.length > 0 && (
        <div className="space-y-3">
          <p className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Victims</p>
          {data.victims.map((v, i) => <VictimCard key={`${v.victim}-${i}`} victim={v} />)}
        </div>
      )}

      {data.victims.length === 0 && !data.group_info && (
        <div className="rounded-xl border py-10 text-center" style={{ borderColor: "var(--border-subtle)" }}>
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>No ransomware records found for "{data.query}"</p>
        </div>
      )}
    </div>
  );
}

export function RansomwareTrackerPage() {
  const [query, setQuery] = useState("");
  const search = useRansomwareTracker();

  const handleSearch = () => {
    if (query.trim()) search.mutate(query.trim());
  };

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3">
        <Lock className="h-6 w-6" style={{ color: "var(--danger-400)" }} />
        <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>Ransomware Tracker</h1>
      </div>

      <Card>
        <CardBody>
          <div className="flex gap-3">
            <div className="flex-1">
              <Input
                placeholder="Company name, domain, or ransomware group (e.g. lockbit)..."
                prefixIcon={<Search className="h-4 w-4" />}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleSearch()}
              />
            </div>
            <Button onClick={handleSearch} disabled={!query.trim() || search.isPending} leftIcon={<Lock className="h-4 w-4" />}>
              {search.isPending ? "Tracking..." : "Track"}
            </Button>
          </div>
          <p className="mt-2 text-xs" style={{ color: "var(--text-tertiary)" }}>
            Powered by ransomware.live — real-time ransomware victim tracking.
          </p>
        </CardBody>
      </Card>

      {search.data && <TrackerResults data={search.data} />}

      {!search.data && !search.isPending && (
        <div className="rounded-xl border py-16 text-center" style={{ borderColor: "var(--border-subtle)" }}>
          <Lock className="mx-auto h-10 w-10 mb-3" style={{ color: "var(--text-tertiary)" }} />
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>Search for ransomware victims or group intelligence</p>
        </div>
      )}
    </div>
  );
}
