import { Badge } from "@/shared/components/Badge";
import { Loader2 } from "lucide-react";

type ScanStatus = "pending" | "running" | "success" | "failed" | "rate_limited";

const statusConfig: Record<ScanStatus, { variant: "neutral" | "info" | "success" | "danger" | "warning"; label: string }> = {
  pending: { variant: "neutral", label: "Pending" },
  running: { variant: "info", label: "Running" },
  success: { variant: "success", label: "Success" },
  failed: { variant: "danger", label: "Failed" },
  rate_limited: { variant: "warning", label: "Rate Limited" },
};

interface ScanStatusBadgeProps {
  status: string;
}

export function ScanStatusBadge({ status }: ScanStatusBadgeProps) {
  const config = statusConfig[status as ScanStatus] ?? statusConfig.pending;
  return (
    <Badge variant={config.variant} size="sm" dot>
      {status === "running" && <Loader2 className="h-3 w-3 animate-spin" />}
      {config.label}
    </Badge>
  );
}
