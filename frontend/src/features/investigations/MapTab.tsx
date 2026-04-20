import { Card, CardBody } from "@/shared/components/Card";
import { EmptyState } from "@/shared/components/EmptyState";
import { MapPin } from "lucide-react";

interface MapTabProps {
  scanResults: any[];
}

export function MapTab({ scanResults }: MapTabProps) {
  // Extract locations from GeoIP scan results
  const locations = scanResults
    .filter((r: any) => r.raw_data?.lat && r.raw_data?.lon)
    .map((r: any) => ({
      lat: r.raw_data.lat,
      lon: r.raw_data.lon,
      label: `${r.raw_data.city || ""}, ${r.raw_data.country || ""}`,
      ip: r.input_value,
    }));

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
          <p className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>
            Discovered Locations ({locations.length})
          </p>
          {locations.map((loc: any, i: number) => (
            <div
              key={i}
              className="flex items-center gap-3 rounded-md border p-3"
              style={{ borderColor: "var(--border-subtle)", background: "var(--bg-elevated)" }}
            >
              <MapPin className="h-4 w-4 shrink-0" style={{ color: "var(--brand-500)" }} />
              <div>
                <p className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>
                  {loc.label}
                </p>
                <p className="text-xs font-mono" style={{ color: "var(--text-tertiary)" }}>
                  {loc.ip} — {loc.lat.toFixed(4)}, {loc.lon.toFixed(4)}
                </p>
              </div>
            </div>
          ))}
          <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>
            Interactive map visualization requires Leaflet.js integration (planned for future release).
          </p>
        </div>
      </CardBody>
    </Card>
  );
}
