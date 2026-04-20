export interface PaymentOrder {
  order_id: string;
  payment_url: string;
  payment_id: string;
  amount_usd: string;
  pay_currency: string;
  expires_at: string | null;
}

export interface PaymentStatus {
  order_id: string;
  status: "pending" | "waiting" | "confirming" | "confirmed" | "finished" | "failed" | "expired";
  subscription_tier: string;
  amount_usd: string;
  amount_crypto: string | null;
  crypto_currency: string | null;
  subscription_activated_at: string | null;
  subscription_expires_at: string | null;
  created_at: string;
}

export interface PaymentHistoryResponse {
  payments: PaymentStatus[];
  total: number;
}

export type CryptoCurrency = "BTC" | "ETH" | "USDT" | "USDC" | "SOL" | "BNB" | "DOGE" | "LTC";
