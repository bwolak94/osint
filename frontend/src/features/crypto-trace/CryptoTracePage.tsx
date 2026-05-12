import { useState } from "react";
import { Bitcoin, Search, AlertTriangle, ArrowRight, ArrowLeft } from "lucide-react";
import { useCryptoTrace } from "./hooks";
import { Badge } from "@/shared/components/Badge";
import { Button } from "@/shared/components/Button";
import { Input } from "@/shared/components/Input";
import { Card, CardBody, CardHeader } from "@/shared/components/Card";

const riskVariant: Record<string, "danger" | "warning" | "info" | "neutral"> = {
  critical: "danger",
  high: "danger",
  medium: "warning",
  low: "neutral",
};

const riskColor = (score: number): string =>
  score > 80
    ? "var(--danger-400)"
    : score > 60
    ? "var(--warning-400)"
    : score > 40
    ? "var(--brand-400)"
    : "var(--success-400)";

export function CryptoTracePage() {
  const [address, setAddress] = useState("");
  const [currency, setCurrency] = useState("BTC");
  const trace = useCryptoTrace();

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3">
        <Bitcoin className="h-6 w-6" style={{ color: "var(--warning-400)" }} />
        <h1
          className="text-xl font-semibold"
          style={{ color: "var(--text-primary)" }}
        >
          Cryptocurrency Tracing
        </h1>
      </div>

      <Card>
        <CardBody>
          <div className="flex gap-3 flex-wrap">
            <div className="flex-1">
              <Input
                placeholder="Wallet address (BTC, ETH, etc.)..."
                prefixIcon={<Search className="h-4 w-4" />}
                value={address}
                onChange={(e) => setAddress(e.target.value)}
                onKeyDown={(e) =>
                  e.key === "Enter" &&
                  address.trim() &&
                  trace.mutate({ address: address.trim(), currency })
                }
              />
            </div>
            <select
              value={currency}
              onChange={(e) => setCurrency(e.target.value)}
              className="rounded-md border px-3 py-2 text-sm"
              style={{
                background: "var(--bg-surface)",
                borderColor: "var(--border-default)",
                color: "var(--text-primary)",
              }}
            >
              {["BTC", "ETH", "LTC", "XMR", "USDT"].map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
            <Button
              onClick={() => trace.mutate({ address: address.trim(), currency })}
              disabled={!address.trim() || trace.isPending}
              leftIcon={<Bitcoin className="h-4 w-4" />}
            >
              {trace.isPending ? "Tracing..." : "Trace Address"}
            </Button>
          </div>
        </CardBody>
      </Card>

      {trace.data && (
        <div className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {[
              {
                label: "Balance",
                value: `${trace.data.address_info.balance} ${currency}`,
              },
              {
                label: "Total Received",
                value: `${trace.data.address_info.total_received} ${currency}`,
              },
              {
                label: "Transactions",
                value: trace.data.address_info.tx_count,
              },
              {
                label: "Cluster Size",
                value: trace.data.address_info.cluster_size,
              },
            ].map(({ label, value }) => (
              <div
                key={label}
                className="rounded-xl border p-4 text-center"
                style={{
                  background: "var(--bg-surface)",
                  borderColor: "var(--border-subtle)",
                }}
              >
                <p
                  className="text-xl font-bold"
                  style={{ color: "var(--text-primary)" }}
                >
                  {value}
                </p>
                <p
                  className="text-xs mt-1"
                  style={{ color: "var(--text-tertiary)" }}
                >
                  {label}
                </p>
              </div>
            ))}
          </div>

          <div className="grid gap-4 md:grid-cols-3">
            <div
              className="rounded-2xl border p-6 text-center"
              style={{
                background: "var(--bg-surface)",
                borderColor: "var(--border-default)",
              }}
            >
              <div
                className="text-5xl font-bold mb-1"
                style={{
                  color: riskColor(trace.data.address_info.risk_score),
                }}
              >
                {trace.data.address_info.risk_score}
              </div>
              <p
                className="text-xs mb-2"
                style={{ color: "var(--text-tertiary)" }}
              >
                Risk Score
              </p>
              <Badge
                variant={
                  riskVariant[trace.data.address_info.risk_level] ?? "neutral"
                }
              >
                {trace.data.address_info.risk_level.toUpperCase()}
              </Badge>
              {trace.data.address_info.labels.length > 0 && (
                <div className="flex flex-wrap justify-center gap-1 mt-3">
                  {trace.data.address_info.labels.map((l) => (
                    <Badge key={l} variant="danger" size="sm">
                      {l}
                    </Badge>
                  ))}
                </div>
              )}
            </div>

            <div className="md:col-span-2 space-y-3">
              {trace.data.risk_indicators.length > 0 && (
                <div
                  className="rounded-lg border p-3"
                  style={{
                    background: "var(--danger-900)",
                    borderColor: "var(--danger-500)",
                  }}
                >
                  <p
                    className="text-xs font-semibold mb-2"
                    style={{ color: "var(--danger-400)" }}
                  >
                    Risk Indicators
                  </p>
                  {trace.data.risk_indicators.map((r, i) => (
                    <div
                      key={i}
                      className="flex items-start gap-2 text-xs"
                      style={{ color: "var(--danger-300)" }}
                    >
                      <AlertTriangle className="h-3 w-3 mt-0.5 shrink-0" />
                      {r}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          <Card>
            <CardHeader>
              <h3
                className="text-sm font-semibold"
                style={{ color: "var(--text-primary)" }}
              >
                Transaction History ({trace.data.transactions.length})
              </h3>
            </CardHeader>
            <div
              className="divide-y"
              style={{ borderColor: "var(--border-subtle)" }}
            >
              {trace.data.transactions.map((tx) => (
                <div key={tx.txid} className="px-4 py-3">
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex items-center gap-2 min-w-0">
                      {tx.from_address === address ? (
                        <ArrowRight
                          className="h-3 w-3 shrink-0"
                          style={{ color: "var(--danger-400)" }}
                        />
                      ) : (
                        <ArrowLeft
                          className="h-3 w-3 shrink-0"
                          style={{ color: "var(--success-400)" }}
                        />
                      )}
                      <span
                        className="font-mono text-xs truncate"
                        style={{ color: "var(--text-secondary)" }}
                      >
                        {tx.txid.slice(0, 16)}...
                      </span>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      {tx.is_mixer && (
                        <Badge variant="danger" size="sm">
                          Mixer
                        </Badge>
                      )}
                      {tx.is_exchange && (
                        <Badge variant="info" size="sm">
                          Exchange
                        </Badge>
                      )}
                      <span
                        className="text-sm font-medium"
                        style={{ color: riskColor(tx.risk_score) }}
                      >
                        {tx.amount} {currency}
                      </span>
                      <span
                        className="text-xs"
                        style={{ color: "var(--text-tertiary)" }}
                      >
                        ${tx.usd_value.toLocaleString()}
                      </span>
                    </div>
                  </div>
                  <p
                    className="text-xs mt-1"
                    style={{ color: "var(--text-tertiary)" }}
                  >
                    Block {tx.block_height} &middot;{" "}
                    {new Date(tx.timestamp).toLocaleDateString()}
                  </p>
                </div>
              ))}
            </div>
          </Card>
        </div>
      )}

      {!trace.data && !trace.isPending && (
        <div
          className="rounded-xl border py-16 text-center"
          style={{ borderColor: "var(--border-subtle)" }}
        >
          <Bitcoin
            className="mx-auto h-10 w-10 mb-3"
            style={{ color: "var(--text-tertiary)" }}
          />
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
            Trace cryptocurrency transactions and wallet risk
          </p>
        </div>
      )}
    </div>
  );
}
