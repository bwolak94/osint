/**
 * Natural Language Graph Query (Feature 4)
 * Parses a natural language query into investigation seed inputs + suggested scanners.
 */
import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Sparkles, ArrowRight, Loader2, X } from "lucide-react";
import { Badge } from "@/shared/components/Badge";
import { apiClient } from "@/shared/api/client";

interface NLQueryResult {
  seed_inputs: { type: string; value: string }[];
  suggested_scanners: string[];
  intent: string;
  confidence: number;
  raw_query: string;
}

interface NLQueryBarProps {
  onApply?: (seeds: { type: string; value: string }[], scanners: string[]) => void;
  placeholder?: string;
}

export function NLQueryBar({ onApply, placeholder = "Describe what you want to investigate…" }: NLQueryBarProps) {
  const [query, setQuery] = useState("");
  const [result, setResult] = useState<NLQueryResult | null>(null);

  const parseMutation = useMutation({
    mutationFn: async (q: string) => {
      const res = await apiClient.post<NLQueryResult>("/nl-query/parse", { query: q });
      return res.data;
    },
    onSuccess: (data) => setResult(data),
  });

  const handleParse = () => {
    if (!query.trim()) return;
    parseMutation.mutate(query);
  };

  const handleApply = () => {
    if (!result || !onApply) return;
    onApply(result.seed_inputs, result.suggested_scanners);
    setResult(null);
    setQuery("");
  };

  return (
    <div className="rounded-lg border p-3 space-y-2" style={{ borderColor: "var(--border-subtle)", background: "var(--bg-elevated)" }}>
      <div className="flex items-center gap-2">
        <Sparkles className="h-4 w-4 shrink-0" style={{ color: "var(--brand-400)" }} />
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleParse()}
          placeholder={placeholder}
          className="flex-1 bg-transparent text-sm outline-none"
          style={{ color: "var(--text-primary)" }}
        />
        {query && (
          <button onClick={() => { setQuery(""); setResult(null); }} className="rounded p-0.5 hover:bg-bg-overlay">
            <X className="h-3.5 w-3.5" style={{ color: "var(--text-tertiary)" }} />
          </button>
        )}
        <button
          onClick={handleParse}
          disabled={!query.trim() || parseMutation.isPending}
          className="flex items-center gap-1 rounded-md px-3 py-1.5 text-xs font-medium transition-colors disabled:opacity-50"
          style={{ background: "var(--brand-600)", color: "#fff" }}
        >
          {parseMutation.isPending ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <ArrowRight className="h-3.5 w-3.5" />
          )}
          Parse
        </button>
      </div>

      {result && (
        <div className="mt-2 rounded-md p-2 space-y-2" style={{ background: "var(--bg-surface)", border: "1px solid var(--border-subtle)" }}>
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold" style={{ color: "var(--text-primary)" }}>
              Intent: {result.intent}
            </span>
            <Badge variant={result.confidence >= 0.7 ? "success" : "warning"} size="sm">
              {Math.round(result.confidence * 100)}% confident
            </Badge>
          </div>

          {result.seed_inputs.length > 0 && (
            <div>
              <p className="text-[10px] font-medium mb-1" style={{ color: "var(--text-tertiary)" }}>EXTRACTED SEEDS</p>
              <div className="flex flex-wrap gap-1">
                {result.seed_inputs.map((s, i) => (
                  <div key={i} className="flex items-center gap-1 rounded-full px-2 py-0.5" style={{ background: "var(--bg-overlay)" }}>
                    <span className="text-[10px]" style={{ color: "var(--text-tertiary)" }}>{s.type}:</span>
                    <span className="text-xs font-mono" style={{ color: "var(--text-primary)" }}>{s.value}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {result.suggested_scanners.length > 0 && (
            <div>
              <p className="text-[10px] font-medium mb-1" style={{ color: "var(--text-tertiary)" }}>SUGGESTED SCANNERS</p>
              <div className="flex flex-wrap gap-1">
                {result.suggested_scanners.map((s) => (
                  <Badge key={s} variant="brand" size="sm">{s}</Badge>
                ))}
              </div>
            </div>
          )}

          {onApply && result.seed_inputs.length > 0 && (
            <div className="flex justify-end">
              <button
                onClick={handleApply}
                className="text-xs font-medium px-3 py-1.5 rounded-md transition-colors"
                style={{ background: "var(--brand-600)", color: "#fff" }}
              >
                Apply to Investigation
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
