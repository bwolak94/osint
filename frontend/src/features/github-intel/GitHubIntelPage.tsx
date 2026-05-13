import { useState } from "react";
import { Github } from "lucide-react";
import { GitHubSearchForm } from "./components/GitHubSearchForm";
import { GitHubResults } from "./components/GitHubResults";
import { GitHubHistory } from "./components/GitHubHistory";
import { useScanGitHubIntel } from "./hooks";
import type { GitHubIntelScan } from "./types";

export function GitHubIntelPage() {
  const [currentScan, setCurrentScan] = useState<GitHubIntelScan | null>(null);
  const scanMutation = useScanGitHubIntel();

  const handleSearch = (query: string, queryType: "username" | "name" | "email") => {
    scanMutation.mutate(
      { query, query_type: queryType },
      { onSuccess: (data) => setCurrentScan(data) }
    );
  };

  return (
    <div className="flex flex-1 flex-col gap-6 p-6">
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-lg" style={{ background: "var(--bg-overlay)" }}>
          <Github className="h-5 w-5" style={{ color: "var(--brand-500)" }} />
        </div>
        <div>
          <h1 className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>
            GitHub Intel
          </h1>
          <p className="text-sm" style={{ color: "var(--text-tertiary)" }}>
            Profile lookup, repo analysis, and commit email extraction via GitHub API
          </p>
        </div>
      </div>

      <div className="rounded-xl border p-5" style={{ background: "var(--bg-surface)", borderColor: "var(--border-subtle)" }}>
        <GitHubSearchForm onSearch={handleSearch} isLoading={scanMutation.isPending} />
      </div>

      {scanMutation.isError && (
        <div className="rounded-md border px-4 py-3 text-sm" style={{ borderColor: "var(--danger-500)", color: "var(--danger-500)", background: "var(--bg-overlay)" }}>
          Search failed. Check the username or try again.
        </div>
      )}

      {currentScan && (
        <div className="rounded-xl border p-5" style={{ background: "var(--bg-surface)", borderColor: "var(--border-subtle)" }}>
          <h2 className="mb-4 text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Results</h2>
          <GitHubResults scan={currentScan} />
        </div>
      )}

      <div className="rounded-xl border p-5" style={{ background: "var(--bg-surface)", borderColor: "var(--border-subtle)" }}>
        <h2 className="mb-3 text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Scan History</h2>
        <GitHubHistory onSelect={setCurrentScan} />
      </div>
    </div>
  );
}
