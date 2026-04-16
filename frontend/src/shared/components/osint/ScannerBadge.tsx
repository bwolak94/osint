import { Badge } from "@/shared/components/Badge";

const scannerColors: Record<string, "brand" | "info" | "success" | "warning"> = {
  holehe: "success",
  maigret: "info",
  playwright_krs: "brand",
  playwright_ceidg: "brand",
  vat_status: "warning",
};

interface ScannerBadgeProps {
  scanner: string;
}

export function ScannerBadge({ scanner }: ScannerBadgeProps) {
  const variant = scannerColors[scanner] ?? "neutral";
  return (
    <Badge variant={variant} size="sm">
      {scanner}
    </Badge>
  );
}
