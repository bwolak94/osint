import { memo } from "react";
import { type NodeProps } from "reactflow";
import { User } from "lucide-react";
import { BaseNode } from "./BaseNode";
import type { OsintNodeData } from "../../types";

export const PersonNode = memo(function PersonNode(props: NodeProps<OsintNodeData>) {
  return <BaseNode icon={<User className="h-4 w-4" style={{ color: "var(--node-person)" }} />} nodeProps={props} />;
});
