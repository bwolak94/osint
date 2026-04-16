import { memo } from "react";
import { type NodeProps } from "reactflow";
import { Phone } from "lucide-react";
import { BaseNode } from "./BaseNode";
import type { OsintNodeData } from "../../types";

export const PhoneNode = memo(function PhoneNode(props: NodeProps<OsintNodeData>) {
  return <BaseNode icon={<Phone className="h-4 w-4" style={{ color: "var(--node-phone)" }} />} nodeProps={props} />;
});
