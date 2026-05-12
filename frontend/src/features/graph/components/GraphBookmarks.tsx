import { useState } from "react";
import { Bookmark } from "lucide-react";
import { Button } from "@/shared/components/Button";

interface BookmarkEntry {
  id: string;
  name: string;
  viewport: { x: number; y: number; zoom: number };
  filters: { types: string[]; minConfidence: number };
  layout: string;
}

interface GraphBookmarksProps {
  onSave: (name: string) => void;
  onLoad: (bookmark: BookmarkEntry) => void;
  bookmarks: BookmarkEntry[];
}

export function GraphBookmarks({ onSave, onLoad, bookmarks }: GraphBookmarksProps) {
  const [showSave, setShowSave] = useState(false);
  const [name, setName] = useState("");

  return (
    <div className="relative">
      <div className="flex items-center gap-1">
        <Button variant="ghost" size="sm" onClick={() => setShowSave(!showSave)}>
          <Bookmark className="h-3.5 w-3.5" />
        </Button>
        {bookmarks.map((b) => (
          <button
            key={b.id}
            onClick={() => onLoad(b)}
            className="rounded px-2 py-1 text-xs font-medium transition-colors hover:bg-bg-overlay"
            style={{ color: "var(--text-secondary)" }}
            title={b.name}
          >
            {b.name}
          </button>
        ))}
      </div>
      {showSave && (
        <div className="absolute top-full left-0 mt-1 z-20 rounded-md border p-2 flex gap-2" style={{ background: "var(--bg-surface)", borderColor: "var(--border-default)" }}>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Bookmark name..."
            className="rounded-md border px-2 py-1 text-xs"
            style={{ background: "var(--bg-elevated)", borderColor: "var(--border-default)", color: "var(--text-primary)" }}
          />
          <Button size="sm" onClick={() => { if (name) { onSave(name); setName(""); setShowSave(false); } }}>Save</Button>
        </div>
      )}
    </div>
  );
}
