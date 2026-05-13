import { AlertTriangle, MessageSquare, ChevronDown, ChevronUp } from "lucide-react";
import { useState } from "react";
import type { VehicleOsintScan, VehicleInfo, VehicleRecall } from "../types";

const SPEC_FIELDS: { key: keyof VehicleInfo; label: string }[] = [
  { key: "make", label: "Make" },
  { key: "model", label: "Model" },
  { key: "model_year", label: "Year" },
  { key: "vehicle_type", label: "Type" },
  { key: "body_class", label: "Body" },
  { key: "drive_type", label: "Drive" },
  { key: "fuel_type", label: "Fuel" },
  { key: "engine_cylinders", label: "Cylinders" },
  { key: "engine_displacement", label: "Displacement" },
  { key: "transmission", label: "Transmission" },
  { key: "doors", label: "Doors" },
  { key: "plant_country", label: "Plant Country" },
  { key: "manufacturer", label: "Manufacturer" },
  { key: "series", label: "Series" },
  { key: "trim", label: "Trim" },
];

function RecallCard({ recall }: { recall: VehicleRecall }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <div
      className="rounded-md border p-3 space-y-1.5"
      style={{ borderColor: "var(--border-subtle)", background: "var(--bg-overlay)" }}
    >
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="text-xs font-medium" style={{ color: "var(--warning-500)" }}>
            {recall.recall_id}
          </p>
          {recall.component && (
            <p className="text-xs font-semibold mt-0.5" style={{ color: "var(--text-primary)" }}>
              {recall.component}
            </p>
          )}
        </div>
        <button onClick={() => setExpanded((e) => !e)} className="shrink-0">
          {expanded ? (
            <ChevronUp className="h-4 w-4" style={{ color: "var(--text-tertiary)" }} />
          ) : (
            <ChevronDown className="h-4 w-4" style={{ color: "var(--text-tertiary)" }} />
          )}
        </button>
      </div>
      {recall.summary && (
        <p className={`text-xs ${expanded ? "" : "line-clamp-2"}`} style={{ color: "var(--text-secondary)" }}>
          {recall.summary}
        </p>
      )}
      {expanded && recall.remedy && (
        <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>
          <strong>Remedy:</strong> {recall.remedy}
        </p>
      )}
      {recall.report_date && (
        <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>
          Reported: {recall.report_date}
        </p>
      )}
    </div>
  );
}

function VehicleCard({ vehicle }: { vehicle: VehicleInfo }) {
  const [showComplaints, setShowComplaints] = useState(false);
  const specs = SPEC_FIELDS.filter((f) => vehicle[f.key]);

  return (
    <div
      className="rounded-lg border p-5 space-y-5"
      style={{ background: "var(--bg-surface)", borderColor: "var(--border-subtle)" }}
    >
      {/* Title */}
      <div>
        <h3 className="text-base font-semibold" style={{ color: "var(--text-primary)" }}>
          {[vehicle.model_year, vehicle.make, vehicle.model].filter(Boolean).join(" ") || "Vehicle"}
        </h3>
        {vehicle.vin && (
          <p className="text-xs font-mono mt-0.5" style={{ color: "var(--text-tertiary)" }}>
            VIN: {vehicle.vin}
          </p>
        )}
      </div>

      {/* Specs grid */}
      {specs.length > 0 && (
        <div className="grid grid-cols-2 gap-x-6 gap-y-1.5 text-xs sm:grid-cols-3">
          {specs.map((f) => (
            <div key={f.key}>
              <span className="block" style={{ color: "var(--text-tertiary)" }}>
                {f.label}
              </span>
              <span style={{ color: "var(--text-primary)" }}>{String(vehicle[f.key])}</span>
            </div>
          ))}
        </div>
      )}

      {/* Recalls */}
      {vehicle.recalls.length > 0 && (
        <div>
          <div className="flex items-center gap-2 mb-2">
            <AlertTriangle className="h-4 w-4" style={{ color: "var(--warning-500)" }} />
            <span className="text-sm font-medium" style={{ color: "var(--warning-500)" }}>
              {vehicle.recalls.length} Safety Recall{vehicle.recalls.length !== 1 ? "s" : ""}
            </span>
          </div>
          <div className="space-y-2">
            {vehicle.recalls.map((recall, i) => (
              <RecallCard key={recall.recall_id ?? i} recall={recall} />
            ))}
          </div>
        </div>
      )}

      {/* Complaints */}
      {vehicle.complaints_count > 0 && (
        <div>
          <button
            onClick={() => setShowComplaints((s) => !s)}
            className="flex items-center gap-2 text-sm font-medium hover:opacity-80 transition-opacity"
            style={{ color: "var(--text-secondary)" }}
          >
            <MessageSquare className="h-4 w-4" />
            {vehicle.complaints_count} NHTSA Complaint{vehicle.complaints_count !== 1 ? "s" : ""}
            {showComplaints ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
          </button>
          {showComplaints && vehicle.recent_complaints.length > 0 && (
            <div className="mt-2 space-y-2">
              {vehicle.recent_complaints.map((c, i) => (
                <div
                  key={c.odt_number ?? i}
                  className="rounded-md border p-3 text-xs"
                  style={{ borderColor: "var(--border-subtle)", background: "var(--bg-overlay)" }}
                >
                  <div className="flex gap-3 mb-1">
                    {c.crash && <span className="text-danger-500 font-medium">CRASH</span>}
                    {c.fire && <span className="text-danger-500 font-medium">FIRE</span>}
                    {c.component && <span style={{ color: "var(--text-secondary)" }}>{c.component}</span>}
                  </div>
                  {c.summary && (
                    <p className="line-clamp-3" style={{ color: "var(--text-secondary)" }}>
                      {c.summary}
                    </p>
                  )}
                  {c.date_complaint_filed && (
                    <p className="mt-1" style={{ color: "var(--text-tertiary)" }}>
                      Filed: {c.date_complaint_filed}
                    </p>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {vehicle.recalls.length === 0 && vehicle.complaints_count === 0 && (
        <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>
          No recalls or complaints on record.
        </p>
      )}
    </div>
  );
}

interface Props {
  scan: VehicleOsintScan;
}

export function VehicleResults({ scan }: Props) {
  if (!scan.results.length) {
    return (
      <div
        className="rounded-lg border p-8 text-center text-sm"
        style={{ borderColor: "var(--border-subtle)", color: "var(--text-tertiary)" }}
      >
        No vehicle data found for "{scan.query}".
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <p className="text-sm" style={{ color: "var(--text-tertiary)" }}>
        Found {scan.total_results} vehicle{scan.total_results !== 1 ? "s" : ""}
      </p>
      {scan.results.map((vehicle, idx) => (
        <VehicleCard key={vehicle.vin ?? idx} vehicle={vehicle} />
      ))}
    </div>
  );
}
