import { memo } from "react";
import { type NodeProps } from "reactflow";
import { Mail } from "lucide-react";
import { BaseNode } from "./BaseNode";
import type { OsintNodeData } from "../../types";

export const EmailNode = memo(function EmailNode(props: NodeProps<OsintNodeData>) {
  return <BaseNode icon={<Mail className="h-4 w-4" style={{ color: "var(--node-email)" }} />} nodeProps={props} />;
});
