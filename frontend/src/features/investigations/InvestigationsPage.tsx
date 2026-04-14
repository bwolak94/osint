import { useState } from "react";
import { Link } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Plus } from "lucide-react";
import { useInvestigations, useCreateInvestigation } from "./hooks";
import {
  createInvestigationSchema,
  type CreateInvestigationFormData,
} from "./schemas";
import { Button } from "@/shared/components/Button";
import { Input } from "@/shared/components/Input";
import { LoadingSpinner } from "@/shared/components/LoadingSpinner";

export function InvestigationsPage() {
  const [showForm, setShowForm] = useState(false);
  const { data, isLoading } = useInvestigations();
  const createMutation = useCreateInvestigation();

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<CreateInvestigationFormData>({
    resolver: zodResolver(createInvestigationSchema),
  });

  const onSubmit = (formData: CreateInvestigationFormData) => {
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
        <h1 className="text-2xl font-bold text-white">Investigations</h1>
        <Button onClick={() => setShowForm(!showForm)}>
          <Plus className="mr-2 h-4 w-4" />
          New Investigation
        </Button>
      </div>

      {showForm && (
        <form
          onSubmit={handleSubmit(onSubmit)}
          className="space-y-4 rounded-lg border border-gray-800 bg-gray-900 p-6"
        >
          <Input
            label="Title"
            error={errors.title?.message}
            {...register("title")}
          />
          <Input
            label="Description"
            error={errors.description?.message}
            {...register("description")}
          />
          <div className="flex gap-2">
            <Button type="submit" disabled={createMutation.isPending}>
              {createMutation.isPending ? "Creating..." : "Create"}
            </Button>
            <Button variant="secondary" onClick={() => setShowForm(false)}>
              Cancel
            </Button>
          </div>
        </form>
      )}

      <div className="grid gap-4">
        {data?.items.map((investigation) => (
          <Link
            key={investigation.id}
            to={`/investigations/${investigation.id}`}
            className="block rounded-lg border border-gray-800 bg-gray-900 p-6 transition-colors hover:border-gray-700"
          >
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold text-white">
                {investigation.title}
              </h2>
              <span className="rounded-full bg-gray-800 px-3 py-1 text-xs text-gray-300">
                {investigation.status}
              </span>
            </div>
            {investigation.description && (
              <p className="mt-2 text-sm text-gray-400">
                {investigation.description}
              </p>
            )}
            <p className="mt-2 text-xs text-gray-500">
              Created: {new Date(investigation.created_at).toLocaleDateString()}
            </p>
          </Link>
        ))}

        {data?.items.length === 0 && (
          <p className="text-center text-gray-500">
            No investigations yet. Create one to get started.
          </p>
        )}
      </div>
    </div>
  );
}
