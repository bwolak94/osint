import { useState } from "react";
import { Lightbulb, Search, FileText, Users } from "lucide-react";
import { useMutation } from "@tanstack/react-query";
import axios from "axios";

interface PatentResult {
  input: string;
  findings: Array<{
    type: string;
    severity: string;
    source: string;
    description: string;
    assignee?: string;
    inventor?: string;
    total_patents?: number;
    co_inventors?: string[];
    assignee_companies?: string[];
    sample_patents?: Array<{ patent_number: string; title: string; date: string }>;
    total_results?: number;
    url?: string;
  }>;
  total_found: number;
}

export function PatentIntelPage() {
  const [query, setQuery] = useState("");

  const mutation = useMutation({
    mutationFn: (q: string) =>
      axios
        .post<PatentResult>("/api/v1/scan", { input_value: q, scanner_name: "patent" })
        .then((r) => r.data),
  });

  return (
    <div className="min-h-screen p-6" style={{ background: "var(--bg-base)" }}>
      <div className="mx-auto max-w-3xl">
        <div className="mb-8 flex items-center gap-3">
          <div
            className="flex h-10 w-10 items-center justify-center rounded-lg"
            style={{ background: "var(--brand-subtle)", border: "1px solid var(--brand-border)" }}
          >
            <Lightbulb className="h-5 w-5" style={{ color: "var(--brand-400)" }} />
          </div>
          <div>
            <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>
              Patent Intelligence
            </h1>
            <p className="text-sm" style={{ color: "var(--text-tertiary)" }}>
              Search USPTO PatentsView and Google Patents for inventor/assignee data
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
            {mutation.data.findings.map((f, i) => (
              <div
                key={i}
                className="rounded-xl border p-5"
                style={{ background: "var(--bg-surface)", borderColor: "var(--border-subtle)" }}
              >
                <div className="mb-2 flex items-center gap-2">
                  {f.type.includes("inventor") ? (
                    <Users className="h-4 w-4" style={{ color: "var(--brand-400)" }} />
                  ) : (
                    <FileText className="h-4 w-4" style={{ color: "var(--brand-400)" }} />
                  )}
                  <span className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>
                    {f.source}
                  </span>
                  {f.total_patents && (
                    <span
                      className="ml-auto rounded-full px-2 py-0.5 text-xs font-semibold"
                      style={{ background: "var(--brand-subtle)", color: "var(--brand-400)" }}
                    >
                      {f.total_patents} patents
                    </span>
                  )}
                </div>
                <p className="mb-3 text-sm" style={{ color: "var(--text-secondary)" }}>{f.description}</p>

                {f.sample_patents?.map((p, j) => (
                  <div key={j} className="mb-2 rounded-lg border px-3 py-2" style={{ borderColor: "var(--border-subtle)", background: "var(--bg-base)" }}>
                    <p className="text-xs font-mono" style={{ color: "var(--text-tertiary)" }}>US{p.patent_number}</p>
                    <p className="text-sm" style={{ color: "var(--text-primary)" }}>{p.title}</p>
                    <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>{p.date}</p>
                  </div>
                ))}

                {f.co_inventors && f.co_inventors.length > 0 && (
                  <p className="mt-2 text-xs" style={{ color: "var(--text-tertiary)" }}>
                    Co-inventors: {f.co_inventors.join(", ")}
                  </p>
                )}
                {f.assignee_companies && f.assignee_companies.length > 0 && (
                  <p className="mt-1 text-xs" style={{ color: "var(--text-tertiary)" }}>
                    Companies: {f.assignee_companies.join(", ")}
                  </p>
                )}
              </div>
            ))}

            {mutation.data.total_found === 0 && (
              <div
                className="rounded-xl border px-5 py-8 text-center"
                style={{ background: "var(--bg-surface)", borderColor: "var(--border-subtle)" }}
              >
                <p className="text-sm" style={{ color: "var(--text-tertiary)" }}>
                  No patents found for "{query}"
                </p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
