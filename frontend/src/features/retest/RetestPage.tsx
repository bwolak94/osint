import { useState } from "react";
import {
  RefreshCw,
  Plus,
  Play,
  CheckCircle2,
  XCircle,
  Clock,
  Bot,
} from "lucide-react";
import {
  useRetestSessions,
  useCreateRetest,
  useRunAutomated,
  useUpdateRetestItem,
} from "./hooks";
import type { RetestSession, RetestItem } from "./types";
import { Badge } from "@/shared/components/Badge";
import { Button } from "@/shared/components/Button";
import { Input } from "@/shared/components/Input";
import { Card, CardBody, CardHeader } from "@/shared/components/Card";

const severityVariant: Record<
  string,
  "danger" | "warning" | "info" | "neutral"
> = {
  critical: "danger",
  high: "danger",
  medium: "warning",
  low: "neutral",
};

function RetestItemRow({
  item,
  sessionId,
}: {
  item: RetestItem;
  sessionId: string;
}) {
  const update = useUpdateRetestItem();

  const statusIcon =
    item.status === "passed" ? (
      <CheckCircle2
        className="h-4 w-4"
        style={{ color: "var(--success-400)" }}
      />
    ) : item.status === "failed" ? (
      <XCircle className="h-4 w-4" style={{ color: "var(--danger-400)" }} />
    ) : (
      <Clock className="h-4 w-4" style={{ color: "var(--text-tertiary)" }} />
    );

  return (
    <div
      className="flex items-center gap-3 px-4 py-3 border-b last:border-0"
      style={{ borderColor: "var(--border-subtle)" }}
    >
      {statusIcon}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <p
            className="text-sm font-medium truncate"
            style={{ color: "var(--text-primary)" }}
          >
            {item.finding_title}
          </p>
          <Badge variant={(severityVariant[item.severity] ?? "neutral") as "success" | "warning" | "danger" | "info" | "neutral" | "brand"} size="sm">
            {item.severity}
          </Badge>
          {item.automated && (
            <Bot className="h-3 w-3" style={{ color: "var(--brand-400)" }} />
          )}
        </div>
        <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>
          CVSS {item.original_cvss}
          {item.result ? ` · ${item.result.replace("_", " ")}` : ""}
          {item.tested_at
            ? ` · ${new Date(item.tested_at).toLocaleDateString()}`
            : ""}
        </p>
      </div>
      {item.status === "pending" && (
        <div className="flex gap-1 shrink-0">
          <button
            onClick={() =>
              update.mutate({ sessionId, itemId: item.id, status: "passed" })
            }
            className="rounded px-2 py-1 text-xs font-medium transition-colors"
            style={{
              background: "var(--success-900)",
              color: "var(--success-400)",
            }}
          >
            Pass
          </button>
          <button
            onClick={() =>
              update.mutate({ sessionId, itemId: item.id, status: "failed" })
            }
            className="rounded px-2 py-1 text-xs font-medium transition-colors"
            style={{
              background: "var(--danger-900)",
              color: "var(--danger-400)",
            }}
          >
            Fail
          </button>
        </div>
      )}
    </div>
  );
}

function SessionDetail({ session }: { session: RetestSession }) {
  const runAuto = useRunAutomated();

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-3">
        <div
          className="flex-1 h-2 rounded-full overflow-hidden"
          style={{ background: "var(--bg-elevated)" }}
        >
          <div
            className="h-full rounded-full"
            style={{
              width: `${session.completion_percentage}%`,
              background:
                session.failed > session.passed
                  ? "var(--danger-500)"
                  : "var(--success-500)",
            }}
          />
        </div>
        <span
          className="text-sm font-bold"
          style={{ color: "var(--text-primary)" }}
        >
          {session.completion_percentage}%
        </span>
      </div>
      <div className="flex gap-3 text-center">
        {[
          {
            label: "Passed",
            value: session.passed,
            color: "var(--success-400)",
          },
          {
            label: "Failed",
            value: session.failed,
            color: "var(--danger-400)",
          },
          {
            label: "Pending",
            value: session.pending,
            color: "var(--text-tertiary)",
          },
        ].map(({ label, value, color }) => (
          <div
            key={label}
            className="flex-1 rounded p-2"
            style={{ background: "var(--bg-elevated)" }}
          >
            <p className="text-xl font-bold" style={{ color }}>
              {value}
            </p>
            <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>
              {label}
            </p>
          </div>
        ))}
      </div>
      {session.pending > 0 && (
        <Button
          size="sm"
          leftIcon={<Play className="h-3 w-3" />}
          onClick={() => runAuto.mutate(session.id)}
          disabled={runAuto.isPending}
          className="w-full"
        >
          {runAuto.isPending
            ? "Running..."
            : `Run Automated Tests (${(session.items ?? []).filter((i) => i.automated && i.status === "pending").length} items)`}
        </Button>
      )}
      <div>
        {(session.items ?? []).map((item) => (
          <RetestItemRow key={item.id} item={item} sessionId={session.id} />
        ))}
      </div>
    </div>
  );
}

export function RetestPage() {
  const { data: sessions = [] } = useRetestSessions();
  const create = useCreateRetest();
  const [showCreate, setShowCreate] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [engId, setEngId] = useState("");
  const selected = sessions.find((s) => s.id === selectedId);

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <RefreshCw
            className="h-6 w-6"
            style={{ color: "var(--brand-500)" }}
          />
          <h1
            className="text-xl font-semibold"
            style={{ color: "var(--text-primary)" }}
          >
            Automated Retest Engine
          </h1>
        </div>
        <Button
          leftIcon={<Plus className="h-4 w-4" />}
          onClick={() => setShowCreate(!showCreate)}
        >
          New Retest
        </Button>
      </div>

      {showCreate && (
        <Card>
          <CardBody className="space-y-3">
            <div className="grid gap-3 sm:grid-cols-2">
              <Input
                placeholder="Retest session name..."
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
              <Input
                placeholder="Engagement ID..."
                value={engId}
                onChange={(e) => setEngId(e.target.value)}
              />
            </div>
            <div className="flex gap-2 justify-end">
              <Button variant="ghost" onClick={() => setShowCreate(false)}>
                Cancel
              </Button>
              <Button
                onClick={() =>
                  create.mutate(
                    { name, engagement_id: engId, finding_ids: [] },
                    {
                      onSuccess: (s) => {
                        setShowCreate(false);
                        setSelectedId(s.id);
                      },
                    }
                  )
                }
                disabled={!name || create.isPending}
              >
                Create
              </Button>
            </div>
          </CardBody>
        </Card>
      )}

      <div className="grid gap-4 md:grid-cols-3">
        <div className="space-y-2">
          {sessions.map((s) => (
            <button
              key={s.id}
              onClick={() =>
                setSelectedId(s.id === selectedId ? null : s.id)
              }
              className="w-full rounded-lg border p-3 text-left transition-all"
              style={{
                background:
                  s.id === selectedId
                    ? "var(--brand-900)"
                    : "var(--bg-surface)",
                borderColor:
                  s.id === selectedId
                    ? "var(--brand-500)"
                    : "var(--border-default)",
              }}
            >
              <p
                className="text-sm font-medium"
                style={{ color: "var(--text-primary)" }}
              >
                {s.name}
              </p>
              <p
                className="text-xs mt-1"
                style={{ color: "var(--text-tertiary)" }}
              >
                {s.passed}/{s.total_items} passed · {s.completion_percentage}%
              </p>
            </button>
          ))}
          {sessions.length === 0 && (
            <p
              className="text-sm text-center py-8"
              style={{ color: "var(--text-tertiary)" }}
            >
              No retest sessions
            </p>
          )}
        </div>
        {selected && (
          <div className="md:col-span-2">
            <Card>
              <CardHeader>
                <h3
                  className="text-sm font-semibold"
                  style={{ color: "var(--text-primary)" }}
                >
                  {selected.name}
                </h3>
              </CardHeader>
              <CardBody>
                <SessionDetail session={selected} />
              </CardBody>
            </Card>
          </div>
        )}
      </div>
    </div>
  );
}
