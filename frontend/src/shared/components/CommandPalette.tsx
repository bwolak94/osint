import { useState, useEffect, useRef, useCallback, useMemo } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import {
  Search, FileSearch, Radar, Settings, Shield, LayoutDashboard, Scan, Loader2,
  Flag, GitBranch, Sparkles, BookOpen, Bell, ScanSearch, FileText, Mail, Cpu,
  Globe, Cloud, Wifi, AlertTriangle, Package, KeyRound, Users, UserSearch,
  Network, MapPin, BarChart3, ShieldAlert, ClipboardCheck, FileOutput, Scale,
  Plug, ShieldCheck, Clock, X,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { apiClient } from "@/shared/api/client";

const ICON_MAP: Record<string, React.ElementType> = {
  LayoutDashboard, Search, Flag, GitBranch, Sparkles, Radar, BookOpen, Bell,
  Shield, ScanSearch, FileText, Mail, Cpu, Globe, Cloud, Wifi, AlertTriangle,
  Package, KeyRound, Users, UserSearch, Network, MapPin, BarChart3, ShieldAlert,
  ClipboardCheck, FileOutput, Scale, Plug, Settings, ShieldCheck, FileSearch, Scan,
};

interface PageCommand {
  id: string;
  label: string;
  path: string;
  iconName: string;
}

interface CommandItem {
  id: string;
  label: string;
  icon: React.ElementType;
  action: () => void;
  category: string;
  path?: string;
}

interface ApiSearchResult {
  type: string;
  id: string;
  title: string;
  snippet: string;
  investigation_id?: string | null;
}

interface RecentPage {
  label: string;
  path: string;
  iconName: string;
  visitedAt: number;
}

const ALL_COMMANDS: PageCommand[] = [
  { id: "dashboard", label: "Dashboard", path: "/dashboard", iconName: "LayoutDashboard" },
  { id: "investigations", label: "Investigations", path: "/investigations", iconName: "Search" },
  { id: "campaigns", label: "Campaigns", path: "/campaigns", iconName: "Flag" },
  { id: "investigation-diff", label: "Diff & Merge", path: "/investigation-diff", iconName: "GitBranch" },
  { id: "hub", label: "AI Hub", path: "/hub", iconName: "Sparkles" },
  { id: "scanners", label: "Scanners", path: "/scanners", iconName: "Radar" },
  { id: "playbooks", label: "Playbooks", path: "/playbooks", iconName: "BookOpen" },
  { id: "watchlist", label: "Watchlist", path: "/watchlist", iconName: "Bell" },
  { id: "threat-actors", label: "Threat Actors", path: "/threat-actors", iconName: "Shield" },
  { id: "image-checker", label: "Image Checker", path: "/image-checker", iconName: "ScanSearch" },
  { id: "doc-metadata", label: "Doc Metadata", path: "/doc-metadata", iconName: "FileText" },
  { id: "email-headers", label: "Email Headers", path: "/email-headers", iconName: "Mail" },
  { id: "mac-lookup", label: "MAC Lookup", path: "/mac-lookup", iconName: "Cpu" },
  { id: "domain-permutation", label: "Domain Permutation", path: "/domain-permutation", iconName: "Globe" },
  { id: "cloud-exposure", label: "Cloud Exposure", path: "/cloud-exposure", iconName: "Cloud" },
  { id: "wigle", label: "WiGLE", path: "/wigle", iconName: "Wifi" },
  { id: "stealer-logs", label: "Stealer Logs", path: "/stealer-logs", iconName: "AlertTriangle" },
  { id: "supply-chain", label: "Supply Chain", path: "/supply-chain", iconName: "Package" },
  { id: "credential-intel", label: "Credential Intel", path: "/credential-intel", iconName: "KeyRound" },
  { id: "fediverse", label: "Fediverse", path: "/fediverse", iconName: "Users" },
  { id: "socmint", label: "SOCMINT", path: "/socmint", iconName: "UserSearch" },
  { id: "tech-recon", label: "Tech Recon", path: "/tech-recon", iconName: "Network" },
  { id: "imint", label: "IMINT / GEOINT", path: "/imint", iconName: "MapPin" },
  { id: "pentest-dashboard", label: "Pentest Dashboard", path: "/pentest/dashboard", iconName: "BarChart3" },
  { id: "pentest-findings", label: "Findings", path: "/pentest/findings", iconName: "ShieldAlert" },
  { id: "pentest-compliance", label: "Compliance", path: "/pentest/compliance", iconName: "ClipboardCheck" },
  { id: "report-builder", label: "Report Builder", path: "/report-builder", iconName: "FileOutput" },
  { id: "gdpr", label: "GDPR Requests", path: "/gdpr", iconName: "Scale" },
  { id: "maltego", label: "Maltego", path: "/maltego", iconName: "Plug" },
  { id: "settings", label: "Settings", path: "/settings", iconName: "Settings" },
  { id: "admin", label: "Admin", path: "/admin", iconName: "ShieldCheck" },
];

const RECENT_PAGES_KEY = "osint_recent_pages";
const MAX_RECENT = 5;

function getRecentPages(): RecentPage[] {
  try {
    const raw = localStorage.getItem(RECENT_PAGES_KEY);
    return raw ? (JSON.parse(raw) as RecentPage[]) : [];
  } catch {
    return [];
  }
}

function recordRecentPage(page: RecentPage): void {
  try {
    const existing = getRecentPages().filter((p) => p.path !== page.path);
    const updated = [{ ...page, visitedAt: Date.now() }, ...existing].slice(0, MAX_RECENT);
    localStorage.setItem(RECENT_PAGES_KEY, JSON.stringify(updated));
  } catch {
    // Silently fail if localStorage is unavailable
  }
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
  const location = useLocation();

  // Record the current page as recently visited when location changes
  useEffect(() => {
    const matched = ALL_COMMANDS.find(
      (cmd) => cmd.path === location.pathname || `/${cmd.path}` === location.pathname,
    );
    if (matched) {
      recordRecentPage({
        label: matched.label,
        path: matched.path,
        iconName: matched.iconName,
        visitedAt: Date.now(),
      });
    }
  }, [location.pathname]);

  const openPalette = useCallback(() => {
    setOpen(true);
    setQuery("");
    setSelectedIndex(0);
    setSearchResults([]);
  }, []);

  const closePalette = useCallback(() => {
    setOpen(false);
  }, []);

  // Build page commands as CommandItems
  const pageCommands: CommandItem[] = useMemo(
    () =>
      ALL_COMMANDS.map((cmd) => ({
        id: `page-${cmd.path}`,
        label: cmd.label,
        icon: ICON_MAP[cmd.iconName] ?? Search,
        action: () => navigate(cmd.path),
        category: "Pages",
        path: cmd.path,
      })),
    [navigate],
  );

  // Recent pages
  const recentPages: CommandItem[] = useMemo(() => {
    if (!open) return [];
    return getRecentPages().map((rp) => ({
      id: `recent-${rp.path}`,
      label: rp.label,
      icon: ICON_MAP[rp.iconName] ?? Search,
      action: () => navigate(rp.path),
      category: "Recent",
      path: rp.path,
    }));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, navigate]);

  // Filter page commands by query
  const filteredPages = useMemo(() => {
    if (!query) return pageCommands;
    const lower = query.toLowerCase();
    return pageCommands.filter((item) => item.label.toLowerCase().includes(lower));
  }, [query, pageCommands]);

  // API search results as CommandItems
  const searchItems: CommandItem[] = useMemo(
    () =>
      searchResults.map((r) => ({
        id: `search-${r.type}-${r.id}`,
        label: r.title,
        icon: r.type === "investigation" ? FileSearch : Scan,
        action: () => {
          if (r.type === "investigation") navigate(`/investigations/${r.id}`);
          else if (r.investigation_id) navigate(`/investigations/${r.investigation_id}`);
        },
        category: r.type === "investigation" ? "Investigations" : "Scan Results",
      })),
    [searchResults, navigate],
  );

  // Build section-aware flat list for keyboard navigation
  // When no query: show Recent first (if any), then all Pages
  // When query: show filtered Pages, then API search results
  const sections = useMemo(() => {
    if (!query) {
      const sects: Array<{ title: string; items: CommandItem[] }> = [];
      if (recentPages.length > 0) sects.push({ title: "Recent", items: recentPages });
      sects.push({ title: "Pages", items: filteredPages });
      return sects;
    }
    const sects: Array<{ title: string; items: CommandItem[] }> = [];
    if (filteredPages.length > 0) sects.push({ title: "Pages", items: filteredPages });
    if (searchItems.length > 0) sects.push({ title: "Search Results", items: searchItems });
    return sects;
  }, [query, recentPages, filteredPages, searchItems]);

  const allItems = useMemo(
    () => sections.flatMap((s) => s.items),
    [sections],
  );

  // Debounced API search
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

  // Global keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Cmd/Ctrl+K
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setOpen((prev) => {
          if (!prev) openPalette();
          else closePalette();
          return !prev;
        });
        return;
      }

      // "/" when not in an input/textarea/contenteditable
      if (e.key === "/" && !open) {
        const target = e.target as HTMLElement;
        const tag = target.tagName.toLowerCase();
        const isEditable =
          tag === "input" || tag === "textarea" || target.isContentEditable;
        if (!isEditable) {
          e.preventDefault();
          openPalette();
        }
        return;
      }

      if (e.key === "Escape" && open) {
        closePalette();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [open, openPalette, closePalette]);

  useEffect(() => {
    if (open) inputRef.current?.focus();
  }, [open]);

  const execute = useCallback(
    (item: CommandItem) => {
      item.action();
      closePalette();
    },
    [closePalette],
  );

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setSelectedIndex((i) => Math.min(i + 1, allItems.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setSelectedIndex((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter" && allItems[selectedIndex]) {
      execute(allItems[selectedIndex]);
    }
  };

  // Track absolute index across sections for highlight
  let runningIndex = 0;

  return (
    <AnimatePresence>
      {open && (
        <div
          className="fixed inset-0 z-50 flex items-start justify-center pt-[20vh]"
          onClick={closePalette}
        >
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
            {/* Search input */}
            <div
              className="flex items-center gap-3 border-b px-4 py-3"
              style={{ borderColor: "var(--border-subtle)" }}
            >
              <Search className="h-4 w-4 shrink-0" style={{ color: "var(--text-tertiary)" }} />
              <input
                ref={inputRef}
                value={query}
                onChange={(e) => handleQueryChange(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Search pages or type a command..."
                className="flex-1 bg-transparent text-sm outline-none"
                style={{ color: "var(--text-primary)" }}
              />
              {searching && (
                <Loader2 className="h-4 w-4 animate-spin" style={{ color: "var(--text-tertiary)" }} />
              )}
              {query && (
                <button
                  onClick={() => { setQuery(""); setSearchResults([]); setSelectedIndex(0); }}
                  className="rounded p-0.5 transition-colors hover:bg-bg-overlay"
                >
                  <X className="h-3.5 w-3.5" style={{ color: "var(--text-tertiary)" }} />
                </button>
              )}
              <kbd
                className="rounded border px-1.5 py-0.5 text-[10px] font-medium"
                style={{ borderColor: "var(--border-default)", color: "var(--text-tertiary)" }}
              >
                ESC
              </kbd>
            </div>

            {/* Results */}
            <div className="max-h-80 overflow-y-auto py-2">
              {allItems.length === 0 ? (
                <p className="px-4 py-6 text-center text-sm" style={{ color: "var(--text-tertiary)" }}>
                  No results found
                </p>
              ) : (
                sections.map((section) => {
                  const sectionStart = runningIndex;
                  runningIndex += section.items.length;

                  return (
                    <div key={section.title}>
                      <div className="flex items-center gap-2 px-4 py-1.5">
                        {section.title === "Recent" && (
                          <Clock className="h-3 w-3" style={{ color: "var(--text-tertiary)" }} />
                        )}
                        <p
                          className="text-[10px] font-medium uppercase tracking-wider"
                          style={{ color: "var(--text-tertiary)" }}
                        >
                          {section.title}
                        </p>
                      </div>
                      {section.items.map((item, i) => {
                        const globalIdx = sectionStart + i;
                        const isSelected = globalIdx === selectedIndex;
                        return (
                          <button
                            key={item.id}
                            onClick={() => execute(item)}
                            className="flex w-full items-center gap-3 px-4 py-2 text-sm transition-colors"
                            style={{
                              color: "var(--text-primary)",
                              background: isSelected ? "var(--bg-overlay)" : "transparent",
                            }}
                            onMouseEnter={() => setSelectedIndex(globalIdx)}
                          >
                            <span
                              className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md border"
                              style={{
                                borderColor: isSelected ? "var(--brand-500)" : "var(--border-subtle)",
                                background: isSelected ? "var(--brand-900)" : "var(--bg-elevated)",
                              }}
                            >
                              <item.icon
                                className="h-3.5 w-3.5"
                                style={{ color: isSelected ? "var(--brand-400)" : "var(--text-tertiary)" }}
                              />
                            </span>
                            <span className="flex-1 text-left">{item.label}</span>
                            <span className="text-xs" style={{ color: "var(--text-tertiary)" }}>
                              {item.category}
                            </span>
                          </button>
                        );
                      })}
                    </div>
                  );
                })
              )}
            </div>

            {/* Footer hints */}
            <div
              className="border-t px-4 py-2 text-xs flex items-center gap-3"
              style={{ borderColor: "var(--border-subtle)", color: "var(--text-tertiary)" }}
            >
              <span>
                <kbd
                  className="mr-1 rounded border px-1 py-0.5"
                  style={{ borderColor: "var(--border-default)" }}
                >
                  &#8593;&#8595;
                </kbd>
                navigate
              </span>
              <span>
                <kbd
                  className="mr-1 rounded border px-1 py-0.5"
                  style={{ borderColor: "var(--border-default)" }}
                >
                  &#8629;
                </kbd>
                select
              </span>
              <span>
                <kbd
                  className="mr-1 rounded border px-1 py-0.5"
                  style={{ borderColor: "var(--border-default)" }}
                >
                  /
                </kbd>
                open
              </span>
              <span>
                <kbd
                  className="mr-1 rounded border px-1 py-0.5"
                  style={{ borderColor: "var(--border-default)" }}
                >
                  esc
                </kbd>
                close
              </span>
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}
