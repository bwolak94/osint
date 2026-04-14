export type PaymentStatus = "pending" | "completed" | "failed" | "refunded";

export interface Payment {
  id: string;
  amount: number;
  currency: string;
  status: PaymentStatus;
  description: string;
  created_at: string;
}

export interface CreatePaymentRequest {
  amount: number;
  currency: string;
  description: string;
}
