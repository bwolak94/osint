import { useState } from "react";
import { Card, CardBody } from "@/shared/components/Card";
import { Button } from "@/shared/components/Button";
import { Badge } from "@/shared/components/Badge";
import { Check, X } from "lucide-react";

interface PricingTableProps {
  currentTier: string;
  onUpgrade: (tier: string, period: string) => void;
}

const features = [
  { name: "Investigations/month", free: "3", pro: "Unlimited", enterprise: "Unlimited" },
  { name: "Email scan (Holehe)", free: true, pro: true, enterprise: true },
  { name: "Username scan (Maigret)", free: "5/day", pro: true, enterprise: true },
  { name: "Playwright (JS sites)", free: false, pro: true, enterprise: true },
  { name: "OCR / PDF analysis", free: false, pro: true, enterprise: true },
  { name: "Graph export", free: false, pro: true, enterprise: true },
  { name: "API access", free: false, pro: true, enterprise: true },
  { name: "Team members", free: "1", pro: "5", enterprise: "Unlimited" },
  { name: "Custom scanners", free: false, pro: false, enterprise: true },
  { name: "Priority support", free: false, pro: false, enterprise: true },
];

const prices = {
  pro: { monthly: "$29.99", yearly: "$24.99" },
  enterprise: { monthly: "$99.99", yearly: "$83.33" },
};

export function PricingTable({ currentTier, onUpgrade }: PricingTableProps) {
  const [period, setPeriod] = useState<"monthly" | "yearly">("monthly");

  return (
    <div className="space-y-4">
      {/* Period toggle */}
      <div className="flex items-center justify-center gap-2">
        <div className="flex rounded-lg border p-0.5" style={{ borderColor: "var(--border-default)" }}>
          <button
            onClick={() => setPeriod("monthly")}
            className={`rounded-md px-4 py-1.5 text-sm font-medium transition-colors ${
              period === "monthly" ? "bg-bg-overlay text-text-primary" : "text-text-tertiary"
            }`}
          >
            Monthly
          </button>
          <button
            onClick={() => setPeriod("yearly")}
            className={`flex items-center gap-1.5 rounded-md px-4 py-1.5 text-sm font-medium transition-colors ${
              period === "yearly" ? "bg-bg-overlay text-text-primary" : "text-text-tertiary"
            }`}
          >
            Yearly
            <Badge variant="success" size="sm">-20%</Badge>
          </button>
        </div>
      </div>

      {/* Plans grid */}
      <div className="grid gap-4 md:grid-cols-3">
        {/* Free */}
        <Card>
          <CardBody className="space-y-4">
            <div>
              <h3 className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>Free</h3>
              <div className="mt-2">
                <span className="text-3xl font-bold" style={{ color: "var(--text-primary)" }}>$0</span>
                <span className="text-sm" style={{ color: "var(--text-secondary)" }}> forever</span>
              </div>
            </div>
            <Button variant="secondary" className="w-full" disabled={currentTier === "free"}>
              {currentTier === "free" ? "Current Plan" : "Downgrade"}
            </Button>
            <FeatureList features={features} tier="free" />
          </CardBody>
        </Card>

        {/* Pro */}
        <Card className="ring-1 ring-brand-500/50">
          <CardBody className="space-y-4">
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>Pro</h3>
                <Badge variant="brand" size="sm">Popular</Badge>
              </div>
              <div className="mt-2">
                <span className="text-3xl font-bold" style={{ color: "var(--text-primary)" }}>
                  {prices.pro[period]}
                </span>
                <span className="text-sm" style={{ color: "var(--text-secondary)" }}> /month</span>
              </div>
              {period === "yearly" && (
                <p className="text-xs" style={{ color: "var(--success-500)" }}>
                  Billed ${period === "yearly" ? "299.99" : ""}/year · Save $60
                </p>
              )}
            </div>
            <Button
              className="w-full"
              disabled={currentTier === "pro"}
              onClick={() => onUpgrade("pro", period)}
            >
              {currentTier === "pro" ? "Current Plan" : "Upgrade to Pro"}
            </Button>
            <FeatureList features={features} tier="pro" />
          </CardBody>
        </Card>

        {/* Enterprise */}
        <Card>
          <CardBody className="space-y-4">
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>Enterprise</h3>
                <Badge variant="warning" size="sm">Premium</Badge>
              </div>
              <div className="mt-2">
                <span className="text-3xl font-bold" style={{ color: "var(--text-primary)" }}>
                  {prices.enterprise[period]}
                </span>
                <span className="text-sm" style={{ color: "var(--text-secondary)" }}> /month</span>
              </div>
              {period === "yearly" && (
                <p className="text-xs" style={{ color: "var(--success-500)" }}>
                  Billed $999.99/year · Save $200
                </p>
              )}
            </div>
            <Button
              className="w-full"
              disabled={currentTier === "enterprise"}
              onClick={() => onUpgrade("enterprise", period)}
            >
              {currentTier === "enterprise" ? "Current Plan" : "Upgrade"}
            </Button>
            <FeatureList features={features} tier="enterprise" />
          </CardBody>
        </Card>
      </div>

      {/* Crypto note */}
      <p className="text-center text-xs" style={{ color: "var(--text-tertiary)" }}>
        All payments processed via cryptocurrency (BTC, ETH, USDT, and 200+ currencies)
      </p>
    </div>
  );
}

type FeatureItem = { name: string; [key: string]: string | boolean }
function FeatureList({ features, tier }: { features: FeatureItem[]; tier: string }) {
  return (
    <ul className="space-y-2 border-t pt-4" style={{ borderColor: "var(--border-subtle)" }}>
      {features.map((f) => {
        const val = f[tier as keyof typeof f];
        const available = val !== false;
        return (
          <li key={f.name} className="flex items-center gap-2 text-sm">
            {available ? (
              <Check className="h-4 w-4 shrink-0" style={{ color: "var(--brand-500)" }} />
            ) : (
              <X className="h-4 w-4 shrink-0" style={{ color: "var(--text-tertiary)" }} />
            )}
            <span style={{ color: available ? "var(--text-secondary)" : "var(--text-tertiary)" }}>
              {f.name}
              {typeof val === "string" && <span className="ml-1 font-medium" style={{ color: "var(--text-primary)" }}>({val})</span>}
            </span>
          </li>
        );
      })}
    </ul>
  );
}
