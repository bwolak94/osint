import { useState } from "react";
import { Search, Loader2 } from "lucide-react";

type QueryType = "vin" | "make_model";

interface Props {
  onSearch: (query: string, queryType: QueryType) => void;
  isLoading: boolean;
}

export function VehicleSearchForm({ onSearch, isLoading }: Props) {
  const [query, setQuery] = useState("");
  const [queryType, setQueryType] = useState<QueryType>("vin");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (query.trim()) onSearch(query.trim(), queryType);
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="flex gap-2">
        {(["vin", "make_model"] as QueryType[]).map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => setQueryType(t)}
            className={`rounded-full px-4 py-1.5 text-sm font-medium transition-colors ${
              queryType === t
                ? "bg-brand-500 text-white"
                : "bg-bg-overlay text-text-secondary hover:text-text-primary"
            }`}
          >
            {t === "vin" ? "VIN" : "Make / Model"}
          </button>
        ))}
      </div>

      <div className="space-y-1">
        <div className="flex gap-3">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={queryType === "vin" ? "e.g. 1HGCM82633A004352" : "e.g. Toyota Camry 2020"}
            className="flex-1 rounded-md border px-3 py-2 text-sm font-mono"
            style={{
              background: "var(--bg-overlay)",
              borderColor: "var(--border-subtle)",
              color: "var(--text-primary)",
            }}
          />
          <button
            type="submit"
            disabled={isLoading || !query.trim()}
            className="flex items-center gap-2 rounded-md bg-brand-500 px-4 py-2 text-sm font-medium text-white disabled:opacity-50 hover:bg-brand-600 transition-colors"
          >
            {isLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
            Lookup
          </button>
        </div>
        {queryType === "make_model" && (
          <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>
            Format: Make Model Year (e.g. "Toyota Camry 2020") — year is optional
          </p>
        )}
      </div>
    </form>
  );
}
