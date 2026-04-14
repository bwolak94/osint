import { useState } from "react";
import { useForm } from "react-hook-form";
import { Plus } from "lucide-react";
import { usePayments, useCreatePayment } from "./hooks";
import type { CreatePaymentRequest } from "./types";
import { Button } from "@/shared/components/Button";
import { Input } from "@/shared/components/Input";
import { LoadingSpinner } from "@/shared/components/LoadingSpinner";

export function PaymentsPage() {
  const [showForm, setShowForm] = useState(false);
  const { data, isLoading } = usePayments();
  const createMutation = useCreatePayment();

  const { register, handleSubmit, reset } = useForm<CreatePaymentRequest>();

  const onSubmit = (formData: CreatePaymentRequest) => {
    createMutation.mutate(formData, {
      onSuccess: () => {
        reset();
        setShowForm(false);
      },
    });
  };

  if (isLoading) return <LoadingSpinner />;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Payments</h1>
        <Button onClick={() => setShowForm(!showForm)}>
          <Plus className="mr-2 h-4 w-4" />
          New Payment
        </Button>
      </div>

      {showForm && (
        <form
          onSubmit={handleSubmit(onSubmit)}
          className="space-y-4 rounded-lg border border-gray-800 bg-gray-900 p-6"
        >
          <Input
            label="Amount"
            type="number"
            step="0.01"
            {...register("amount", { valueAsNumber: true })}
          />
          <Input
            label="Currency"
            placeholder="USD"
            {...register("currency")}
          />
          <Input label="Description" {...register("description")} />
          <div className="flex gap-2">
            <Button type="submit" disabled={createMutation.isPending}>
              {createMutation.isPending ? "Processing..." : "Create Payment"}
            </Button>
            <Button variant="secondary" onClick={() => setShowForm(false)}>
              Cancel
            </Button>
          </div>
        </form>
      )}

      <div className="overflow-hidden rounded-lg border border-gray-800">
        <table className="w-full text-left text-sm">
          <thead className="bg-gray-900 text-gray-400">
            <tr>
              <th className="px-4 py-3">Date</th>
              <th className="px-4 py-3">Description</th>
              <th className="px-4 py-3">Amount</th>
              <th className="px-4 py-3">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-800">
            {data?.items.map((payment) => (
              <tr key={payment.id} className="bg-gray-950">
                <td className="px-4 py-3 text-gray-300">
                  {new Date(payment.created_at).toLocaleDateString()}
                </td>
                <td className="px-4 py-3 text-gray-300">
                  {payment.description}
                </td>
                <td className="px-4 py-3 text-white">
                  {payment.amount} {payment.currency}
                </td>
                <td className="px-4 py-3">
                  <span className="rounded-full bg-gray-800 px-2 py-1 text-xs text-gray-300">
                    {payment.status}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {data?.items.length === 0 && (
          <p className="p-6 text-center text-gray-500">No payments yet.</p>
        )}
      </div>
    </div>
  );
}
