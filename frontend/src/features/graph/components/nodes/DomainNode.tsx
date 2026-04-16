import { memo } from "react";
import { type NodeProps } from "reactflow";
import { Globe } from "lucide-react";
import { BaseNode } from "./BaseNode";
import type { OsintNodeData } from "../../types";

export const DomainNode = memo(function DomainNode(props: NodeProps<OsintNodeData>) {
  return <BaseNode icon={<Globe className="h-4 w-4" style={{ color: "var(--node-domain)" }} />} nodeProps={props} />;
});
