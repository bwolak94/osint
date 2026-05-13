import { useState } from "react";
import { Car } from "lucide-react";
import { VehicleSearchForm } from "./components/VehicleSearchForm";
import { VehicleResults } from "./components/VehicleResults";
import { VehicleHistory } from "./components/VehicleHistory";
import { useScanVehicleOsint } from "./hooks";
import type { VehicleOsintScan } from "./types";

export function VehicleOsintPage() {
  const [currentScan, setCurrentScan] = useState<VehicleOsintScan | null>(null);
  const scanMutation = useScanVehicleOsint();

  const handleSearch = (query: string, queryType: "vin" | "make_model") => {
    scanMutation.mutate(
      { query, query_type: queryType },
      { onSuccess: (data) => setCurrentScan(data) }
    );
  };

  return (
    <div className="flex flex-1 flex-col gap-6 p-6">
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-lg" style={{ background: "var(--bg-overlay)" }}>
          <Car className="h-5 w-5" style={{ color: "var(--brand-500)" }} />
        </div>
        <div>
          <h1 className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>
            Vehicle OSINT
          </h1>
          <p className="text-sm" style={{ color: "var(--text-tertiary)" }}>
            VIN decode, safety recalls, and NHTSA complaints via free public APIs
          </p>
        </div>
      </div>

      <div className="rounded-xl border p-5" style={{ background: "var(--bg-surface)", borderColor: "var(--border-subtle)" }}>
        <VehicleSearchForm onSearch={handleSearch} isLoading={scanMutation.isPending} />
      </div>

      {scanMutation.isError && (
        <div className="rounded-md border px-4 py-3 text-sm" style={{ borderColor: "var(--danger-500)", color: "var(--danger-500)", background: "var(--bg-overlay)" }}>
          Lookup failed. Check the VIN or make/model and try again.
        </div>
      )}

      {currentScan && (
        <div className="rounded-xl border p-5" style={{ background: "var(--bg-surface)", borderColor: "var(--border-subtle)" }}>
          <h2 className="mb-4 text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Results</h2>
          <VehicleResults scan={currentScan} />
        </div>
      )}

      <div className="rounded-xl border p-5" style={{ background: "var(--bg-surface)", borderColor: "var(--border-subtle)" }}>
        <h2 className="mb-3 text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Scan History</h2>
        <VehicleHistory onSelect={setCurrentScan} />
      </div>
    </div>
  );
}
