import { useNavigate } from "react-router-dom";
import { Card } from "@/shared/components/Card";
import { Badge } from "@/shared/components/Badge";
import { ProgressBar } from "@/shared/components/ProgressBar";
import { Clock, Hash } from "lucide-react";

interface InvestigationCardProps {
  id: string;
  title: string;
  status: string;
  seedCount: number;
  progress?: number;
  tags: string[];
  createdAt: string;
}

const statusVariant: Record<string, "neutral" | "info" | "success" | "warning" | "danger"> = {
  draft: "neutral",
  running: "info",
  paused: "warning",
  completed: "success",
  archived: "danger",
};

export function InvestigationCard({
  id,
  title,
  status,
  seedCount,
  progress,
  tags,
  createdAt,
}: InvestigationCardProps) {
  const navigate = useNavigate();

  return (
    <Card hover onClick={() => navigate(`/investigations/${id}`)}>
      <div className="p-4">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <h3
              className="truncate text-sm font-semibold"
              style={{ color: "var(--text-primary)" }}
            >
              {title}
            </h3>
            <div className="mt-1 flex items-center gap-2">
              <Badge variant={statusVariant[status] ?? "neutral"} size="sm" dot>
                {status}
              </Badge>
              <span className="text-xs" style={{ color: "var(--text-tertiary)" }}>
                <Hash className="mr-0.5 inline h-3 w-3" />
                {seedCount} seeds
              </span>
            </div>
          </div>
          <span className="shrink-0 text-xs" style={{ color: "var(--text-tertiary)" }}>
            <Clock className="mr-0.5 inline h-3 w-3" />
            {new Date(createdAt).toLocaleDateString()}
          </span>
        </div>

        {status === "running" && progress !== undefined && (
          <div className="mt-3">
            <ProgressBar value={progress} size="sm" showPercentage={false} />
          </div>
        )}

        {tags.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1">
            {tags.slice(0, 3).map((tag) => (
              <Badge key={tag} variant="neutral" size="sm">
                {tag}
              </Badge>
            ))}
            {tags.length > 3 && (
              <Badge variant="neutral" size="sm">
                +{tags.length - 3}
              </Badge>
            )}
          </div>
        )}
      </div>
    </Card>
  );
}
