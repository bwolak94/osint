import { Expand, Copy, Route, Scan, Trash2, EyeOff, Bookmark, Tag, MessageSquare, Shield } from "lucide-react";

interface ContextMenuProps {
  x: number;
  y: number;
  nodeId: string;
  nodeLabel: string;
  /** Optional node type — used to conditionally show the "Pentest this" item */
  nodeType?: string;
  onClose: () => void;
  onExpand: (id: string) => void;
  onStartPathFrom: (id: string) => void;
  onCopyValue: (value: string) => void;
  onRunTransforms?: (id: string) => void;
  onHideNode?: (id: string) => void;
  onRemoveNode?: (id: string) => void;
  /** Called when user clicks "Pentest this target". Only rendered for domain/IP nodes. */
  onPentestThis?: (nodeId: string, nodeLabel: string, nodeType: string) => void;
}

interface MenuItem {
  icon: typeof Expand;
  label: string;
  action: () => void;
  divider?: boolean;
  variant?: "danger";
}

const PENTEST_NODE_TYPES = new Set(["domain", "ip", "subdomain", "url"]);

export function NodeContextMenu({
  x, y, nodeId, nodeLabel, nodeType, onClose, onExpand, onStartPathFrom, onCopyValue,
  onRunTransforms, onHideNode, onRemoveNode, onPentestThis,
}: ContextMenuProps) {
  const isPentestable = nodeType != null && PENTEST_NODE_TYPES.has(nodeType);

  const items: MenuItem[] = [
    { icon: Expand, label: "Expand All", action: () => onExpand(nodeId) },
    { icon: Scan, label: "Run Transforms", action: () => onRunTransforms?.(nodeId), divider: true },
    { icon: Route, label: "Find Paths From Here", action: () => onStartPathFrom(nodeId) },
    { icon: Copy, label: "Copy Value", action: () => onCopyValue(nodeLabel) },
    { icon: Bookmark, label: "Bookmark Node", action: () => {} },
    { icon: Tag, label: "Add Tag", action: () => {} },
    { icon: MessageSquare, label: "Add Note", action: () => {}, divider: isPentestable ? false : true },
    ...(isPentestable
      ? [
          {
            icon: Shield,
            label: "Pentest this target",
            action: () => onPentestThis?.(nodeId, nodeLabel, nodeType ?? "domain"),
            divider: true as const,
          },
        ]
      : []),
    { icon: EyeOff, label: "Hide Node", action: () => onHideNode?.(nodeId) },
    { icon: Trash2, label: "Remove Node", action: () => onRemoveNode?.(nodeId), variant: "danger" },
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
          minWidth: 220,
        }}
      >
        {/* Header showing node label */}
        <div
          className="border-b px-3 py-1.5 text-xs font-medium truncate"
          style={{ borderColor: "var(--border-subtle)", color: "var(--text-tertiary)", maxWidth: 240 }}
          title={nodeLabel}
        >
          {nodeLabel}
        </div>

        {items.map((item) => (
          <div key={item.label}>
            <button
              onClick={() => { item.action(); onClose(); }}
              className="flex w-full items-center gap-2.5 px-3 py-2 text-sm transition-colors hover:bg-bg-overlay"
              style={{ color: item.variant === "danger" ? "var(--status-error)" : "var(--text-primary)" }}
            >
              <item.icon
                className="h-3.5 w-3.5"
                style={{ color: item.variant === "danger" ? "var(--status-error)" : "var(--text-tertiary)" }}
              />
              {item.label}
            </button>
            {item.divider && (
              <div className="my-1 h-px" style={{ background: "var(--border-subtle)" }} />
            )}
          </div>
        ))}
      </div>
    </>
  );
}
