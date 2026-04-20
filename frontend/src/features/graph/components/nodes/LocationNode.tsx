import { memo } from "react";
import { type NodeProps } from "reactflow";
import { MapPin } from "lucide-react";
import { BaseNode } from "./BaseNode";
import type { OsintNodeData } from "../../types";

export const LocationNode = memo(function LocationNode(props: NodeProps<OsintNodeData>) {
  return <BaseNode icon={<MapPin className="h-4 w-4" style={{ color: "var(--node-location, #fb923c)" }} />} nodeProps={props} />;
});
