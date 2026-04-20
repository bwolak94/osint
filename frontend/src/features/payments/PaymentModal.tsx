import { useState, useEffect } from "react";
import { X, Bitcoin, CheckCircle2, Clock, AlertTriangle, Copy, Check, HelpCircle } from "lucide-react";
import { motion } from "framer-motion";
import { Button } from "@/shared/components/Button";
import { Badge } from "@/shared/components/Badge";
import { Card, CardBody } from "@/shared/components/Card";
import { ProgressBar } from "@/shared/components/ProgressBar";

interface PaymentModalProps {
  tier: string;
  period: string;
  onClose: () => void;
}

const currencies = [
  { code: "BTC", name: "Bitcoin", icon: "\u20bf" },
  { code: "ETH", name: "Ethereum", icon: "\u039e" },
  { code: "USDT", name: "Tether", icon: "\u20ae" },
  { code: "USDC", name: "USD Coin", icon: "$" },
  { code: "SOL", name: "Solana", icon: "\u25ce" },
  { code: "BNB", name: "BNB", icon: "B" },
  { code: "DOGE", name: "Dogecoin", icon: "\u00d0" },
  { code: "LTC", name: "Litecoin", icon: "\u0141" },
];

const prices: Record<string, Record<string, string>> = {
  pro: { monthly: "29.99", yearly: "299.99" },
  enterprise: { monthly: "99.99", yearly: "999.99" },
};

type Step = "currency" | "payment" | "success" | "expired";

export function PaymentModal({ tier, period, onClose }: PaymentModalProps) {
  const [step, setStep] = useState<Step>("currency");
  const [selectedCurrency, setSelectedCurrency] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [showHelp, setShowHelp] = useState(false);
  const [countdown, setCountdown] = useState(1800); // 30 min
  const [confirmations, setConfirmations] = useState(0);

  const priceUsd = prices[tier]?.[period] ?? "29.99";

  // Countdown timer
  useEffect(() => {
    if (step !== "payment") return;
    const interval = setInterval(() => {
      setCountdown((c) => {
        if (c <= 1) { setStep("expired"); return 0; }
        return c - 1;
      });
    }, 1000);
    return () => clearInterval(interval);
  }, [step]);

  // Simulate payment status polling
  useEffect(() => {
    if (step !== "payment") return;
    const timeout = setTimeout(() => {
      setConfirmations(1);
      setTimeout(() => { setConfirmations(2); }, 3000);
      setTimeout(() => { setConfirmations(3); setStep("success"); }, 6000);
    }, 10000);
    return () => clearTimeout(timeout);
  }, [step]);

  const mockAddress = "bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh";
  const mockCryptoAmount = selectedCurrency === "BTC" ? "0.000412" : selectedCurrency === "ETH" ? "0.0089" : "29.99";

  const copyAddress = async () => {
    await navigator.clipboard.writeText(mockAddress);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const formatTime = (s: number) => `${Math.floor(s / 60)}:${(s % 60).toString().padStart(2, "0")}`;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm" onClick={onClose}>
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        className="w-full max-w-md rounded-xl border shadow-lg"
        style={{ background: "var(--bg-surface)", borderColor: "var(--border-default)" }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b px-6 py-4" style={{ borderColor: "var(--border-subtle)" }}>
          <div>
            <h2 className="text-base font-semibold" style={{ color: "var(--text-primary)" }}>
              {step === "success" ? "Payment Confirmed" : step === "expired" ? "Payment Expired" : `Upgrade to ${tier.charAt(0).toUpperCase() + tier.slice(1)}`}
            </h2>
            <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>${priceUsd} / {period}</p>
          </div>
          <button onClick={onClose} className="rounded-md p-1 hover:bg-bg-overlay"><X className="h-4 w-4" style={{ color: "var(--text-secondary)" }} /></button>
        </div>

        <div className="px-6 py-5">
          {/* Step: Currency selection */}
          {step === "currency" && (
            <div className="space-y-4">
              <p className="text-sm" style={{ color: "var(--text-secondary)" }}>Select your preferred cryptocurrency</p>
              <div className="grid grid-cols-4 gap-2">
                {currencies.map((c) => (
                  <button
                    key={c.code}
                    onClick={() => setSelectedCurrency(c.code)}
                    className={`flex flex-col items-center gap-1 rounded-lg border p-3 text-center transition-all ${
                      selectedCurrency === c.code
                        ? "border-brand-500 bg-brand-900/30"
                        : "border-border hover:bg-bg-overlay"
                    }`}
                  >
                    <span className="text-lg">{c.icon}</span>
                    <span className="text-[10px] font-medium" style={{ color: "var(--text-secondary)" }}>{c.code}</span>
                  </button>
                ))}
              </div>
              {selectedCurrency && (
                <div className="text-center">
                  <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>
                    Estimated: <span className="font-mono font-medium" style={{ color: "var(--text-primary)" }}>{mockCryptoAmount} {selectedCurrency}</span> at current rate
                  </p>
                </div>
              )}
              <Button className="w-full" disabled={!selectedCurrency} onClick={() => setStep("payment")}>
                Continue with {selectedCurrency ?? "..."}
              </Button>

              {/* Help section */}
              <button onClick={() => setShowHelp(!showHelp)} className="flex w-full items-center gap-1 text-xs" style={{ color: "var(--text-tertiary)" }}>
                <HelpCircle className="h-3 w-3" /> How to pay with crypto?
              </button>
              {showHelp && (
                <div className="rounded-md p-3 text-xs space-y-1" style={{ background: "var(--bg-elevated)", color: "var(--text-secondary)" }}>
                  <p>1. Select your cryptocurrency above</p>
                  <p>2. You'll receive a unique payment address</p>
                  <p>3. Send the exact amount from your wallet</p>
                  <p>4. Wait for blockchain confirmation (1-30 min)</p>
                  <p>5. Your subscription activates automatically</p>
                </div>
              )}
            </div>
          )}

          {/* Step: Payment details */}
          {step === "payment" && (
            <div className="space-y-4 text-center">
              <div>
                <p className="text-sm font-medium" style={{ color: "var(--text-secondary)" }}>Send exactly</p>
                <p className="mt-1 text-2xl font-bold font-mono" style={{ color: "var(--text-primary)" }}>
                  {mockCryptoAmount} {selectedCurrency}
                </p>
              </div>

              {/* QR placeholder */}
              <div className="mx-auto flex h-48 w-48 items-center justify-center rounded-lg border-2 border-dashed" style={{ borderColor: "var(--border-default)" }}>
                <span className="text-xs" style={{ color: "var(--text-tertiary)" }}>QR Code</span>
              </div>

              {/* Address */}
              <div className="rounded-md p-2" style={{ background: "var(--bg-elevated)" }}>
                <p className="break-all font-mono text-xs" style={{ color: "var(--text-primary)" }}>{mockAddress}</p>
              </div>
              <Button variant="secondary" size="sm" onClick={copyAddress} leftIcon={copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}>
                {copied ? "Copied" : "Copy Address"}
              </Button>

              {/* Status */}
              <div className="space-y-2 rounded-md p-3" style={{ background: "var(--bg-elevated)" }}>
                {confirmations === 0 ? (
                  <div className="flex items-center justify-center gap-2">
                    <span className="inline-block h-2 w-2 animate-pulse rounded-full" style={{ background: "var(--warning-500)" }} />
                    <span className="text-sm" style={{ color: "var(--warning-500)" }}>Waiting for payment...</span>
                  </div>
                ) : (
                  <div className="space-y-1">
                    <div className="flex items-center justify-center gap-2">
                      <span className="inline-block h-2 w-2 animate-pulse rounded-full" style={{ background: "var(--info-500)" }} />
                      <span className="text-sm" style={{ color: "var(--info-500)" }}>Confirming ({confirmations}/3)</span>
                    </div>
                    <ProgressBar value={confirmations} max={3} showPercentage={false} size="sm" />
                  </div>
                )}
                <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>
                  Expires in {formatTime(countdown)}
                </p>
              </div>
            </div>
          )}

          {/* Step: Success */}
          {step === "success" && (
            <div className="space-y-4 text-center py-4">
              <CheckCircle2 className="mx-auto h-16 w-16" style={{ color: "var(--success-500)" }} />
              <div>
                <p className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>Payment Confirmed!</p>
                <p className="mt-1 text-sm" style={{ color: "var(--text-secondary)" }}>
                  Your {tier.charAt(0).toUpperCase() + tier.slice(1)} subscription is now active.
                </p>
              </div>
              <Button className="w-full" onClick={onClose}>Continue to Dashboard</Button>
            </div>
          )}

          {/* Step: Expired */}
          {step === "expired" && (
            <div className="space-y-4 text-center py-4">
              <AlertTriangle className="mx-auto h-16 w-16" style={{ color: "var(--warning-500)" }} />
              <div>
                <p className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>Payment Expired</p>
                <p className="mt-1 text-sm" style={{ color: "var(--text-secondary)" }}>
                  The payment window has expired. Please create a new payment.
                </p>
              </div>
              <Button className="w-full" onClick={() => { setStep("currency"); setCountdown(1800); }}>Try Again</Button>
            </div>
          )}
        </div>
      </motion.div>
    </div>
  );
}
