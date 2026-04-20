import { Link } from "react-router-dom";
import { Lock } from "lucide-react";
import { useAuth } from "@/shared/hooks/useAuth";
import type { ReactNode } from "react";

type Feature = "deep_scan" | "graph_analysis" | "export_report" | "api_access" | "bulk_scan" | "playwright_scan";

const featureRequirements: Record<Feature, string> = {
  deep_scan: "pro",
  graph_analysis: "pro",
  export_report: "pro",
  api_access: "pro",
  bulk_scan: "enterprise",
  playwright_scan: "pro",
};

const tierOrder = ["free", "pro", "enterprise"];

function hasAccess(userTier: string, requiredTier: string): boolean {
  return tierOrder.indexOf(userTier) >= tierOrder.indexOf(requiredTier);
}

interface FeatureGateProps {
  feature: Feature;
  children: ReactNode;
  fallback?: ReactNode;
}

export function FeatureGate({ feature, children, fallback }: FeatureGateProps) {
  const { user } = useAuth();
  const requiredTier = featureRequirements[feature] ?? "pro";
  const userTier = user?.subscription_tier ?? "free";

  if (hasAccess(userTier, requiredTier)) {
    return <>{children}</>;
  }

  if (fallback) {
    return <>{fallback}</>;
  }

  return (
    <div
      className="flex flex-col items-center justify-center rounded-lg border border-dashed p-8 text-center"
      style={{ borderColor: "var(--border-default)", background: "var(--bg-elevated)" }}
    >
      <Lock className="mb-2 h-6 w-6" style={{ color: "var(--text-tertiary)" }} />
      <p className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>
        Requires {requiredTier.charAt(0).toUpperCase() + requiredTier.slice(1)} plan
      </p>
      <p className="mt-1 text-xs" style={{ color: "var(--text-secondary)" }}>
        Upgrade your subscription to access this feature
      </p>
      <Link
        to="/billing"
        className="mt-3 text-sm font-medium"
        style={{ color: "var(--brand-500)" }}
      >
        Upgrade &rarr;
      </Link>
    </div>
  );
}
