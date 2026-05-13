import { useState } from "react";
import { Search, Loader2 } from "lucide-react";

type QueryType = "username" | "name";

interface Props {
  onSearch: (query: string, queryType: QueryType) => void;
  isLoading: boolean;
}

const QUERY_TYPES: { value: QueryType; label: string }[] = [
  { value: "username", label: "Username" },
  { value: "name", label: "Full Name" },
];

export function LinkedInSearchForm({ onSearch, isLoading }: Props) {
  const [query, setQuery] = useState("");
  const [queryType, setQueryType] = useState<QueryType>("username");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (query.trim()) onSearch(query.trim(), queryType);
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="flex gap-2">
        {QUERY_TYPES.map((t) => (
          <button
            key={t.value}
            type="button"
            onClick={() => setQueryType(t.value)}
            className={`rounded-full px-4 py-1.5 text-sm font-medium transition-colors ${
              queryType === t.value
                ? "bg-brand-500 text-white"
                : "bg-bg-overlay text-text-secondary hover:text-text-primary"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="flex gap-3">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={queryType === "username" ? "e.g. john-doe-123" : "e.g. John Doe"}
          className="flex-1 rounded-md border px-3 py-2 text-sm"
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
          Search
        </button>
      </div>
    </form>
  );
}
