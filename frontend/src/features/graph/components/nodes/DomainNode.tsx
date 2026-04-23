import { memo, useCallback } from "react";
import { type NodeProps } from "reactflow";
import { Globe } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { BaseNode } from "./BaseNode";
import type { OsintNodeData } from "../../types";

export const DomainNode = memo(function DomainNode(props: NodeProps<OsintNodeData>) {
  const navigate = useNavigate();

  const handlePentestTarget = useCallback(() => {
    navigate("/pentest/engagements/new", {
      state: {
        prefilled_target: { type: "domain", value: props.data.label },
      },
    });
  }, [navigate, props.data.label]);

  return (
    <BaseNode
      icon={<Globe className="h-4 w-4" style={{ color: "var(--node-domain)" }} />}
      nodeProps={props}
      onPentestTarget={handlePentestTarget}
    />
  );
});
