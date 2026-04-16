import { memo } from "react";
import { type NodeProps } from "reactflow";
import { AtSign } from "lucide-react";
import { BaseNode } from "./BaseNode";
import type { OsintNodeData } from "../../types";

export const UsernameNode = memo(function UsernameNode(props: NodeProps<OsintNodeData>) {
  return <BaseNode icon={<AtSign className="h-4 w-4" style={{ color: "var(--node-username)" }} />} nodeProps={props} />;
});
