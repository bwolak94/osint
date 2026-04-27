import {
  useState,
  useEffect,
  useCallback,
  useMemo,
  useRef,
  type ChangeEvent,
} from "react";
import { Filter, X, ChevronDown, Check, Bookmark, BookmarkCheck } from "lucide-react";
import { Button } from "@/shared/components/Button";
import { Badge } from "@/shared/components/Badge";
import { Input } from "@/shared/components/Input";
import type { NodeType, OsintNodeData } from "../types";

export interface GraphFilterState {
  nodeTypes: string[];
  minConfidence: number;
  scanners: string[];
  searchText: string;
  dateRange: { from: Date | null; to: Date | null };
}

interface GraphFilterBarProps {
  nodes: OsintNodeData[];
  onFilterChange: (hiddenNodeIds: Set<string>) => void;
}

const ALL_NODE_TYPES: NodeType[] = [
  "person", "company", "email", "phone", "username", "ip", "domain",
  "service", "location", "vulnerability", "breach", "subdomain",
  "port", "certificate", "asn", "url", "hash", "address",
  "bank_account", "regon", "nip", "online_service", "input",
];

const DEFAULT_FILTER: GraphFilterState = {
  nodeTypes: [],
  minConfidence: 0,
  scanners: [],
  searchText: "",
  dateRange: { from: null, to: null },
};

const PRESETS_STORAGE_KEY = "graph_filter_presets";

interface FilterPreset {
  name: string;
  filters: Omit<GraphFilterState, "dateRange">;
}

function loadPresets(): FilterPreset[] {
  try {
    const raw = localStorage.getItem(PRESETS_STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function savePresets(presets: FilterPreset[]): void {
  try {
    localStorage.setItem(PRESETS_STORAGE_KEY, JSON.stringify(presets));
  } catch {
    // Storage quota exceeded — silently ignore
  }
}

function countActiveFilters(state: GraphFilterState): number {
  let count = 0;
  if (state.nodeTypes.length > 0) count++;
  if (state.minConfidence > 0) count++;
  if (state.scanners.length > 0) count++;
  if (state.searchText.trim()) count++;
  if (state.dateRange.from || state.dateRange.to) count++;
  return count;
}

export function GraphFilterBar({ nodes, onFilterChange }: GraphFilterBarProps) {
  const [filters, setFilters] = useState<GraphFilterState>(DEFAULT_FILTER);
  const [showTypeDropdown, setShowTypeDropdown] = useState(false);
  const [showScannerDropdown, setShowScannerDropdown] = useState(false);
  const [visible, setVisible] = useState(false);
  const [presets, setPresets] = useState<FilterPreset[]>(loadPresets);
  const [showPresetsDropdown, setShowPresetsDropdown] = useState(false);
  const [newPresetName, setNewPresetName] = useState("");
  const presetsDropdownRef = useRef<HTMLDivElement>(null);

  const typeDropdownRef = useRef<HTMLDivElement>(null);
  const scannerDropdownRef = useRef<HTMLDivElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const saveCurrentAsPreset = useCallback(() => {
    const name = newPresetName.trim();
    if (!name) return;
    const preset: FilterPreset = {
      name,
      filters: { nodeTypes: filters.nodeTypes, minConfidence: filters.minConfidence, scanners: filters.scanners, searchText: filters.searchText },
    };
    const updated = [...presets.filter((p) => p.name !== name), preset];
    setPresets(updated);
    savePresets(updated);
    setNewPresetName("");
    setShowPresetsDropdown(false);
  }, [filters, newPresetName, presets]);

  const loadPreset = useCallback((preset: FilterPreset) => {
    setFilters((prev) => ({ ...prev, ...preset.filters }));
    setShowPresetsDropdown(false);
  }, []);

  const deletePreset = useCallback((name: string) => {
    const updated = presets.filter((p) => p.name !== name);
    setPresets(updated);
    savePresets(updated);
  }, [presets]);

  const availableScanners = useMemo(() => {
    const scannerSet = new Set<string>();
    for (const node of nodes) {
      for (const source of node.sources) {
        scannerSet.add(source);
      }
    }
    return Array.from(scannerSet).sort();
  }, [nodes]);

  // Compute hidden node IDs when filters change
  const applyFilters = useCallback(
    (state: GraphFilterState) => {
      const hidden = new Set<string>();
      for (const node of nodes) {
        const typeMatch =
          state.nodeTypes.length === 0 || state.nodeTypes.includes(node.type);
        const confidenceMatch = node.confidence >= state.minConfidence;
        const scannerMatch =
          state.scanners.length === 0 ||
          node.sources.some((s) => state.scanners.includes(s));
        const textMatch =
          !state.searchText.trim() ||
          node.label.toLowerCase().includes(state.searchText.toLowerCase());

        if (!typeMatch || !confidenceMatch || !scannerMatch || !textMatch) {
          hidden.add(node.id);
        }
      }
      onFilterChange(hidden);
    },
    [nodes, onFilterChange],
  );

  // Debounce text search
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      applyFilters(filters);
    }, 300);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [filters, applyFilters]);

  // Close dropdowns on outside click
  useEffect(() => {
    const handler = (e: globalThis.MouseEvent) => {
      if (typeDropdownRef.current && !typeDropdownRef.current.contains(e.target as Node)) {
        setShowTypeDropdown(false);
      }
      if (scannerDropdownRef.current && !scannerDropdownRef.current.contains(e.target as Node)) {
        setShowScannerDropdown(false);
      }
      if (presetsDropdownRef.current && !presetsDropdownRef.current.contains(e.target as Node)) {
        setShowPresetsDropdown(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const toggleNodeType = useCallback((type: string) => {
    setFilters((prev) => ({
      ...prev,
      nodeTypes: prev.nodeTypes.includes(type)
        ? prev.nodeTypes.filter((t) => t !== type)
        : [...prev.nodeTypes, type],
    }));
  }, []);

  const toggleScanner = useCallback((scanner: string) => {
    setFilters((prev) => ({
      ...prev,
      scanners: prev.scanners.includes(scanner)
        ? prev.scanners.filter((s) => s !== scanner)
        : [...prev.scanners, scanner],
    }));
  }, []);

  const handleSearchChange = useCallback((e: ChangeEvent<HTMLInputElement>) => {
    setFilters((prev) => ({ ...prev, searchText: e.target.value }));
  }, []);

  const handleConfidenceChange = useCallback(
    (e: ChangeEvent<HTMLInputElement>) => {
      setFilters((prev) => ({
        ...prev,
        minConfidence: parseInt(e.target.value) / 100,
      }));
    },
    [],
  );

  const clearAll = useCallback(() => {
    setFilters(DEFAULT_FILTER);
    onFilterChange(new Set());
  }, [onFilterChange]);

  const activeCount = countActiveFilters(filters);

  return (
    <div className="relative">
      {/* Toggle button */}
      <button
        onClick={() => setVisible((v) => !v)}
        aria-expanded={visible}
        aria-label="Toggle filter bar"
        className={`inline-flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-xs font-medium transition-colors ${
          visible || activeCount > 0
            ? "bg-bg-overlay text-text-primary"
            : "text-text-secondary hover:bg-bg-overlay"
        }`}
        style={{ borderColor: "var(--border-default)" }}
      >
        <Filter className="h-3.5 w-3.5" />
        Filters
        {activeCount > 0 && (
          <Badge variant="brand" size="sm">
            {activeCount}
          </Badge>
        )}
      </button>

      {/* Filter bar */}
      <div
        className={`mt-1 overflow-hidden rounded-lg border transition-all duration-200 ${
          visible
            ? "max-h-24 opacity-100"
            : "max-h-0 opacity-0 border-transparent"
        }`}
        style={{
          background: visible ? "var(--bg-surface)" : undefined,
          borderColor: visible ? "var(--border-subtle)" : undefined,
        }}
      >
        {visible && (
          <div className="flex flex-wrap items-center gap-3 px-4 py-2.5">
            {/* Node type multi-select */}
            <div className="relative" ref={typeDropdownRef}>
              <button
                onClick={() => setShowTypeDropdown((v) => !v)}
                aria-expanded={showTypeDropdown}
                aria-haspopup="listbox"
                className="inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-xs font-medium transition-colors hover:bg-bg-overlay"
                style={{
                  borderColor: "var(--border-default)",
                  color: "var(--text-secondary)",
                }}
              >
                {filters.nodeTypes.length === 0
                  ? "All Types"
                  : `${filters.nodeTypes.length} Types`}
                <ChevronDown className="h-3 w-3" />
              </button>
              {showTypeDropdown && (
                <div
                  className="absolute left-0 top-full z-50 mt-1 max-h-52 w-44 overflow-y-auto rounded-lg border py-1 shadow-lg"
                  style={{
                    background: "var(--bg-surface)",
                    borderColor: "var(--border-default)",
                  }}
                  role="listbox"
                  aria-label="Node types"
                  aria-multiselectable="true"
                >
                  {ALL_NODE_TYPES.map((type) => (
                    <button
                      key={type}
                      role="option"
                      aria-selected={filters.nodeTypes.includes(type)}
                      onClick={() => toggleNodeType(type)}
                      className="flex w-full items-center gap-2 px-3 py-1.5 text-xs capitalize transition-colors hover:bg-bg-overlay"
                      style={{ color: "var(--text-primary)" }}
                    >
                      <span className="flex h-3.5 w-3.5 shrink-0 items-center justify-center rounded-sm border"
                        style={{
                          borderColor: "var(--border-default)",
                          background: filters.nodeTypes.includes(type)
                            ? "var(--brand-500)"
                            : undefined,
                        }}
                      >
                        {filters.nodeTypes.includes(type) && (
                          <Check className="h-2.5 w-2.5 text-white" />
                        )}
                      </span>
                      {type.replace(/_/g, " ")}
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* Confidence slider */}
            <div className="flex items-center gap-2">
              <span
                className="text-xs font-medium"
                style={{ color: "var(--text-tertiary)" }}
              >
                Confidence:
              </span>
              <input
                type="range"
                min={0}
                max={100}
                value={Math.round(filters.minConfidence * 100)}
                onChange={handleConfidenceChange}
                aria-label="Minimum confidence filter"
                className="w-20 accent-[var(--brand-500)]"
              />
              <span
                className="w-8 text-right text-xs font-mono"
                style={{ color: "var(--text-secondary)" }}
              >
                {Math.round(filters.minConfidence * 100)}%
              </span>
            </div>

            {/* Scanner multi-select */}
            {availableScanners.length > 0 && (
              <div className="relative" ref={scannerDropdownRef}>
                <button
                  onClick={() => setShowScannerDropdown((v) => !v)}
                  aria-expanded={showScannerDropdown}
                  aria-haspopup="listbox"
                  className="inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-xs font-medium transition-colors hover:bg-bg-overlay"
                  style={{
                    borderColor: "var(--border-default)",
                    color: "var(--text-secondary)",
                  }}
                >
                  {filters.scanners.length === 0
                    ? "All Scanners"
                    : `${filters.scanners.length} Scanners`}
                  <ChevronDown className="h-3 w-3" />
                </button>
                {showScannerDropdown && (
                  <div
                    className="absolute left-0 top-full z-50 mt-1 max-h-48 w-44 overflow-y-auto rounded-lg border py-1 shadow-lg"
                    style={{
                      background: "var(--bg-surface)",
                      borderColor: "var(--border-default)",
                    }}
                    role="listbox"
                    aria-label="Scanners"
                    aria-multiselectable="true"
                  >
                    {availableScanners.map((scanner) => (
                      <button
                        key={scanner}
                        role="option"
                        aria-selected={filters.scanners.includes(scanner)}
                        onClick={() => toggleScanner(scanner)}
                        className="flex w-full items-center gap-2 px-3 py-1.5 text-xs transition-colors hover:bg-bg-overlay"
                        style={{ color: "var(--text-primary)" }}
                      >
                        <span className="flex h-3.5 w-3.5 shrink-0 items-center justify-center rounded-sm border"
                          style={{
                            borderColor: "var(--border-default)",
                            background: filters.scanners.includes(scanner)
                              ? "var(--brand-500)"
                              : undefined,
                          }}
                        >
                          {filters.scanners.includes(scanner) && (
                            <Check className="h-2.5 w-2.5 text-white" />
                          )}
                        </span>
                        {scanner}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Search text */}
            <div className="w-44">
              <Input
                placeholder="Filter by value..."
                value={filters.searchText}
                onChange={handleSearchChange}
                aria-label="Filter nodes by value"
                suffixIcon={
                  filters.searchText ? (
                    <button
                      onClick={() =>
                        setFilters((prev) => ({ ...prev, searchText: "" }))
                      }
                      aria-label="Clear search"
                    >
                      <X className="h-3 w-3" />
                    </button>
                  ) : undefined
                }
              />
            </div>

            {/* Filter presets */}
            <div className="relative ml-auto" ref={presetsDropdownRef}>
              <button
                onClick={() => setShowPresetsDropdown((v) => !v)}
                aria-expanded={showPresetsDropdown}
                className="inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-xs font-medium transition-colors hover:bg-bg-overlay"
                style={{ borderColor: "var(--border-default)", color: "var(--text-secondary)" }}
                title="Filter presets"
              >
                <Bookmark className="h-3.5 w-3.5" />
                Presets {presets.length > 0 && <span className="opacity-60">({presets.length})</span>}
              </button>
              {showPresetsDropdown && (
                <div
                  className="absolute right-0 top-full z-50 mt-1 w-52 rounded-lg border py-1 shadow-lg"
                  style={{ background: "var(--bg-surface)", borderColor: "var(--border-default)" }}
                >
                  {presets.length > 0 && (
                    <div className="border-b pb-1 mb-1" style={{ borderColor: "var(--border-subtle)" }}>
                      {presets.map((p) => (
                        <div key={p.name} className="flex items-center gap-1 px-2 py-1 hover:bg-bg-overlay">
                          <button
                            onClick={() => loadPreset(p)}
                            className="flex-1 truncate text-left text-xs"
                            style={{ color: "var(--text-primary)" }}
                          >
                            <BookmarkCheck className="h-3 w-3 inline mr-1" style={{ color: "var(--brand-400)" }} />
                            {p.name}
                          </button>
                          <button
                            onClick={() => deletePreset(p.name)}
                            className="rounded p-0.5 hover:bg-bg-elevated"
                            aria-label={`Delete preset ${p.name}`}
                          >
                            <X className="h-3 w-3" style={{ color: "var(--text-tertiary)" }} />
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                  <div className="flex items-center gap-1 px-2 py-1">
                    <input
                      type="text"
                      value={newPresetName}
                      onChange={(e) => setNewPresetName(e.target.value)}
                      onKeyDown={(e) => e.key === "Enter" && saveCurrentAsPreset()}
                      placeholder="Preset name…"
                      className="flex-1 rounded border px-2 py-0.5 text-xs"
                      style={{ background: "var(--bg-overlay)", borderColor: "var(--border-subtle)", color: "var(--text-primary)" }}
                    />
                    <button
                      onClick={saveCurrentAsPreset}
                      disabled={!newPresetName.trim()}
                      className="rounded px-2 py-0.5 text-xs font-medium disabled:opacity-40"
                      style={{ background: "var(--brand-500)", color: "#fff" }}
                    >
                      Save
                    </button>
                  </div>
                </div>
              )}
            </div>

            {/* Clear all */}
            {activeCount > 0 && (
              <Button
                variant="ghost"
                size="sm"
                onClick={clearAll}
                leftIcon={<X className="h-3.5 w-3.5" />}
              >
                Clear all
              </Button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
