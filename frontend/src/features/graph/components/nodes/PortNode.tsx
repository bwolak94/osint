import { memo } from "react";
import { type NodeProps } from "reactflow";
import { Network } from "lucide-react";
import { BaseNode } from "./BaseNode";
import type { OsintNodeData } from "../../types";

export const PortNode = memo(function PortNode(props: NodeProps<OsintNodeData>) {
  return <BaseNode icon={<Network className="h-4 w-4" style={{ color: "var(--node-port, #94a3b8)" }} />} nodeProps={props} />;
});
