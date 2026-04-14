import { useParams, Link } from "react-router-dom";
import { ArrowLeft, Network } from "lucide-react";
import { useInvestigation } from "./hooks";
import { Button } from "@/shared/components/Button";
import { LoadingSpinner } from "@/shared/components/LoadingSpinner";

export function InvestigationDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { data: investigation, isLoading } = useInvestigation(id!);

  if (isLoading) return <LoadingSpinner />;
  if (!investigation) return <p className="text-gray-400">Not found.</p>;

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Link to="/investigations">
          <ArrowLeft className="h-5 w-5 text-gray-400 hover:text-white" />
        </Link>
        <h1 className="text-2xl font-bold text-white">
          {investigation.title}
        </h1>
        <span className="rounded-full bg-gray-800 px-3 py-1 text-xs text-gray-300">
          {investigation.status}
        </span>
      </div>

      {investigation.description && (
        <p className="text-gray-400">{investigation.description}</p>
      )}

      <div className="flex gap-2">
        <Link to={`/graph/${investigation.id}`}>
          <Button variant="secondary">
            <Network className="mr-2 h-4 w-4" />
            View Graph
          </Button>
        </Link>
      </div>

      <div>
        <h2 className="mb-4 text-lg font-semibold text-white">Identities</h2>
        {investigation.identities.length === 0 ? (
          <p className="text-sm text-gray-500">No identities found yet.</p>
        ) : (
          <div className="grid gap-3">
            {investigation.identities.map((identity) => (
              <div
                key={identity.id}
                className="rounded-lg border border-gray-800 bg-gray-900 p-4"
              >
                <div className="flex items-center justify-between">
                  <span className="font-medium text-white">
                    {identity.username}
                  </span>
                  <span className="rounded bg-gray-800 px-2 py-1 text-xs text-gray-400">
                    {identity.platform}
                  </span>
                </div>
                <p className="mt-1 text-xs text-gray-500">
                  Added: {new Date(identity.created_at).toLocaleDateString()}
                </p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
