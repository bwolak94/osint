import { useState, useCallback } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2, Loader2, AlertTriangle, Save, Sliders } from "lucide-react";
import { apiClient } from "@/shared/api/client";
import { Card, CardBody, CardHeader } from "@/shared/components/Card";
import { Badge } from "@/shared/components/Badge";
import { Button } from "@/shared/components/Button";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ScanProfile {
  id: string;
  name: string;
  tool: string;
  options: Record<string, unknown>;
  description: string;
  created_at: string;
}

interface ScanProfilesResponse {
  profiles: ScanProfile[];
  count: number;
}

// ---------------------------------------------------------------------------
// API
// ---------------------------------------------------------------------------

async function fetchProfiles(): Promise<ScanProfilesResponse> {
  const res = await apiClient.get("/advanced-scanners/scan-profiles");
  return res.data as ScanProfilesResponse;
}

async function createProfile(data: { name: string; tool: string; options: Record<string, unknown>; description: string }): Promise<ScanProfile> {
  const res = await apiClient.post("/advanced-scanners/scan-profiles", data);
  return res.data as ScanProfile;
}

async function deleteProfile(id: string): Promise<void> {
  await apiClient.delete(`/advanced-scanners/scan-profiles/${id}`);
}

// ---------------------------------------------------------------------------
// Create form
// ---------------------------------------------------------------------------

const TOOLS = ["nuclei", "subfinder", "httpx", "sslyze", "ffuf", "zap", "nmap"];

function CreateProfileForm({ onCreated }: { onCreated: () => void }) {
  const [name, setName] = useState("");
  const [tool, setTool] = useState("nuclei");
  const [description, setDescription] = useState("");
  const [optionsRaw, setOptionsRaw] = useState("{}");
  const [jsonError, setJsonError] = useState<string | null>(null);

  const queryClient = useQueryClient();
  const mutation = useMutation({
    mutationFn: createProfile,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["scan-profiles"] });
      setName("");
      setDescription("");
      setOptionsRaw("{}");
      onCreated();
    },
  });

  const handleSubmit = useCallback(() => {
    setJsonError(null);
    let options: Record<string, unknown> = {};
    try {
      options = JSON.parse(optionsRaw) as Record<string, unknown>;
    } catch {
      setJsonError("Invalid JSON in options");
      return;
    }
    if (!name.trim()) return;
    mutation.mutate({ name: name.trim(), tool, options, description });
  }, [name, tool, description, optionsRaw, mutation]);

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2">
          <Plus className="h-3.5 w-3.5" style={{ color: "var(--brand-500)" }} />
          <span className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>New Profile</span>
        </div>
      </CardHeader>
      <CardBody className="space-y-3">
        <div className="grid sm:grid-cols-2 gap-3">
          <div>
            <label className="text-xs font-medium block mb-1" style={{ color: "var(--text-secondary)" }}>Name *</label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Full nuclei scan"
              className="w-full rounded-md border px-3 py-1.5 text-xs"
              style={{ background: "var(--bg-elevated)", borderColor: "var(--border-default)", color: "var(--text-primary)" }}
            />
          </div>
          <div>
            <label className="text-xs font-medium block mb-1" style={{ color: "var(--text-secondary)" }}>Tool</label>
            <select
              value={tool}
              onChange={(e) => setTool(e.target.value)}
              className="w-full rounded-md border px-3 py-1.5 text-xs"
              style={{ background: "var(--bg-elevated)", borderColor: "var(--border-default)", color: "var(--text-primary)" }}
            >
              {TOOLS.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>
        </div>
        <div>
          <label className="text-xs font-medium block mb-1" style={{ color: "var(--text-secondary)" }}>Description</label>
          <input
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Optional description"
            className="w-full rounded-md border px-3 py-1.5 text-xs"
            style={{ background: "var(--bg-elevated)", borderColor: "var(--border-default)", color: "var(--text-primary)" }}
          />
        </div>
        <div>
          <label className="text-xs font-medium block mb-1" style={{ color: "var(--text-secondary)" }}>Options (JSON)</label>
          <textarea
            value={optionsRaw}
            onChange={(e) => setOptionsRaw(e.target.value)}
            rows={4}
            className="w-full rounded-md border px-3 py-2 text-xs font-mono resize-none"
            style={{ background: "var(--bg-elevated)", borderColor: jsonError ? "var(--danger-400)" : "var(--border-default)", color: "var(--text-primary)" }}
          />
          {jsonError && <p className="text-xs mt-1" style={{ color: "var(--danger-400)" }}>{jsonError}</p>}
        </div>
        {mutation.isError && (
          <p className="text-xs" style={{ color: "var(--danger-400)" }}>
            Failed to create profile.
          </p>
        )}
        <Button
          size="sm"
          leftIcon={<Save className="h-3.5 w-3.5" />}
          onClick={handleSubmit}
          loading={mutation.isPending}
          disabled={!name.trim()}
        >
          Save Profile
        </Button>
      </CardBody>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Profile card
// ---------------------------------------------------------------------------

function ProfileCard({ profile, onDelete }: { profile: ScanProfile; onDelete: (id: string) => void }) {
  const [showOptions, setShowOptions] = useState(false);
  const createdAt = new Date(profile.created_at).toLocaleString();

  return (
    <div className="rounded-lg border p-4 space-y-2"
      style={{ background: "var(--bg-elevated)", borderColor: "var(--border-default)" }}>
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>{profile.name}</p>
          {profile.description && (
            <p className="text-xs mt-0.5" style={{ color: "var(--text-secondary)" }}>{profile.description}</p>
          )}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <Badge variant="neutral" size="sm">{profile.tool}</Badge>
          <button onClick={() => onDelete(profile.id)} title="Delete">
            <Trash2 className="h-3.5 w-3.5" style={{ color: "var(--text-tertiary)" }} />
          </button>
        </div>
      </div>
      <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>Created: {createdAt}</p>
      <button
        className="text-xs underline"
        style={{ color: "var(--brand-400)" }}
        onClick={() => setShowOptions((p) => !p)}
      >
        {showOptions ? "Hide options" : "Show options"}
      </button>
      {showOptions && (
        <pre className="rounded p-2 text-xs font-mono overflow-x-auto"
          style={{ background: "var(--bg-base)", color: "var(--text-secondary)" }}>
          {JSON.stringify(profile.options, null, 2)}
        </pre>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export function ScanProfilesPage() {
  const [showCreate, setShowCreate] = useState(false);
  const queryClient = useQueryClient();

  const { data, isLoading, isError } = useQuery({
    queryKey: ["scan-profiles"],
    queryFn: fetchProfiles,
    staleTime: 30_000,
  });

  const deleteMutation = useMutation({
    mutationFn: deleteProfile,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["scan-profiles"] }),
  });

  const grouped = (data?.profiles ?? []).reduce<Record<string, ScanProfile[]>>((acc, p) => {
    if (!acc[p.tool]) acc[p.tool] = [];
    acc[p.tool].push(p);
    return acc;
  }, {});

  return (
    <div className="space-y-6 max-w-3xl">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>
            Scan Profiles
          </h1>
          <p className="text-sm mt-1" style={{ color: "var(--text-secondary)" }}>
            Save reusable tool configurations. Profiles are stored server-side.
          </p>
        </div>
        <Button size="sm" leftIcon={<Plus className="h-3.5 w-3.5" />} onClick={() => setShowCreate((p) => !p)}>
          New Profile
        </Button>
      </div>

      {showCreate && <CreateProfileForm onCreated={() => setShowCreate(false)} />}

      {isLoading && (
        <div className="flex items-center gap-2" style={{ color: "var(--text-tertiary)" }}>
          <Loader2 className="h-4 w-4 animate-spin" />
          <span className="text-sm">Loading profiles...</span>
        </div>
      )}

      {isError && (
        <div className="flex items-center gap-2 text-sm" style={{ color: "var(--danger-400)" }}>
          <AlertTriangle className="h-4 w-4" />
          Failed to load scan profiles.
        </div>
      )}

      {!isLoading && data?.profiles.length === 0 && (
        <div className="rounded-lg border px-6 py-10 text-center"
          style={{ borderColor: "var(--border-default)", background: "var(--bg-elevated)" }}>
          <Sliders className="h-8 w-8 mx-auto mb-2" style={{ color: "var(--text-tertiary)" }} />
          <p className="text-sm" style={{ color: "var(--text-tertiary)" }}>No profiles saved yet. Create one above.</p>
        </div>
      )}

      {Object.entries(grouped).map(([tool, profiles]) => (
        <div key={tool} className="space-y-2">
          <p className="text-xs font-semibold uppercase tracking-wider" style={{ color: "var(--text-tertiary)" }}>
            {tool} ({profiles.length})
          </p>
          <div className="grid gap-3 sm:grid-cols-2">
            {profiles.map((p) => (
              <ProfileCard key={p.id} profile={p} onDelete={(id) => deleteMutation.mutate(id)} />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
