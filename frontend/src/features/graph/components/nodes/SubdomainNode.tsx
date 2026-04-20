import { memo } from "react";
import { type NodeProps } from "reactflow";
import { Layers } from "lucide-react";
import { BaseNode } from "./BaseNode";
import type { OsintNodeData } from "../../types";

export const SubdomainNode = memo(function SubdomainNode(props: NodeProps<OsintNodeData>) {
  return <BaseNode icon={<Layers className="h-4 w-4" style={{ color: "var(--node-subdomain, #38bdf8)" }} />} nodeProps={props} />;
});
