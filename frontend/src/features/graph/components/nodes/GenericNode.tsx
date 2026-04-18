import { memo } from "react";
import { type NodeProps } from "reactflow";
import { Circle } from "lucide-react";
import { BaseNode } from "./BaseNode";
import type { OsintNodeData } from "../../types";

export const GenericNode = memo(function GenericNode(props: NodeProps<OsintNodeData>) {
  return <BaseNode icon={<Circle className="h-4 w-4" style={{ color: "var(--text-tertiary)" }} />} nodeProps={props} />;
});
