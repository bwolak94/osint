import { useCallback, useState } from "react";
import { Expand, Eye, EyeOff, Pin, MessageSquare, Copy, Route, Scan, Trash2 } from "lucide-react";

interface ContextMenuProps {
  x: number;
  y: number;
  nodeId: string;
  nodeLabel: string;
  onClose: () => void;
  onExpand: (id: string) => void;
  onStartPathFrom: (id: string) => void;
  onCopyValue: (value: string) => void;
}

export function NodeContextMenu({
  x, y, nodeId, nodeLabel, onClose, onExpand, onStartPathFrom, onCopyValue,
}: ContextMenuProps) {
  const items = [
    { icon: Expand, label: "Expand Connections", action: () => onExpand(nodeId) },
    { icon: Route, label: "Find Paths From Here", action: () => onStartPathFrom(nodeId) },
    { icon: Copy, label: "Copy Value", action: () => onCopyValue(nodeLabel) },
    { icon: Scan, label: "Run New Scan", action: () => {} },
    { icon: MessageSquare, label: "Add Annotation", action: () => {} },
    { icon: Trash2, label: "Hide Node", action: () => {} },
  ];

  return (
    <>
      <div className="fixed inset-0 z-40" onClick={onClose} />
      <div
        className="fixed z-50 rounded-lg border py-1 shadow-lg"
        style={{
          left: x, top: y,
          background: "var(--bg-surface)",
          borderColor: "var(--border-default)",
          minWidth: 200,
        }}
      >
        {items.map((item) => (
          <button
            key={item.label}
            onClick={() => { item.action(); onClose(); }}
            className="flex w-full items-center gap-2.5 px-3 py-2 text-sm transition-colors hover:bg-bg-overlay"
            style={{ color: "var(--text-primary)" }}
          >
            <item.icon className="h-3.5 w-3.5" style={{ color: "var(--text-tertiary)" }} />
            {item.label}
          </button>
        ))}
      </div>
    </>
  );
}
