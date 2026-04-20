import { memo } from "react";
import { type NodeProps } from "reactflow";
import { Server } from "lucide-react";
import { BaseNode } from "./BaseNode";
import type { OsintNodeData } from "../../types";

export const ASNNode = memo(function ASNNode(props: NodeProps<OsintNodeData>) {
  return <BaseNode icon={<Server className="h-4 w-4" style={{ color: "var(--node-asn, #64748b)" }} />} nodeProps={props} />;
});
