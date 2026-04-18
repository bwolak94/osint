import { memo } from "react";
import { type NodeProps } from "reactflow";
import { Link } from "lucide-react";
import { BaseNode } from "./BaseNode";
import type { OsintNodeData } from "../../types";

export const URLNode = memo(function URLNode(props: NodeProps<OsintNodeData>) {
  return <BaseNode icon={<Link className="h-4 w-4" style={{ color: "var(--node-url, #2dd4bf)" }} />} nodeProps={props} />;
});
