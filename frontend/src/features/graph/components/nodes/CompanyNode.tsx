import { memo } from "react";
import { type NodeProps } from "reactflow";
import { Building2 } from "lucide-react";
import { BaseNode } from "./BaseNode";
import type { OsintNodeData } from "../../types";

export const CompanyNode = memo(function CompanyNode(props: NodeProps<OsintNodeData>) {
  return <BaseNode icon={<Building2 className="h-4 w-4" style={{ color: "var(--node-company)" }} />} nodeProps={props} />;
});
