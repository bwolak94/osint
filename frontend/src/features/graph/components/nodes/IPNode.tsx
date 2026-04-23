import { memo, useCallback } from "react";
import { type NodeProps } from "reactflow";
import { Wifi } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { BaseNode } from "./BaseNode";
import type { OsintNodeData } from "../../types";

export const IPNode = memo(function IPNode(props: NodeProps<OsintNodeData>) {
  const navigate = useNavigate();

  const handlePentestTarget = useCallback(() => {
    navigate("/pentest/engagements/new", {
      state: {
        prefilled_target: { type: "ip", value: props.data.label },
      },
    });
  }, [navigate, props.data.label]);

  return (
    <BaseNode
      icon={<Wifi className="h-4 w-4" style={{ color: "var(--node-ip)" }} />}
      nodeProps={props}
      onPentestTarget={handlePentestTarget}
    />
  );
});
