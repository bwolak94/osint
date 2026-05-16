import { useState } from "react";
import { Scale, Search, AlertOctagon, FileText } from "lucide-react";
import { useMutation } from "@tanstack/react-query";
import axios from "axios";

interface CourtResult {
  input: string;
  search_query: string;
  findings: Array<{
    type: string;
    severity: string;
    source: string;
    description: string;
    total_cases?: number;
    criminal_cases?: number;
    civil_cases?: number;
    total_opinions?: number;
    sample_cases?: Array<{
      case_name: string;
      docket_number: string;
      court: string;
      date_filed: string;
      case_type: string;
    }>;
    url?: string;
  }>;
  total_found: number;
  total_cases: number;
}

const SEV_COLOR: Record<string, string> = {
  critical: "#dc2626",
  high: "#ea580c",
  medium: "#ca8a04",
  info: "#2563eb",
};

export function CourtRecordsPage() {
  const [query, setQuery] = useState("");

  const mutation = useMutation({
    mutationFn: (q: string) =>
      axios
        .post<CourtResult>("/api/v1/scan", { input_value: q, scanner_name: "court_records" })
        .then((r) => r.data),
  });

  return (
    <div className="min-h-screen p-6" style={{ background: "var(--bg-base)" }}>
      <div className="mx-auto max-w-3xl">
        <div className="mb-8 flex items-center gap-3">
          <div
            className="flex h-10 w-10 items-center justify-center rounded-lg"
            style={{ background: "#450a0a", border: "1px solid #7f1d1d" }}
          >
            <Scale className="h-5 w-5" style={{ color: "#f87171" }} />
          </div>
          <div>
            <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>
              Court Records Search
            </h1>
            <p className="text-sm" style={{ color: "var(--text-tertiary)" }}>
              Search CourtListener, PACER, and Justia for US federal court cases
            </p>
          </div>
        </div>

        <div className="mb-6 flex gap-3">
          <input
            type="text"
            placeholder="Person name, company name, domain, or email..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && query && mutation.mutate(query)}
            className="flex-1 rounded-xl border px-4 py-3 text-sm outline-none"
            style={{
              background: "var(--bg-surface)",
              borderColor: "var(--border-default)",
              color: "var(--text-primary)",
            }}
          />
          <button
            onClick={() => query && mutation.mutate(query)}
            disabled={!query || mutation.isPending}
            className="flex items-center gap-2 rounded-xl px-5 py-3 text-sm font-semibold disabled:opacity-40"
            style={{ background: "var(--brand-500)", color: "#fff" }}
          >
            <Search className="h-4 w-4" />
            {mutation.isPending ? "Searching..." : "Search"}
          </button>
        </div>

        {mutation.data && (
          <div className="space-y-4">
            {mutation.data.findings.filter(f => f.type === "court_records_found" && (f.criminal_cases ?? 0) > 0).length > 0 && (
              <div
                className="flex items-center gap-3 rounded-xl border px-4 py-3"
                style={{ borderColor: "#7f1d1d", background: "#450a0a" }}
              >
                <AlertOctagon className="h-5 w-5 shrink-0" style={{ color: "#f87171" }} />
                <p className="text-sm font-semibold" style={{ color: "#fca5a5" }}>
                  Criminal court records found — proceed with caution
                </p>
              </div>
            )}

            {mutation.data.findings.map((f, i) => (
              <div
                key={i}
                className="rounded-xl border"
                style={{ background: "var(--bg-surface)", borderColor: "var(--border-subtle)" }}
              >
                <div className="flex items-center gap-3 border-b px-5 py-3" style={{ borderColor: "var(--border-subtle)" }}>
                  <FileText className="h-4 w-4" style={{ color: SEV_COLOR[f.severity] || "var(--brand-400)" }} />
                  <span className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>
                    {f.source}
                  </span>
                  <span
                    className="ml-auto rounded-full px-2 py-0.5 text-xs font-bold uppercase"
                    style={{ background: (SEV_COLOR[f.severity] || "#2563eb") + "33", color: SEV_COLOR[f.severity] || "#2563eb" }}
                  >
                    {f.severity}
                  </span>
                </div>
                <div className="px-5 py-4">
                  <p className="mb-3 text-sm" style={{ color: "var(--text-secondary)" }}>{f.description}</p>

                  {f.total_cases !== undefined && (
                    <div className="mb-3 flex gap-4">
                      <div>
                        <span className="text-lg font-bold" style={{ color: "var(--text-primary)" }}>{f.total_cases}</span>
                        <span className="ml-1 text-xs" style={{ color: "var(--text-tertiary)" }}>total</span>
                      </div>
                      {(f.criminal_cases ?? 0) > 0 && (
                        <div>
                          <span className="text-lg font-bold" style={{ color: "#f87171" }}>{f.criminal_cases}</span>
                          <span className="ml-1 text-xs" style={{ color: "var(--text-tertiary)" }}>criminal</span>
                        </div>
                      )}
                      {(f.civil_cases ?? 0) > 0 && (
                        <div>
                          <span className="text-lg font-bold" style={{ color: "#fbbf24" }}>{f.civil_cases}</span>
                          <span className="ml-1 text-xs" style={{ color: "var(--text-tertiary)" }}>civil</span>
                        </div>
                      )}
                    </div>
                  )}

                  {f.sample_cases?.map((c, j) => (
                    <div key={j} className="mb-2 rounded-lg border px-3 py-2" style={{ borderColor: "var(--border-subtle)", background: "var(--bg-base)" }}>
                      <div className="flex items-center justify-between">
                        <p className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>{c.case_name}</p>
                        <span
                          className="text-xs capitalize"
                          style={{ color: c.case_type === "criminal" ? "#f87171" : "#fbbf24" }}
                        >
                          {c.case_type}
                        </span>
                      </div>
                      <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>
                        {c.court} · {c.docket_number} · {c.date_filed}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            ))}

            {mutation.data.total_found === 0 && (
              <div
                className="rounded-xl border px-5 py-8 text-center"
                style={{ background: "var(--bg-surface)", borderColor: "var(--border-subtle)" }}
              >
                <p className="text-sm" style={{ color: "var(--text-tertiary)" }}>
                  No court records found for "{mutation.data.search_query}"
                </p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
