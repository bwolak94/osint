import { useState } from "react";
import { MapPin, Search, Clock, Home, Briefcase, AlertTriangle } from "lucide-react";
import { useMutation } from "@tanstack/react-query";
import apiClient from "@/shared/api/client";
import { Button } from "@/shared/components/Button";
import { Input } from "@/shared/components/Input";
import { Card, CardBody, CardHeader } from "@/shared/components/Card";
import { Badge } from "@/shared/components/Badge";
import { ScanResultErrorBoundary } from "@/shared/components/osint/ScanResultErrorBoundary";

interface LocationSignal       {mutationError && (
        <p role="alert" className="text-xs rounded-lg px-3 py-2 border" style={{ color: "var(--danger-400)", borderColor: "var(--danger-500)", background: "var(--bg-surface)" }}>
          {mutationError}
        </p>
      )}
      {
  signal_id: string;
  source: string;
  timestamp: string;
  latitude: number | null;
  longitude: number | null;
  location_name: string | null;
  country: string;
  city: string | null;
  raw_evidence: string;
  confidence: number;
}

interface LocationCluster {
  cluster_id: string;
  location_name: string;
  latitude: number;
  longitude: number;
  visit_count: number;
  first_visit: string;
  last_visit: string;
  avg_duration_hours: number;
  location_type: string;
  signals: LocationSignal[];
}

interface TriangulationResult {
  subject: string;
  total_signals: number;
  unique_locations: number;
  countries_visited: string[];
  home_location: LocationCluster | null;
  work_location: LocationCluster | null;
  location_clusters: LocationCluster[];
  location_timeline: LocationSignal[];
  pattern_summary: string;
  privacy_risk_level: string;
}

const SOURCE_ICONS: Record<string, string> = {
  exif: "📷",
  social_post: "📱",
  ip_geolocation: "🌐",
  wifi: "📡",
  cell_tower: "📶",
  checkin: "📍",
};

const DATA_SOURCES = ["social_posts", "ip_geolocation", "exif", "wifi", "cell_tower"];

const locationTypeIcon = (type: string) => {
  if (type === "home") return <Home className="h-4 w-4" style={{ color: "var(--success-400)" }} />;
  if (type === "work") return <Briefcase className="h-4 w-4" style={{ color: "var(--brand-400)" }} />;
  return <MapPin className="h-4 w-4" style={{ color: "var(--text-tertiary)" }} />;
};

const privacyVariant = (level: string): "danger" | "warning" | "neutral" | "success" => {
  if (level === "critical") return "danger";
  if (level === "high") return "warning";
  if (level === "medium") return "neutral";
  return "success";
};

function ClusterCard({ cluster }: { cluster: LocationCluster }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="rounded-xl border p-4 space-y-2" style={{ background: "var(--bg-surface)", borderColor: "var(--border-subtle)" }}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2">
          {locationTypeIcon(cluster.location_type)}
          <div>
            <p className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>{cluster.location_name}</p>
            <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>
              {cluster.visit_count} visit{cluster.visit_count !== 1 ? "s" : ""} · avg {cluster.avg_duration_hours}h
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="neutral" size="sm">{cluster.location_type}</Badge>
          <button className="text-xs underline" style={{ color: "var(--brand-400)" }} onClick={() => setExpanded((e) => !e)}>
            {expanded ? "Less" : "Signals"}
          </button>
        </div>
      </div>

      <div className="flex items-center gap-3 text-xs" style={{ color: "var(--text-tertiary)" }}>
        <span>
          <Clock className="inline h-3 w-3 mr-1" />
          {new Date(cluster.first_visit).toLocaleDateString()} – {new Date(cluster.last_visit).toLocaleDateString()}
        </span>
        <span>📍 {cluster.latitude.toFixed(4)}, {cluster.longitude.toFixed(4)}</span>
      </div>

      {expanded && (
        <div className="space-y-1.5 pt-2 border-t" style={{ borderColor: "var(--border-subtle)" }}>
          {cluster.signals.slice(0, 6).map((sig) => (
            <div key={sig.signal_id} className="flex items-start gap-2 text-xs">
              <span className="shrink-0">{SOURCE_ICONS[sig.source] || "•"}</span>
              <span style={{ color: "var(--text-secondary)" }}>{sig.raw_evidence}</span>
              <span className="ml-auto shrink-0" style={{ color: "var(--text-tertiary)" }}>
                {(sig.confidence * 100).toFixed(0)}%
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export function GeolocationPage() {
  const [subject, setSubject] = useState("");
  const [mutationError, setMutationError] = useState<string | null>(null);
  const [selectedSources, setSelectedSources] = useState<string[]>(["social_posts", "ip_geolocation", "exif"]);

  const triangulate = useMutation({
    mutationFn: (data: { subject_identifier: string; data_sources: string[] }) =>
      apiClient.post<TriangulationResult>("/api/v1/geolocation/triangulate", data).then((r) => r.data),
  });

  const toggleSource = (src: string) => {
    setSelectedSources((prev) =>
      prev.includes(src) ? prev.filter((s) => s !== src) : [...prev, src]
    );
  };

  const handleTriangulate = () => {
    if (subject.trim() && selectedSources.length) {
      triangulate.mutate({ subject_identifier: subject.trim(), data_sources: selectedSources });
    }
  };

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3">
        <MapPin className="h-6 w-6" style={{ color: "var(--brand-400)" }} />
        <div>
          <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>Geolocation Triangulation</h1>
          <p className="text-xs mt-0.5" style={{ color: "var(--text-tertiary)" }}>Multi-source location intelligence and pattern analysis</p>
        </div>
      </div>

      <Card>
        <CardHeader>
          <p className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>Subject & Data Sources</p>
        </CardHeader>
        <CardBody className="space-y-3">
          <div>
            <label className="text-xs mb-1 block" style={{ color: "var(--text-tertiary)" }}>Subject Identifier</label>
            <Input
              placeholder="Username, email, or IP address"
              prefixIcon={<Search className="h-4 w-4" />}
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
            />
          </div>

          <div>
            <label className="text-xs mb-1 block" style={{ color: "var(--text-tertiary)" }}>Data Sources</label>
            <div className="flex gap-2 flex-wrap">
              {DATA_SOURCES.map((src) => (
                <button
                  key={src}
                  onClick={() => toggleSource(src)}
                  className="text-xs px-2.5 py-1 rounded-lg border transition-colors"
                  style={{
                    borderColor: selectedSources.includes(src) ? "var(--brand-400)" : "var(--border-subtle)",
                    background: selectedSources.includes(src) ? "var(--brand-950)" : "var(--bg-surface)",
                    color: selectedSources.includes(src) ? "var(--brand-300)" : "var(--text-secondary)",
                  }}
                >
                  {src.replace("_", " ")}
                </button>
              ))}
            </div>
          </div>

          <Button
            onClick={handleTriangulate}
            disabled={!subject.trim() || selectedSources.length === 0 || triangulate.isPending}
            leftIcon={<MapPin className="h-4 w-4" />}
          >
            {triangulate.isPending ? "Triangulating..." : "Triangulate Location"}
          </Button>
        </CardBody>
      </Card>

      {triangulate.data && (
        <div className="space-y-4">
          {/* Privacy risk banner */}
          <div
            className="rounded-xl border p-4 flex items-start gap-3"
            style={{
              background: "var(--bg-surface)",
              borderColor: triangulate.data.privacy_risk_level === "critical" ? "var(--danger-500)" : "var(--border-subtle)",
            }}
          >
            <AlertTriangle className="h-5 w-5 shrink-0" style={{ color: "var(--danger-400)" }} />
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-1">
                <Badge variant={privacyVariant(triangulate.data.privacy_risk_level)}>
                  {triangulate.data.privacy_risk_level.toUpperCase()} PRIVACY RISK
                </Badge>
              </div>
              <p className="text-xs" style={{ color: "var(--text-secondary)" }}>{triangulate.data.pattern_summary}</p>
            </div>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {[
              { label: "Signals", value: triangulate.data.total_signals },
              { label: "Locations", value: triangulate.data.unique_locations },
              { label: "Countries", value: triangulate.data.countries_visited.length },
              { label: "Home ID'd", value: triangulate.data.home_location ? "Yes" : "No", color: triangulate.data.home_location ? "var(--danger-400)" : "var(--text-primary)" },
            ].map(({ label, value, color }) => (
              <div key={label} className="rounded-xl border p-3 text-center" style={{ background: "var(--bg-surface)", borderColor: "var(--border-subtle)" }}>
                <p className="text-2xl font-bold" style={{ color: color || "var(--text-primary)" }}>{value}</p>
                <p className="text-xs mt-1" style={{ color: "var(--text-tertiary)" }}>{label}</p>
              </div>
            ))}
          </div>

          <div className="space-y-3">
            <p className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Location Clusters</p>
            {triangulate.data.location_clusters.map((c) => <ClusterCard key={c.cluster_id} cluster={c} />)}
          </div>

          {triangulate.data.location_timeline.length > 0 && (
            <div className="rounded-xl border p-4" style={{ background: "var(--bg-surface)", borderColor: "var(--border-subtle)" }}>
              <p className="text-sm font-semibold mb-3" style={{ color: "var(--text-primary)" }}>
                Timeline (last {Math.min(10, triangulate.data.location_timeline.length)} signals)
              </p>
              <div className="space-y-2">
                {triangulate.data.location_timeline.slice(-10).reverse().map((sig) => (
                  <div key={sig.signal_id} className="flex items-start gap-3 text-xs">
                    <span className="shrink-0">{SOURCE_ICONS[sig.source] || "•"}</span>
                    <div className="flex-1 min-w-0">
                      <span style={{ color: "var(--text-secondary)" }}>{sig.raw_evidence}</span>
                    </div>
                    <span className="shrink-0" style={{ color: "var(--text-tertiary)" }}>
                      {new Date(sig.timestamp).toLocaleDateString()}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {!triangulate.data && !triangulate.isPending && (
        <div className="rounded-xl border py-16 text-center" style={{ borderColor: "var(--border-subtle)" }}>
          <MapPin className="mx-auto h-10 w-10 mb-3" style={{ color: "var(--text-tertiary)" }} />
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>Enter a subject identifier to triangulate location patterns</p>
        </div>
      )}
    </div>
  );
}
