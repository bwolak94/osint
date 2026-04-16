import { useQuery, useMutation } from "@tanstack/react-query";
import { apiClient } from "@/shared/api/client";

interface PaymentOrder {
  order_id: string;
  payment_url: string;
  payment_id: string;
  amount_usd: string;
  pay_currency: string;
  expires_at: string | null;
}

interface PaymentStatus {
  order_id: string;
  status: string;
  subscription_tier: string;
  amount_usd: string;
  amount_crypto: string | null;
  crypto_currency: string | null;
  subscription_activated_at: string | null;
  subscription_expires_at: string | null;
}

export function useCreatePayment() {
  return useMutation({
    mutationFn: async (data: { subscription_tier: string; billing_period: string; pay_currency: string }) => {
      const res = await apiClient.post<PaymentOrder>("/payments/create", data);
      return res.data;
    },
  });
}

export function usePaymentStatus(orderId: string | null) {
  return useQuery({
    queryKey: ["payment-status", orderId],
    queryFn: async () => {
      const res = await apiClient.get<PaymentStatus>(`/payments/status/${orderId}`);
      return res.data;
    },
    enabled: !!orderId,
    refetchInterval: 15000,
  });
}

export function usePaymentHistory() {
  return useQuery({
    queryKey: ["payment-history"],
    queryFn: async () => {
      const res = await apiClient.get<{ payments: PaymentStatus[]; total: number }>("/payments/history");
      return res.data;
    },
  });
}

export function useSupportedCurrencies() {
  return useQuery({
    queryKey: ["currencies"],
    queryFn: async () => {
      const res = await apiClient.get<{ currencies: string[] }>("/payments/currencies");
      return res.data.currencies;
    },
    staleTime: 60 * 60 * 1000, // 1 hour
  });
}
