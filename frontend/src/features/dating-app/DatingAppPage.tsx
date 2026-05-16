import { useState } from "react";
import { Heart, Search, UserCheck } from "lucide-react";
import { useMutation } from "@tanstack/react-query";
import axios from "axios";

interface DatingResult {
  input: string;
  platforms_found: string[];
  findings: Array<{
    type: string;
    severity: string;
    source?: string;
    platform?: string;
    username?: string;
    display_name?: string;
    age?: string;
    description: string;
    url?: string;
    platforms_found?: string[];
  }>;
  total_found: number;
}

export function DatingAppPage() {
  const [query, setQuery] = useState("");

  const mutation = useMutation({
    mutationFn: (q: string) =>
      axios
        .post<DatingResult>("/api/v1/scan", { input_value: q, scanner_name: "dating_app" })
        .then((r) => r.data),
  });

  return (
    <div className="min-h-screen p-6" style={{ background: "var(--bg-base)" }}>
      <div className="mx-auto max-w-2xl">
        <div className="mb-8 flex items-center gap-3">
          <div
            className="flex h-10 w-10 items-center justify-center rounded-lg"
            style={{ background: "#500724", border: "1px solid #9f1239" }}
          >
            <Heart className="h-5 w-5" style={{ color: "#fb7185" }} />
          </div>
          <div>
            <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>
              Dating App Lookup
            </h1>
            <p className="text-sm" style={{ color: "var(--text-tertiary)" }}>
              Check Badoo, OkCupid, and PlentyOfFish for profile existence
            </p>
          </div>
        </div>

        <div
          className="mb-4 rounded-lg border px-4 py-3"
          style={{ borderColor: "#713f12", background: "#422006" }}
        >
          <p className="text-xs" style={{ color: "#fde68a" }}>
            For authorized OSINT investigations only. Ensure you have legal basis before searching.
          </p>
        </div>

        <div className="mb-6 flex gap-3">
          <input
            type="text"
            placeholder="Email address, username, or phone number..."
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
          <div className="space-y-3">
            {mutation.data.platforms_found.length > 0 && (
              <div
                className="rounded-xl border px-5 py-4"
                style={{ borderColor: "#9f1239", background: "#500724" }}
              >
                <p className="mb-2 text-sm font-semibold" style={{ color: "#fda4af" }}>
                  Profiles found on:
                </p>
                <div className="flex flex-wrap gap-2">
                  {mutation.data.platforms_found.map((p) => (
                    <span
                      key={p}
                      className="rounded-full px-3 py-1 text-xs font-semibold"
                      style={{ background: "#9f1239", color: "#fecdd3" }}
                    >
                      {p}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {mutation.data.findings
              .filter((f) => f.type === "dating_profile_found")
              .map((f, i) => (
                <div
                  key={i}
                  className="rounded-xl border p-5"
                  style={{ background: "var(--bg-surface)", borderColor: "var(--border-subtle)" }}
                >
                  <div className="flex items-center gap-2 mb-2">
                    <UserCheck className="h-4 w-4" style={{ color: "#fb7185" }} />
                    <span className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
                      {f.platform}
                    </span>
                    {f.display_name && (
                      <span className="text-sm" style={{ color: "var(--text-secondary)" }}>
                        — {f.display_name}
                        {f.age && `, ${f.age}`}
                      </span>
                    )}
                  </div>
                  <p className="text-sm" style={{ color: "var(--text-secondary)" }}>{f.description}</p>
                  {f.url && (
                    <a
                      href={f.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="mt-2 inline-block text-xs hover:underline"
                      style={{ color: "var(--brand-400)" }}
                    >
                      View profile →
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
                  No dating app profiles found for "{query}"
                </p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
