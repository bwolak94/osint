import { useState, useRef, useCallback } from "react";
import { Search, Network, Shield, Activity, Plus, ArrowUpRight, Loader2, GripVertical } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { Card, CardBody, CardHeader } from "@/shared/components/Card";
import { Button } from "@/shared/components/Button";
import { Badge } from "@/shared/components/Badge";
import { EmptyState } from "@/shared/components/EmptyState";
import { useInvestigations, useCreateInvestigation, useStartInvestigation } from "./hooks";

const STAT_ORDER_KEY = "dashboard-stat-order";

function loadStatOrder(len: number): number[] {
  try {
    const saved = localStorage.getItem(STAT_ORDER_KEY);
    if (saved) {
      const parsed = JSON.parse(saved) as number[];
      if (parsed.length === len) return parsed;
    }
  } catch { /* ignore */ }
  return Array.from({ length: len }, (_, i) => i);
}

interface StatCardProps {
  label: string;
  value: string | number;
  icon: typeof Search;
  dragging: boolean;
  dragOver: boolean;
  onDragStart: () => void;
  onDragOver: (e: React.DragEvent) => void;
  onDrop: () => void;
  onDragEnd: () => void;
}

function StatCard({ label, value, icon: Icon, dragging, dragOver, onDragStart, onDragOver, onDrop, onDragEnd }: StatCardProps) {
  return (
    <div
      draggable
      onDragStart={onDragStart}
      onDragOver={onDragOver}
      onDrop={onDrop}
      onDragEnd={onDragEnd}
      style={{ opacity: dragging ? 0.4 : 1, cursor: "grab", transition: "opacity 0.15s" }}
    >
      <Card style={{ outline: dragOver ? "2px dashed var(--brand-500)" : undefined }}>
        <CardBody>
          <div className="flex items-start justify-between">
            <div className="flex items-start gap-2">
              <GripVertical className="mt-0.5 h-4 w-4 shrink-0" style={{ color: "var(--text-tertiary)", cursor: "grab" }} />
              <div>
                <p className="text-xs font-medium uppercase tracking-wide" style={{ color: "var(--text-tertiary)" }}>
                  {label}
                </p>
                <p className="mt-1 text-2xl font-bold" style={{ color: "var(--text-primary)" }}>
                  {value}
                </p>
              </div>
            </div>
            <div
              className="flex h-10 w-10 items-center justify-center rounded-lg"
              style={{ background: "var(--brand-900)" }}
            >
              <Icon className="h-5 w-5" style={{ color: "var(--brand-400)" }} />
            </div>
          </div>
        </CardBody>
      </Card>
    </div>
  );
}

const statusVariant: Record<string, "neutral" | "info" | "success" | "warning"> = {
  draft: "neutral",
  running: "info",
  completed: "success",
  paused: "warning",
};

// Relative time helper
function timeAgo(dateStr: string): string {
  const now = Date.now();
  const diff = now - new Date(dateStr).getTime();
  const minutes = Math.floor(diff / 60000);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

function QuickScan() {
  const navigate = useNavigate();
  const [scanType, setScanType] = useState("email");
  const [scanValue, setScanValue] = useState("");
  const createMutation = useCreateInvestigation();
  const startMutation = useStartInvestigation();

  const handleScan = async () => {
    if (!scanValue.trim()) return;
    try {
      const inv = await createMutation.mutateAsync({
        title: `Quick scan — ${scanValue}`,
        description: `Quick ${scanType} scan`,
        seed_inputs: [{ type: scanType, value: scanValue.trim() }],
        tags: ["quick-scan"],
      });
      await startMutation.mutateAsync(inv.id);
      navigate(`/investigations/${inv.id}`);
    } catch {
      // Error handled by react-query
    }
  };

  const isLoading = createMutation.isPending || startMutation.isPending;

  return (
    <div>
      <Card>
        <CardHeader>
          <h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Quick Scan</h2>
        </CardHeader>
        <CardBody className="space-y-3">
          <p className="text-xs" style={{ color: "var(--text-secondary)" }}>
            Quickly check an email, username, or NIP without creating a full investigation.
          </p>
          <select
            value={scanType}
            onChange={(e) => setScanType(e.target.value)}
            className="w-full rounded-md border px-3 py-2 text-sm"
            style={{ background: "var(--bg-elevated)", borderColor: "var(--border-default)", color: "var(--text-primary)" }}
          >
            <option value="email">Email</option>
            <option value="username">Username</option>
            <option value="nip">NIP</option>
          </select>
          <input
            value={scanValue}
            onChange={(e) => setScanValue(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleScan()}
            className="w-full rounded-md border px-3 py-2 text-sm"
            placeholder={scanType === "email" ? "user@example.com" : scanType === "nip" ? "5261040828" : "username"}
            style={{ background: "var(--bg-elevated)", borderColor: "var(--border-default)", color: "var(--text-primary)" }}
          />
          <Button className="w-full" leftIcon={<Search className="h-4 w-4" />} onClick={handleScan} loading={isLoading} disabled={!scanValue.trim()}>
            Scan
          </Button>
        </CardBody>
      </Card>
    </div>
  );
}

export function DashboardPage() {
  const navigate = useNavigate();
  const { data, isLoading, isError } = useInvestigations();

  const items = data?.items ?? [];

  // Compute stats from real data
  const activeCount = items.filter((i) => i.status === "running" || i.status === "draft" || i.status === "paused").length;
  const completedCount = items.filter((i) => i.status === "completed").length;
  const totalSeeds = items.reduce((acc, i) => acc + (i.seed_inputs?.length ?? 0), 0);

  const statsBase = [
    { label: "Active Investigations", value: activeCount, icon: Search },
    { label: "Completed", value: completedCount, icon: Shield },
    { label: "Total Investigations", value: data?.total ?? 0, icon: Activity },
    { label: "Total Seeds", value: totalSeeds, icon: Network },
  ];

  // Drag-and-drop ordering for stat widgets (Improvement 38)
  const [statOrder, setStatOrder] = useState<number[]>(() => loadStatOrder(statsBase.length));
  const [draggingIdx, setDraggingIdx] = useState<number | null>(null);
  const [dragOverIdx, setDragOverIdx] = useState<number | null>(null);
  const dragSourceOrder = useRef<number | null>(null);

  const handleDragStart = useCallback((orderPos: number) => {
    setDraggingIdx(orderPos);
    dragSourceOrder.current = orderPos;
  }, []);

  const handleDragOver = useCallback((e: React.DragEvent, orderPos: number) => {
    e.preventDefault();
    setDragOverIdx(orderPos);
  }, []);

  const handleDrop = useCallback((orderPos: number) => {
    const from = dragSourceOrder.current;
    if (from === null || from === orderPos) return;
    setStatOrder((prev) => {
      const next = [...prev];
      const tmp = next[from] as number;
      next[from] = next[orderPos] as number;
      next[orderPos] = tmp;
      localStorage.setItem(STAT_ORDER_KEY, JSON.stringify(next));
      return next;
    });
    setDraggingIdx(null);
    setDragOverIdx(null);
    dragSourceOrder.current = null;
  }, []);

  const handleDragEnd = useCallback(() => {
    setDraggingIdx(null);
    setDragOverIdx(null);
    dragSourceOrder.current = null;
  }, []);

  const stats = statOrder.map((origIdx) => statsBase[origIdx]).filter((s): s is typeof statsBase[0] => s !== undefined);

  // Show the 5 most recent investigations
  const recentInvestigations = items.slice(0, 5).map((inv) => ({
    id: inv.id,
    title: inv.title,
    status: inv.status,
    updatedAt: timeAgo(inv.updated_at),
  }));

  if (isLoading && !data && !isError) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-6 w-6 animate-spin" style={{ color: "var(--brand-500)" }} />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>
            Dashboard
          </h1>
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
            Overview of your OSINT operations
          </p>
        </div>
        <Button
          leftIcon={<Plus className="h-4 w-4" />}
          onClick={() => navigate("/investigations")}
        >
          New Investigation
        </Button>
      </div>

      {/* Stats grid — draggable to reorder */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {stats.map((stat, orderPos) => (
          <StatCard
            key={stat.label}
            {...stat}
            dragging={draggingIdx === orderPos}
            dragOver={dragOverIdx === orderPos}
            onDragStart={() => handleDragStart(orderPos)}
            onDragOver={(e) => handleDragOver(e, orderPos)}
            onDrop={() => handleDrop(orderPos)}
            onDragEnd={handleDragEnd}
          />
        ))}
      </div>

      {/* Two-column layout */}
      <div className="grid gap-6 lg:grid-cols-3">
        {/* Recent investigations */}
        <div className="lg:col-span-2">
          <Card>
            <CardHeader className="flex items-center justify-between">
              <h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
                Recent Investigations
              </h2>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => navigate("/investigations")}
                rightIcon={<ArrowUpRight className="h-3 w-3" />}
              >
                View all
              </Button>
            </CardHeader>
            <CardBody className="p-0">
              {recentInvestigations.length === 0 ? (
                <div className="p-6">
                  <EmptyState
                    title="No investigations yet"
                    description="Start your first investigation to see it here"
                    action={<Button leftIcon={<Plus className="h-4 w-4" />}>Create Investigation</Button>}
                  />
                </div>
              ) : (
                <div>
                  {recentInvestigations.map((inv) => (
                    <div
                      key={inv.id}
                      onClick={() => navigate(`/investigations/${inv.id}`)}
                      className="flex cursor-pointer items-center justify-between border-b px-5 py-3 transition-colors hover:bg-bg-overlay"
                      style={{ borderColor: "var(--border-subtle)" }}
                    >
                      <div className="flex items-center gap-3">
                        <div>
                          <p className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>
                            {inv.title}
                          </p>
                          <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>
                            {inv.updatedAt}
                          </p>
                        </div>
                      </div>
                      <Badge variant={statusVariant[inv.status] ?? "neutral"} size="sm" dot>
                        {inv.status}
                      </Badge>
                    </div>
                  ))}
                </div>
              )}
            </CardBody>
          </Card>
        </div>

        {/* Quick scan */}
        <QuickScan />
      </div>
    </div>
  );
}
