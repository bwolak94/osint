import { useState } from "react";
import { Card, CardBody, CardHeader } from "@/shared/components/Card";
import { Button } from "@/shared/components/Button";
import { Badge } from "@/shared/components/Badge";
import { ProgressBar } from "@/shared/components/ProgressBar";
import { Check, Zap, Building2, CreditCard } from "lucide-react";
import { useAuth } from "@/shared/hooks/useAuth";
import { PricingTable } from "./PricingTable";
import { PaymentModal } from "./PaymentModal";
import { PaymentHistory } from "./PaymentHistory";

export function PaymentsPage() {
  const { user, isPro, isEnterprise } = useAuth();
  const [showPaymentModal, setShowPaymentModal] = useState(false);
  const [selectedPlan, setSelectedPlan] = useState<{ tier: string; period: string } | null>(null);

  const currentTier = user?.subscription_tier ?? "free";
  const tierLabel = { free: "Free", pro: "Pro", enterprise: "Enterprise" }[currentTier] ?? "Free";
  const tierBadgeVariant = { free: "neutral", pro: "brand", enterprise: "warning" }[currentTier] as any ?? "neutral";

  const handleUpgrade = (tier: string, period: string) => {
    setSelectedPlan({ tier, period });
    setShowPaymentModal(true);
  };

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>Billing</h1>
        <p className="text-sm" style={{ color: "var(--text-secondary)" }}>Manage your subscription and payments</p>
      </div>

      {/* Current plan */}
      <Card>
        <CardBody>
          <div className="flex items-start justify-between">
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>{tierLabel} Plan</h2>
                <Badge variant={tierBadgeVariant} dot>Active</Badge>
              </div>
              {isPro && (
                <p className="mt-1 text-sm" style={{ color: "var(--text-secondary)" }}>
                  $29.99/month · Renews on March 15, 2025
                </p>
              )}
              {isEnterprise && (
                <p className="mt-1 text-sm" style={{ color: "var(--text-secondary)" }}>
                  $99.99/month · Renews on March 15, 2025
                </p>
              )}
              {!isPro && !isEnterprise && (
                <p className="mt-1 text-sm" style={{ color: "var(--text-secondary)" }}>
                  Limited features · Upgrade to unlock more
                </p>
              )}
            </div>
            {!isEnterprise && (
              <Button onClick={() => handleUpgrade(isPro ? "enterprise" : "pro", "monthly")}>
                {isPro ? "Upgrade to Enterprise" : "Upgrade to Pro"}
              </Button>
            )}
          </div>

          {/* Usage meters */}
          <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {[
              { label: "Investigations", value: 2, max: currentTier === "free" ? 3 : -1 },
              { label: "Scans Today", value: 8, max: currentTier === "free" ? 5 : -1 },
              { label: "Graph Nodes", value: 312, max: -1 },
              { label: "Storage", value: 2.3, max: currentTier === "free" ? 1 : 10, unit: "GB" },
            ].map((m) => (
              <div key={m.label} className="rounded-md border p-3" style={{ borderColor: "var(--border-subtle)", background: "var(--bg-elevated)" }}>
                <p className="text-xs font-medium" style={{ color: "var(--text-tertiary)" }}>{m.label}</p>
                <p className="mt-1 text-lg font-bold font-mono" style={{ color: "var(--text-primary)" }}>
                  {m.value}{m.unit ? ` ${m.unit}` : ""}
                  <span className="text-xs font-normal" style={{ color: "var(--text-tertiary)" }}>
                    {m.max > 0 ? ` / ${m.max}${m.unit ? ` ${m.unit}` : ""}` : " / unlimited"}
                  </span>
                </p>
                {m.max > 0 && (
                  <div className="mt-1">
                    <ProgressBar value={m.value} max={m.max} showPercentage={false} size="sm" />
                  </div>
                )}
              </div>
            ))}
          </div>
        </CardBody>
      </Card>

      {/* Pricing table */}
      {!isEnterprise && <PricingTable currentTier={currentTier} onUpgrade={handleUpgrade} />}

      {/* Payment history */}
      <PaymentHistory />

      {/* Payment modal */}
      {showPaymentModal && selectedPlan && (
        <PaymentModal
          tier={selectedPlan.tier}
          period={selectedPlan.period}
          onClose={() => { setShowPaymentModal(false); setSelectedPlan(null); }}
        />
      )}
    </div>
  );
}
