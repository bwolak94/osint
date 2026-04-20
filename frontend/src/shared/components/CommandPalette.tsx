import { useState, useEffect, useRef, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { Search, FileSearch, Radar, Settings, CreditCard, Shield, LayoutDashboard, Scan, Loader2 } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { apiClient } from "@/shared/api/client";

interface CommandItem {
  id: string;
  label: string;
  icon: typeof Search;
  action: () => void;
  category: string;
}

interface ApiSearchResult {
  type: string;
  id: string;
  title: string;
  snippet: string;
  investigation_id?: string | null;
}

export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [searchResults, setSearchResults] = useState<ApiSearchResult[]>([]);
  const [searching, setSearching] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const navigate = useNavigate();

  const items: CommandItem[] = [
    { id: "dashboard", label: "Go to Dashboard", icon: LayoutDashboard, action: () => navigate("/dashboard"), category: "Navigation" },
    { id: "investigations", label: "Go to Investigations", icon: FileSearch, action: () => navigate("/investigations"), category: "Navigation" },
    { id: "scanners", label: "Go to Scanners", icon: Radar, action: () => navigate("/scanners"), category: "Navigation" },
    { id: "settings", label: "Go to Settings", icon: Settings, action: () => navigate("/settings"), category: "Navigation" },
    { id: "billing", label: "Go to Billing", icon: CreditCard, action: () => navigate("/billing"), category: "Navigation" },
    { id: "admin", label: "Go to Admin Panel", icon: Shield, action: () => navigate("/admin"), category: "Navigation" },
    { id: "new-investigation", label: "Create New Investigation", icon: Search, action: () => navigate("/investigations"), category: "Actions" },
  ];

  const filtered = items.filter((item) =>
    item.label.toLowerCase().includes(query.toLowerCase()),
  );

  // Build combined list: command items + search results
  const searchItems: CommandItem[] = searchResults.map((r) => ({
    id: `search-${r.type}-${r.id}`,
    label: r.title,
    icon: r.type === "investigation" ? FileSearch : Scan,
    action: () => {
      if (r.type === "investigation") {
        navigate(`/investigations/${r.id}`);
      } else if (r.investigation_id) {
        navigate(`/investigations/${r.investigation_id}`);
      }
    },
    category: r.type === "investigation" ? "Investigations" : "Scan Results",
  }));

  const allItems = [...filtered, ...searchItems];

  // Debounced search against API
  const doSearch = useCallback(async (q: string) => {
    if (q.length < 2) {
      setSearchResults([]);
      setSearching(false);
      return;
    }
    setSearching(true);
    try {
      const res = await apiClient.get("/search", { params: { q } });
      setSearchResults(res.data?.results ?? []);
    } catch {
      setSearchResults([]);
    } finally {
      setSearching(false);
    }
  }, []);

  const handleQueryChange = (value: string) => {
    setQuery(value);
    setSelectedIndex(0);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => doSearch(value), 300);
  };

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setOpen((o) => !o);
        setQuery("");
        setSelectedIndex(0);
        setSearchResults([]);
      }
      if (e.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  useEffect(() => {
    if (open) inputRef.current?.focus();
  }, [open]);

  const execute = (item: CommandItem) => {
    item.action();
    setOpen(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") { e.preventDefault(); setSelectedIndex((i) => Math.min(i + 1, allItems.length - 1)); }
    if (e.key === "ArrowUp") { e.preventDefault(); setSelectedIndex((i) => Math.max(i - 1, 0)); }
    if (e.key === "Enter" && allItems[selectedIndex]) { execute(allItems[selectedIndex]); }
  };

  return (
    <AnimatePresence>
      {open && (
        <div className="fixed inset-0 z-50 flex items-start justify-center pt-[20vh]" onClick={() => setOpen(false)}>
          <div className="fixed inset-0 bg-black/50 backdrop-blur-sm" />
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: -10 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: -10 }}
            transition={{ duration: 0.15 }}
            className="relative z-10 w-full max-w-lg overflow-hidden rounded-xl border shadow-2xl"
            style={{ background: "var(--bg-surface)", borderColor: "var(--border-default)" }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center gap-3 border-b px-4 py-3" style={{ borderColor: "var(--border-subtle)" }}>
              <Search className="h-4 w-4 shrink-0" style={{ color: "var(--text-tertiary)" }} />
              <input
                ref={inputRef}
                value={query}
                onChange={(e) => handleQueryChange(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Type a command or search..."
                className="flex-1 bg-transparent text-sm outline-none"
                style={{ color: "var(--text-primary)" }}
              />
              {searching && <Loader2 className="h-4 w-4 animate-spin" style={{ color: "var(--text-tertiary)" }} />}
              <kbd className="rounded border px-1.5 py-0.5 text-[10px] font-medium" style={{ borderColor: "var(--border-default)", color: "var(--text-tertiary)" }}>ESC</kbd>
            </div>
            <div className="max-h-72 overflow-y-auto py-2">
              {allItems.length === 0 ? (
                <p className="px-4 py-6 text-center text-sm" style={{ color: "var(--text-tertiary)" }}>No results found</p>
              ) : (
                <>
                  {/* Command results */}
                  {filtered.length > 0 && (
                    <>
                      <p className="px-4 py-1 text-[10px] font-medium uppercase tracking-wider" style={{ color: "var(--text-tertiary)" }}>Commands</p>
                      {filtered.map((item, i) => (
                        <button
                          key={item.id}
                          onClick={() => execute(item)}
                          className={`flex w-full items-center gap-3 px-4 py-2 text-sm transition-colors ${
                            i === selectedIndex ? "bg-bg-overlay" : ""
                          }`}
                          style={{ color: "var(--text-primary)" }}
                          onMouseEnter={() => setSelectedIndex(i)}
                        >
                          <item.icon className="h-4 w-4 shrink-0" style={{ color: "var(--text-tertiary)" }} />
                          <span className="flex-1 text-left">{item.label}</span>
                          <span className="text-xs" style={{ color: "var(--text-tertiary)" }}>{item.category}</span>
                        </button>
                      ))}
                    </>
                  )}
                  {/* API search results */}
                  {searchItems.length > 0 && (
                    <>
                      <p className="px-4 py-1 text-[10px] font-medium uppercase tracking-wider" style={{ color: "var(--text-tertiary)" }}>Search Results</p>
                      {searchItems.map((item, i) => {
                        const globalIdx = filtered.length + i;
                        const apiResult = searchResults[i];
                        return (
                          <button
                            key={item.id}
                            onClick={() => execute(item)}
                            className={`flex w-full items-center gap-3 px-4 py-2 text-sm transition-colors ${
                              globalIdx === selectedIndex ? "bg-bg-overlay" : ""
                            }`}
                            style={{ color: "var(--text-primary)" }}
                            onMouseEnter={() => setSelectedIndex(globalIdx)}
                          >
                            <item.icon className="h-4 w-4 shrink-0" style={{ color: "var(--text-tertiary)" }} />
                            <div className="flex-1 text-left">
                              <span>{item.label}</span>
                              {apiResult?.snippet && (
                                <p className="text-xs truncate" style={{ color: "var(--text-tertiary)" }}>{apiResult.snippet}</p>
                              )}
                            </div>
                            <span className="text-xs" style={{ color: "var(--text-tertiary)" }}>{item.category}</span>
                          </button>
                        );
                      })}
                    </>
                  )}
                </>
              )}
            </div>
            <div className="border-t px-4 py-2 text-xs" style={{ borderColor: "var(--border-subtle)", color: "var(--text-tertiary)" }}>
              <kbd className="mr-1 rounded border px-1 py-0.5" style={{ borderColor: "var(--border-default)" }}>&#8593;&#8595;</kbd> navigate
              <kbd className="mx-1 rounded border px-1 py-0.5" style={{ borderColor: "var(--border-default)" }}>&#8629;</kbd> select
              <kbd className="mx-1 rounded border px-1 py-0.5" style={{ borderColor: "var(--border-default)" }}>esc</kbd> close
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}
