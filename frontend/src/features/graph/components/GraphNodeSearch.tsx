import {
  useState,
  useEffect,
  useCallback,
  useRef,
  useMemo,
  type KeyboardEvent,
} from "react";
import { Search, X } from "lucide-react";
import { NodeTypeIcon } from "@/shared/components/osint/NodeTypeIcon";
import type { OsintNodeData } from "../types";

interface GraphNodeSearchProps {
  nodes: OsintNodeData[];
  onSelectNode: (nodeId: string) => void;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

function fuzzyScore(query: string, target: string): number {
  if (!query) return 1;
  const q = query.toLowerCase();
  const t = target.toLowerCase();
  if (t.includes(q)) return 2;
  let qi = 0;
  for (let ti = 0; ti < t.length && qi < q.length; ti++) {
    if (t[ti] === q[qi]) qi++;
  }
  return qi === q.length ? 1 : 0;
}

export function GraphNodeSearch({
  nodes,
  onSelectNode,
  open,
  onOpenChange,
}: GraphNodeSearchProps) {
  const [query, setQuery] = useState("");
  const [activeIndex, setActiveIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLUListElement>(null);

  const results = useMemo(() => {
    if (!query.trim()) return nodes.slice(0, 20);
    return nodes
      .map((node) => ({
        node,
        score: Math.max(fuzzyScore(query, node.label), fuzzyScore(query, node.type)),
      }))
      .filter((r) => r.score > 0)
      .sort((a, b) => b.score - a.score)
      .slice(0, 20)
      .map((r) => r.node);
  }, [nodes, query]);

  // Focus input on open
  useEffect(() => {
    if (open) {
      setQuery("");
      setActiveIndex(0);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [open]);

  // Reset active index when results change
  useEffect(() => {
    setActiveIndex(0);
  }, [results]);

  // Keyboard shortcut: Ctrl+F to open
  useEffect(() => {
    const handler = (e: globalThis.KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "f") {
        e.preventDefault();
        onOpenChange(true);
      }
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [onOpenChange]);

  const handleSelect = useCallback(
    (nodeId: string) => {
      onSelectNode(nodeId);
      onOpenChange(false);
      setQuery("");
    },
    [onSelectNode, onOpenChange],
  );

  const handleKeyDown = useCallback(
    (e: KeyboardEvent<HTMLInputElement>) => {
      switch (e.key) {
        case "ArrowDown":
          e.preventDefault();
          setActiveIndex((i) => Math.min(i + 1, results.length - 1));
          break;
        case "ArrowUp":
          e.preventDefault();
          setActiveIndex((i) => Math.max(i - 1, 0));
          break;
        case "Enter":
          e.preventDefault();
          if (results[activeIndex]) {
            handleSelect(results[activeIndex].id);
          }
          break;
        case "Escape":
          onOpenChange(false);
          break;
      }
    },
    [results, activeIndex, handleSelect, onOpenChange],
  );

  // Scroll active item into view
  useEffect(() => {
    const list = listRef.current;
    if (!list) return;
    const item = list.children[activeIndex] as HTMLElement | undefined;
    item?.scrollIntoView({ block: "nearest" });
  }, [activeIndex]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center pt-24"
      role="dialog"
      aria-modal="true"
      aria-label="Node search"
    >
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/50"
        onClick={() => onOpenChange(false)}
        aria-hidden="true"
      />

      {/* Panel */}
      <div
        className="relative z-10 w-full max-w-md rounded-xl border shadow-2xl overflow-hidden"
        style={{
          background: "var(--bg-surface)",
          borderColor: "var(--border-default)",
        }}
      >
        {/* Search input */}
        <div
          className="flex items-center gap-3 border-b px-4 py-3"
          style={{ borderColor: "var(--border-subtle)" }}
        >
          <Search
            className="h-4 w-4 shrink-0"
            style={{ color: "var(--text-tertiary)" }}
          />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Search nodes..."
            aria-label="Search nodes"
            aria-controls="node-search-results"
            aria-activedescendant={
              results[activeIndex] ? `node-result-${results[activeIndex].id}` : undefined
            }
            className="flex-1 bg-transparent text-sm outline-none placeholder:text-[var(--text-tertiary)]"
            style={{ color: "var(--text-primary)" }}
          />
          {query && (
            <button
              onClick={() => setQuery("")}
              aria-label="Clear search"
              className="rounded p-0.5 transition-colors hover:bg-bg-overlay"
            >
              <X className="h-3.5 w-3.5" style={{ color: "var(--text-tertiary)" }} />
            </button>
          )}
          <kbd
            className="hidden rounded px-1.5 py-0.5 text-[10px] font-mono sm:block"
            style={{
              background: "var(--bg-elevated)",
              color: "var(--text-tertiary)",
              border: "1px solid var(--border-default)",
            }}
          >
            ESC
          </kbd>
        </div>

        {/* Results list */}
        <ul
          ref={listRef}
          id="node-search-results"
          role="listbox"
          aria-label="Search results"
          className="max-h-72 overflow-y-auto py-1"
        >
          {results.length === 0 ? (
            <li
              className="px-4 py-6 text-center text-sm"
              style={{ color: "var(--text-tertiary)" }}
            >
              No nodes found
            </li>
          ) : (
            results.map((node, idx) => (
              <li
                key={node.id}
                id={`node-result-${node.id}`}
                role="option"
                aria-selected={idx === activeIndex}
              >
                <button
                  onClick={() => handleSelect(node.id)}
                  onMouseEnter={() => setActiveIndex(idx)}
                  className="flex w-full items-center gap-3 px-4 py-2 text-left text-sm transition-colors"
                  style={{
                    background: idx === activeIndex ? "var(--bg-overlay)" : undefined,
                    color: "var(--text-primary)",
                  }}
                >
                  <NodeTypeIcon type={node.type} size="sm" />
                  <div className="flex-1 min-w-0">
                    <p className="truncate font-medium" style={{ color: "var(--text-primary)" }}>
                      {node.label}
                    </p>
                    <p className="truncate text-xs capitalize" style={{ color: "var(--text-tertiary)" }}>
                      {node.type.replace(/_/g, " ")}
                    </p>
                  </div>
                  {idx === activeIndex && (
                    <kbd
                      className="rounded px-1 py-0.5 text-[10px] font-mono"
                      style={{
                        background: "var(--bg-elevated)",
                        color: "var(--text-tertiary)",
                        border: "1px solid var(--border-default)",
                      }}
                    >
                      ↵
                    </kbd>
                  )}
                </button>
              </li>
            ))
          )}
        </ul>

        {/* Footer */}
        <div
          className="flex items-center gap-4 border-t px-4 py-2"
          style={{
            borderColor: "var(--border-subtle)",
            background: "var(--bg-elevated)",
          }}
        >
          <span className="text-[10px]" style={{ color: "var(--text-tertiary)" }}>
            <kbd className="font-mono">↑↓</kbd> navigate
          </span>
          <span className="text-[10px]" style={{ color: "var(--text-tertiary)" }}>
            <kbd className="font-mono">↵</kbd> select
          </span>
          <span className="ml-auto text-[10px]" style={{ color: "var(--text-tertiary)" }}>
            {results.length} result{results.length !== 1 ? "s" : ""}
          </span>
        </div>
      </div>
    </div>
  );
}
