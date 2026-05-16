import { useState } from "react";
import { Newspaper, Search, AlertTriangle, ExternalLink, TrendingDown } from "lucide-react";
import { useMutation } from "@tanstack/react-query";
import axios from "axios";

interface NewsResult {
  input: string;
  search_term: string;
  findings: Array<{
    type: string;
    severity: string;
    source: string;
    query: string;
    total_articles: number;
    negative_articles?: number;
    sample_headlines?: string[];
    sample_articles?: Array<{ title: string; url: string; date: string; domain: string }>;
    description: string;
  }>;
  total_found: number;
  total_negative_articles: number;
}

export function NewsMediaPage() {
  const [query, setQuery] = useState("");

  const mutation = useMutation({
    mutationFn: (q: string) =>
      axios
        .post<NewsResult>("/api/v1/scan", { input_value: q, scanner_name: "news_media" })
        .then((r) => r.data),
  });

  const sevColor = (s: string) => {
    if (s === "critical") return "#dc2626";
    if (s === "high") return "#ea580c";
    if (s === "medium") return "#ca8a04";
    return "#2563eb";
  };

  return (
    <div className="min-h-screen p-6" style={{ background: "var(--bg-base)" }}>
      <div className="mx-auto max-w-3xl">
        <div className="mb-8 flex items-center gap-3">
          <div
            className="flex h-10 w-10 items-center justify-center rounded-lg"
            style={{ background: "var(--brand-subtle)", border: "1px solid var(--brand-border)" }}
          >
            <Newspaper className="h-5 w-5" style={{ color: "var(--brand-400)" }} />
          </div>
          <div>
            <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>
              News & Media Monitor
            </h1>
            <p className="text-sm" style={{ color: "var(--text-tertiary)" }}>
              Search Google News, GDELT, and Bing News for mentions
            </p>
          </div>
        </div>

        <div className="mb-6 flex gap-3">
          <input
            type="text"
            placeholder="Person name, company, domain..."
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
            {mutation.data.total_negative_articles > 0 && (
              <div
                className="flex items-center gap-3 rounded-xl border px-4 py-3"
                style={{ borderColor: "#7f1d1d", background: "#450a0a" }}
              >
                <TrendingDown className="h-5 w-5 shrink-0" style={{ color: "#f87171" }} />
                <p className="text-sm" style={{ color: "#fca5a5" }}>
                  {mutation.data.total_negative_articles} negative news article(s) found — potential reputational risk
                </p>
              </div>
            )}

            {mutation.data.findings.map((f, i) => (
              <div
                key={i}
                className="rounded-xl border"
                style={{ background: "var(--bg-surface)", borderColor: "var(--border-subtle)" }}
              >
                <div className="flex items-center justify-between border-b px-5 py-3" style={{ borderColor: "var(--border-subtle)" }}>
                  <div className="flex items-center gap-2">
                    <span
                      className="rounded-full px-2 py-0.5 text-xs font-bold uppercase"
                      style={{ background: sevColor(f.severity) + "33", color: sevColor(f.severity) }}
                    >
                      {f.severity}
                    </span>
                    <span className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>
                      {f.source}
                    </span>
                  </div>
                  {f.negative_articles ? (
                    <span className="flex items-center gap-1 text-xs" style={{ color: "#f87171" }}>
                      <AlertTriangle className="h-3 w-3" />
                      {f.negative_articles} negative
                    </span>
                  ) : null}
                </div>
                <div className="px-5 py-4">
                  <p className="mb-3 text-sm" style={{ color: "var(--text-secondary)" }}>{f.description}</p>
                  {f.sample_headlines?.map((h, j) => (
                    <div key={j} className="mb-1 flex items-start gap-2">
                      <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full" style={{ background: "var(--text-tertiary)" }} />
                      <p className="text-sm" style={{ color: "var(--text-primary)" }}>{h}</p>
                    </div>
                  ))}
                  {f.sample_articles?.map((a, j) => (
                    <div key={j} className="mb-1 flex items-start gap-2">
                      <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full" style={{ background: "var(--text-tertiary)" }} />
                      <div>
                        <p className="text-sm" style={{ color: "var(--text-primary)" }}>{a.title}</p>
                        <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>
                          {a.domain} · {a.date?.slice(0, 10)}
                        </p>
                      </div>
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
                  No news coverage found for "{mutation.data.search_term}"
                </p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
