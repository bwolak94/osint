import { useMemo, useState } from "react";
import { Card, CardBody } from "@/shared/components/Card";
import { EmptyState } from "@/shared/components/EmptyState";
import { Badge } from "@/shared/components/Badge";
import { MapPin, ChevronDown, ChevronUp } from "lucide-react";

interface Location {
  lat: number;
  lon: number;
  label: string;
  ip: string;
}

interface Cluster {
  lat: number;
  lon: number;
  label: string;
  items: Location[];
}

interface MapTabProps {
  scanResults: any[];
}

const CLUSTER_THRESHOLD = 2.0; // degrees (~222 km)

function clusterLocations(locs: Location[]): Cluster[] {
  const clusters: Cluster[] = [];
  for (const loc of locs) {
    const existing = clusters.find(
      (c) =>
        Math.abs(c.lat - loc.lat) < CLUSTER_THRESHOLD &&
        Math.abs(c.lon - loc.lon) < CLUSTER_THRESHOLD,
    );
    if (existing) {
      existing.items.push(loc);
      existing.lat = existing.items.reduce((s, l) => s + l.lat, 0) / existing.items.length;
      existing.lon = existing.items.reduce((s, l) => s + l.lon, 0) / existing.items.length;
    } else {
      clusters.push({ lat: loc.lat, lon: loc.lon, label: loc.label, items: [loc] });
    }
  }
  return clusters;
}

function ClusterRow({ cluster }: { cluster: Cluster }) {
  const [expanded, setExpanded] = useState(false);
  const isCluster = cluster.items.length > 1;

  return (
    <div
      className="rounded-md border"
      style={{ borderColor: "var(--border-subtle)", background: "var(--bg-elevated)" }}
    >
      <button
        className="flex w-full items-center gap-3 p-3 text-left"
        onClick={() => isCluster && setExpanded((p) => !p)}
        aria-expanded={isCluster ? expanded : undefined}
      >
        <MapPin
          className="h-4 w-4 shrink-0"
          style={{ color: isCluster ? "var(--warning-500)" : "var(--brand-500)" }}
        />
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium truncate" style={{ color: "var(--text-primary)" }}>
            {isCluster ? `${cluster.items.length} locations near ${cluster.label}` : cluster.label}
          </p>
          <p className="text-xs font-mono" style={{ color: "var(--text-tertiary)" }}>
            {cluster.lat.toFixed(4)}, {cluster.lon.toFixed(4)}
            {!isCluster && ` — ${cluster.items[0]?.ip}`}
          </p>
        </div>
        {isCluster && (
          <div className="flex items-center gap-2">
            <Badge variant="warning" size="sm">{cluster.items.length}</Badge>
            {expanded ? (
              <ChevronUp className="h-3.5 w-3.5" style={{ color: "var(--text-tertiary)" }} />
            ) : (
              <ChevronDown className="h-3.5 w-3.5" style={{ color: "var(--text-tertiary)" }} />
            )}
          </div>
        )}
      </button>

      {isCluster && expanded && (
        <div
          className="border-t"
          style={{ borderColor: "var(--border-subtle)" }}
        >
          {cluster.items.map((loc, i) => (
            <div
              key={i}
              className="flex items-center gap-3 px-4 py-2"
              style={{ borderBottom: i < cluster.items.length - 1 ? "1px solid var(--border-subtle)" : undefined }}
            >
              <MapPin className="h-3.5 w-3.5 shrink-0" style={{ color: "var(--text-tertiary)" }} />
              <div>
                <p className="text-xs font-medium" style={{ color: "var(--text-secondary)" }}>
                  {loc.label || "Unknown location"}
                </p>
                <p className="text-xs font-mono" style={{ color: "var(--text-tertiary)" }}>
                  {loc.ip} — {loc.lat.toFixed(4)}, {loc.lon.toFixed(4)}
                </p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export function MapTab({ scanResults }: MapTabProps) {
  const locations = useMemo<Location[]>(
    () =>
      scanResults
        .filter((r: any) => r.raw_data?.lat && r.raw_data?.lon)
        .map((r: any) => ({
          lat: r.raw_data.lat,
          lon: r.raw_data.lon,
          label: `${r.raw_data.city || ""}, ${r.raw_data.country || ""}`.replace(/^, |, $/, ""),
          ip: r.input_value,
        })),
    [scanResults],
  );

  const clusters = useMemo(() => clusterLocations(locations), [locations]);
  const clusterCount = clusters.filter((c) => c.items.length > 1).length;

  if (locations.length === 0) {
    return (
      <EmptyState
        variant="no-data"
        title="No geographic data"
        description="Run a GeoIP scan on IP addresses to see their locations on a map. Add IP address seeds and enable the GeoIP scanner."
        action={
          <div className="flex items-center gap-2 text-xs" style={{ color: "var(--text-tertiary)" }}>
            <MapPin className="h-4 w-4" /> Requires GeoIP scanner results
          </div>
        }
      />
    );
  }

  return (
    <Card>
      <CardBody>
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <p className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>
              Discovered Locations ({locations.length})
            </p>
            <div className="flex items-center gap-2 text-xs" style={{ color: "var(--text-tertiary)" }}>
              {clusterCount > 0 && (
                <Badge variant="warning" size="sm">{clusterCount} cluster{clusterCount !== 1 ? "s" : ""}</Badge>
              )}
              <span>{clusters.length} group{clusters.length !== 1 ? "s" : ""}</span>
            </div>
          </div>

          {clusters.map((cluster, i) => (
            <ClusterRow key={i} cluster={cluster} />
          ))}

          <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>
            Nearby markers (within {CLUSTER_THRESHOLD}°) are grouped into clusters. Interactive map visualization requires Leaflet.js integration (planned).
          </p>
        </div>
      </CardBody>
    </Card>
  );
}
