import { Card, CardBody, CardHeader } from "@/shared/components/Card";
import { Badge } from "@/shared/components/Badge";
import { EmptyState } from "@/shared/components/EmptyState";
import { Button } from "@/shared/components/Button";
import { Download, Loader2 } from "lucide-react";
import { usePaymentHistory } from "./hooks";

const statusVariant: Record<string, "success" | "warning" | "danger" | "neutral"> = {
  finished: "success",
  pending: "warning",
  waiting: "warning",
  confirming: "warning",
  failed: "danger",
  expired: "neutral",
};

export function PaymentHistory() {
  const { data, isLoading } = usePaymentHistory();
  const payments = data?.payments ?? [];

  if (isLoading) {
    return (
      <Card>
        <CardBody>
          <div className="flex items-center justify-center py-10">
            <Loader2 className="h-6 w-6 animate-spin" style={{ color: "var(--brand-500)" }} />
          </div>
        </CardBody>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader className="flex items-center justify-between">
        <h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Payment History</h2>
        {payments.length > 0 && (
          <Button variant="ghost" size="sm" leftIcon={<Download className="h-3.5 w-3.5" />}>Export CSV</Button>
        )}
      </CardHeader>
      <CardBody className="p-0">
        {payments.length === 0 ? (
          <div className="p-6">
            <EmptyState title="No payment history" description="Your payment transactions will appear here" />
          </div>
        ) : (
          <table className="w-full">
            <thead>
              <tr className="border-b text-left text-xs font-medium" style={{ borderColor: "var(--border-subtle)", color: "var(--text-tertiary)" }}>
                <th className="px-5 py-3">Date</th>
                <th className="px-5 py-3">Tier</th>
                <th className="px-5 py-3">Amount</th>
                <th className="px-5 py-3">Crypto</th>
                <th className="px-5 py-3">Status</th>
              </tr>
            </thead>
            <tbody>
              {payments.map((p) => (
                <tr key={p.order_id} className="border-b" style={{ borderColor: "var(--border-subtle)" }}>
                  <td className="px-5 py-3 text-sm" style={{ color: "var(--text-secondary)" }}>
                    {p.subscription_activated_at
                      ? new Date(p.subscription_activated_at).toLocaleDateString()
                      : "—"}
                  </td>
                  <td className="px-5 py-3 text-sm font-medium" style={{ color: "var(--text-primary)" }}>
                    {p.subscription_tier}
                  </td>
                  <td className="px-5 py-3 text-sm font-mono" style={{ color: "var(--text-primary)" }}>
                    ${p.amount_usd}
                  </td>
                  <td className="px-5 py-3 text-sm font-mono" style={{ color: "var(--text-secondary)" }}>
                    {p.amount_crypto && p.crypto_currency
                      ? `${p.amount_crypto} ${p.crypto_currency}`
                      : "—"}
                  </td>
                  <td className="px-5 py-3">
                    <Badge variant={statusVariant[p.status] ?? "neutral"} size="sm" dot>{p.status}</Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </CardBody>
    </Card>
  );
}
