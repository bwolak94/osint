import { memo } from "react";
import { type NodeProps } from "reactflow";
import { Wifi } from "lucide-react";
import { BaseNode } from "./BaseNode";
import type { OsintNodeData } from "../../types";

export const IPNode = memo(function IPNode(props: NodeProps<OsintNodeData>) {
  return <BaseNode icon={<Wifi className="h-4 w-4" style={{ color: "var(--node-ip)" }} />} nodeProps={props} />;
});
