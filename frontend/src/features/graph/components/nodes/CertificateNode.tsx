import { memo } from "react";
import { type NodeProps } from "reactflow";
import { FileKey } from "lucide-react";
import { BaseNode } from "./BaseNode";
import type { OsintNodeData } from "../../types";

export const CertificateNode = memo(function CertificateNode(props: NodeProps<OsintNodeData>) {
  return <BaseNode icon={<FileKey className="h-4 w-4" style={{ color: "var(--node-certificate, #a78bfa)" }} />} nodeProps={props} />;
});
