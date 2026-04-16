import { memo } from "react";
import { Handle, Position, type NodeProps } from "reactflow";
import type { OsintNodeData, NodeType } from "../../types";

const nodeColors: Record<NodeType, string> = {
  person: "var(--node-person)",
  company: "var(--node-company)",
  email: "var(--node-email)",
  phone: "var(--node-phone)",
  username: "var(--node-username)",
  ip: "var(--node-ip)",
  domain: "var(--node-domain)",
};

interface BaseNodeProps {
  icon: React.ReactNode;
  nodeProps: NodeProps<OsintNodeData>;
}

export const BaseNode = memo(function BaseNode({ icon, nodeProps }: BaseNodeProps) {
  const { data, selected } = nodeProps;
  const color = nodeColors[data.type] ?? "var(--text-tertiary)";
  const truncatedLabel = data.label.length > 25 ? data.label.slice(0, 22) + "..." : data.label;

  return (
    <>
      <Handle type="target" position={Position.Top} className="!w-2 !h-2 !border-0" style={{ background: color }} />
      <Handle type="target" position={Position.Left} className="!w-2 !h-2 !border-0" style={{ background: color }} />

      <div
        className={`rounded-lg border px-3 py-2 transition-all ${
          data.isDimmed ? "opacity-20" : ""
        } ${data.isOnPath ? "ring-2 ring-brand-400" : ""}`}
        style={{
          background: "var(--bg-surface)",
          borderColor: selected ? color : "var(--border-default)",
          boxShadow: selected ? `0 0 12px ${color}40` : "var(--shadow-sm)",
          minWidth: 160,
          maxWidth: 220,
        }}
      >
        {/* Header */}
        <div className="flex items-center gap-2">
          <div
            className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md"
            style={{ background: `${color}15` }}
          >
            {icon}
          </div>
          <span
            className="truncate text-xs font-semibold"
            style={{ color: "var(--text-primary)" }}
            title={data.label}
          >
            {truncatedLabel}
          </span>
        </div>

        {/* Separator */}
        <div className="my-1.5 h-px" style={{ background: "var(--border-subtle)" }} />

        {/* Footer */}
        <div className="flex items-center justify-between">
          {/* Confidence dots */}
          <div className="flex items-center gap-0.5">
            {[0.25, 0.5, 0.75, 1.0].map((threshold) => (
              <div
                key={threshold}
                className="h-1.5 w-1.5 rounded-full"
                style={{
                  background: data.confidence >= threshold ? color : "var(--bg-overlay)",
                }}
              />
            ))}
            <span className="ml-1 text-[10px] font-mono" style={{ color: "var(--text-tertiary)" }}>
              {Math.round(data.confidence * 100)}%
            </span>
          </div>

          {/* Sources */}
          <span className="truncate text-[10px]" style={{ color: "var(--text-tertiary)", maxWidth: 80 }}>
            {data.sources.slice(0, 2).join(", ")}
            {data.sources.length > 2 ? ` +${data.sources.length - 2}` : ""}
          </span>
        </div>
      </div>

      <Handle type="source" position={Position.Bottom} className="!w-2 !h-2 !border-0" style={{ background: color }} />
      <Handle type="source" position={Position.Right} className="!w-2 !h-2 !border-0" style={{ background: color }} />
    </>
  );
});
