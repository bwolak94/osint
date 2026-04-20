import { memo } from "react";
import { type NodeProps } from "reactflow";
import { ShieldAlert } from "lucide-react";
import { BaseNode } from "./BaseNode";
import type { OsintNodeData } from "../../types";

export const BreachNode = memo(function BreachNode(props: NodeProps<OsintNodeData>) {
  return <BaseNode icon={<ShieldAlert className="h-4 w-4" style={{ color: "var(--node-breach, #dc2626)" }} />} nodeProps={props} />;
});
