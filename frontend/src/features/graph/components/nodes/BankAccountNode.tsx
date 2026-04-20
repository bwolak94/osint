import { memo } from "react";
import { type NodeProps } from "reactflow";
import { Landmark } from "lucide-react";
import { BaseNode } from "./BaseNode";
import type { OsintNodeData } from "../../types";

export const BankAccountNode = memo(function BankAccountNode(props: NodeProps<OsintNodeData>) {
  return <BaseNode icon={<Landmark className="h-4 w-4" style={{ color: "var(--node-bank-account, #eab308)" }} />} nodeProps={props} />;
});
