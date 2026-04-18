import { memo } from "react";
import { type NodeProps } from "reactflow";
import { Hash } from "lucide-react";
import { BaseNode } from "./BaseNode";
import type { OsintNodeData } from "../../types";

export const HashNode = memo(function HashNode(props: NodeProps<OsintNodeData>) {
  return <BaseNode icon={<Hash className="h-4 w-4" style={{ color: "var(--node-hash, #a3a3a3)" }} />} nodeProps={props} />;
});
