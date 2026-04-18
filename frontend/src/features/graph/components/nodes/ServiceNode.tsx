import { memo } from "react";
import { type NodeProps } from "reactflow";
import { Cog } from "lucide-react";
import { BaseNode } from "./BaseNode";
import type { OsintNodeData } from "../../types";

export const ServiceNode = memo(function ServiceNode(props: NodeProps<OsintNodeData>) {
  return <BaseNode icon={<Cog className="h-4 w-4" style={{ color: "var(--node-service, #f472b6)" }} />} nodeProps={props} />;
});
