import { useState, useEffect } from "react";
import { Clock, Play, Square, Plus, DollarSign } from "lucide-react";
import { useTimeEntries, useTimeSummary, useStartTimer, useStopTimer } from "./hooks";
import { Button } from "@/shared/components/Button";
import { Input } from "@/shared/components/Input";
import { Card, CardBody, CardHeader } from "@/shared/components/Card";

const CATEGORIES = ["reconnaissance", "exploitation", "reporting", "meeting", "admin"];

const categoryColors: Record<string, string> = {
  reconnaissance: "var(--brand-400)",
  exploitation: "var(--danger-400)",
  reporting: "var(--success-400)",
  meeting: "var(--warning-400)",
  admin: "var(--text-tertiary)",
};

function TimerWidget() {
  const [running, setRunning] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [form, setForm] = useState({
    engagement_id: "",
    category: "reconnaissance",
    description: "",
  });
  const start = useStartTimer();
  const stop = useStopTimer();

  useEffect(() => {
    let interval: ReturnType<typeof setInterval> | undefined;
    if (running) interval = setInterval(() => setElapsed((e) => e + 1), 1000);
    return () => clearInterval(interval);
  }, [running]);

  const fmt = (s: number) =>
    `${Math.floor(s / 3600).toString().padStart(2, "0")}:${Math.floor((s % 3600) / 60)
      .toString()
      .padStart(2, "0")}:${(s % 60).toString().padStart(2, "0")}`;

  const handleStart = () => {
    if (!form.description.trim() || !form.engagement_id.trim()) return;
    start.mutate(form, {
      onSuccess: () => {
        setRunning(true);
        setElapsed(0);
      },
    });
  };

  const handleStop = () => {
    stop.mutate(undefined, {
      onSuccess: () => {
        setRunning(false);
        setElapsed(0);
      },
    });
  };

  return (
    <Card>
      <CardHeader>
        <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
          Timer
        </h3>
      </CardHeader>
      <CardBody className="space-y-3">
        <div className="text-center py-3">
          <p
            className="text-4xl font-mono font-bold"
            style={{ color: running ? "var(--brand-400)" : "var(--text-tertiary)" }}
          >
            {fmt(elapsed)}
          </p>
        </div>
        {!running && (
          <div className="space-y-2">
            <div className="grid gap-2 sm:grid-cols-2">
              <Input
                placeholder="Engagement ID..."
                value={form.engagement_id}
                onChange={(e) => setForm((p) => ({ ...p, engagement_id: e.target.value }))}
              />
              <select
                value={form.category}
                onChange={(e) => setForm((p) => ({ ...p, category: e.target.value }))}
                className="rounded-md border px-3 py-2 text-sm"
                style={{
                  background: "var(--bg-surface)",
                  borderColor: "var(--border-default)",
                  color: "var(--text-primary)",
                }}
              >
                {CATEGORIES.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </div>
            <Input
              placeholder="What are you working on?"
              value={form.description}
              onChange={(e) => setForm((p) => ({ ...p, description: e.target.value }))}
            />
          </div>
        )}
        <Button
          className="w-full"
          onClick={running ? handleStop : handleStart}
          leftIcon={running ? <Square className="h-4 w-4" /> : <Play className="h-4 w-4" />}
          disabled={start.isPending || stop.isPending}
        >
          {running ? "Stop Timer" : "Start Timer"}
        </Button>
      </CardBody>
    </Card>
  );
}

export function TimeTrackingPage() {
  const { data: entries = [] } = useTimeEntries();
  const { data: summary } = useTimeSummary();

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3">
        <Clock className="h-6 w-6" style={{ color: "var(--brand-500)" }} />
        <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>
          Time Tracking & Billing
        </h1>
      </div>

      {summary && (
        <div className="grid gap-3 sm:grid-cols-3">
          {[
            {
              label: "Total Hours",
              value: `${summary.total_hours}h`,
              icon: <Clock className="h-4 w-4" />,
            },
            {
              label: "Billable Amount",
              value: `$${summary.total_amount.toLocaleString()}`,
              icon: <DollarSign className="h-4 w-4" />,
            },
            {
              label: "Entries",
              value: summary.billable_entries,
              icon: <Plus className="h-4 w-4" />,
            },
          ].map(({ label, value, icon }) => (
            <div
              key={label}
              className="rounded-xl border p-4 text-center"
              style={{ background: "var(--bg-surface)", borderColor: "var(--border-subtle)" }}
            >
              <div className="flex justify-center mb-1" style={{ color: "var(--brand-400)" }}>
                {icon}
              </div>
              <p className="text-2xl font-bold" style={{ color: "var(--text-primary)" }}>
                {value}
              </p>
              <p className="text-xs mt-1" style={{ color: "var(--text-tertiary)" }}>
                {label}
              </p>
            </div>
          ))}
        </div>
      )}

      <div className="grid gap-4 md:grid-cols-3">
        <TimerWidget />
        <div className="md:col-span-2">
          <Card>
            <CardHeader>
              <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
                Recent Entries
              </h3>
            </CardHeader>
            <div className="divide-y" style={{ borderColor: "var(--border-subtle)" }}>
              {entries.slice(0, 10).map((e) => (
                <div key={e.id} className="flex items-center gap-4 px-4 py-3">
                  <div
                    className="h-2 w-2 rounded-full shrink-0"
                    style={{
                      background: categoryColors[e.category] ?? "var(--text-tertiary)",
                    }}
                  />
                  <div className="flex-1 min-w-0">
                    <p
                      className="text-sm truncate"
                      style={{ color: "var(--text-primary)" }}
                    >
                      {e.description}
                    </p>
                    <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>
                      {e.engagement_id} · {e.category}
                    </p>
                  </div>
                  <div className="text-right shrink-0">
                    <p
                      className="text-sm font-medium"
                      style={{ color: "var(--text-primary)" }}
                    >
                      {e.duration_minutes != null
                        ? `${Math.floor(e.duration_minutes / 60)}h ${e.duration_minutes % 60}m`
                        : "Running"}
                    </p>
                    {e.billable && (
                      <p className="text-xs" style={{ color: "var(--success-400)" }}>
                        ${e.amount}
                      </p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
