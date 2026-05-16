import { useState } from "react";
import { GraduationCap, Search, BookOpen, Users, Award } from "lucide-react";
import { useMutation } from "@tanstack/react-query";
import axios from "axios";

interface AcademicResult {
  input: string;
  findings: Array<{
    type: string;
    severity: string;
    source: string;
    description: string;
    full_name?: string;
    orcid_id?: string;
    publications_count?: number;
    paper_count?: number;
    citation_count?: number;
    h_index?: number;
    affiliations?: string[];
    total_papers?: number;
    sample_titles?: string[];
    profiles?: Array<{ orcid_id: string; name: string }>;
    url?: string;
  }>;
  total_found: number;
}

export function AcademicIntelPage() {
  const [query, setQuery] = useState("");

  const mutation = useMutation({
    mutationFn: (q: string) =>
      axios
        .post<AcademicResult>("/api/v1/scan", { input_value: q, scanner_name: "academic" })
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
            <GraduationCap className="h-5 w-5" style={{ color: "var(--brand-400)" }} />
          </div>
          <div>
            <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>
              Academic Intelligence
            </h1>
            <p className="text-sm" style={{ color: "var(--text-tertiary)" }}>
              Search ORCID, Semantic Scholar, and arXiv for researcher profiles
            </p>
          </div>
        </div>

        <div className="mb-6 flex gap-3">
          <input
            type="text"
            placeholder="Researcher name, email, or ORCID iD..."
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
                  {f.type === "semantic_scholar_author" ? (
                    <Users className="h-4 w-4" style={{ color: "var(--brand-400)" }} />
                  ) : f.type.includes("arxiv") ? (
                    <BookOpen className="h-4 w-4" style={{ color: "var(--brand-400)" }} />
                  ) : (
                    <Award className="h-4 w-4" style={{ color: "var(--brand-400)" }} />
                  )}
                  <span className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>
                    {f.source}
                  </span>
                </div>
                <p className="mb-3 text-sm" style={{ color: "var(--text-secondary)" }}>{f.description}</p>

                {f.paper_count !== undefined && (
                  <div className="flex gap-4">
                    <div>
                      <span className="text-lg font-bold" style={{ color: "var(--text-primary)" }}>{f.paper_count}</span>
                      <span className="ml-1 text-xs" style={{ color: "var(--text-tertiary)" }}>papers</span>
                    </div>
                    <div>
                      <span className="text-lg font-bold" style={{ color: "var(--text-primary)" }}>{f.citation_count ?? 0}</span>
                      <span className="ml-1 text-xs" style={{ color: "var(--text-tertiary)" }}>citations</span>
                    </div>
                    <div>
                      <span className="text-lg font-bold" style={{ color: "var(--text-primary)" }}>h{f.h_index ?? 0}</span>
                      <span className="ml-1 text-xs" style={{ color: "var(--text-tertiary)" }}>index</span>
                    </div>
                  </div>
                )}

                {f.affiliations && f.affiliations.length > 0 && (
                  <p className="mt-2 text-xs" style={{ color: "var(--text-tertiary)" }}>
                    {f.affiliations.join(", ")}
                  </p>
                )}

                {f.sample_titles?.map((t, j) => (
                  <div key={j} className="mt-1 flex items-start gap-2">
                    <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full" style={{ background: "var(--text-tertiary)" }} />
                    <p className="text-xs" style={{ color: "var(--text-secondary)" }}>{t}</p>
                  </div>
                ))}

                {f.url && (
                  <a
                    href={f.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="mt-3 inline-block text-xs hover:underline"
                    style={{ color: "var(--brand-400)" }}
                  >
                    View Profile →
                  </a>
                )}
              </div>
            ))}

            {mutation.data.total_found === 0 && (
              <div
                className="rounded-xl border px-5 py-8 text-center"
                style={{ background: "var(--bg-surface)", borderColor: "var(--border-subtle)" }}
              >
                <p className="text-sm" style={{ color: "var(--text-tertiary)" }}>
                  No academic profiles found for "{query}"
                </p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
