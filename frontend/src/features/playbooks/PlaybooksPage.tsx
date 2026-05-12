import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Card, CardBody } from "@/shared/components/Card";
import { Badge } from "@/shared/components/Badge";
import { Button } from "@/shared/components/Button";
import { Input } from "@/shared/components/Input";
import { apiClient } from "@/shared/api/client";
import { toast } from "@/shared/components/Toast";
import { Play, Zap, X, Plus, Trash2, GripVertical, History, CheckCircle2, Clock, AlertCircle } from "lucide-react";
import { formatDistanceToNow } from "date-fns";

function usePlaybooks() {
  return useQuery({
    queryKey: ["playbooks"],
    queryFn: async () => {
      const res = await apiClient.get("/playbooks/");
      return res.data;
    },
  });
}

interface PlaybookStep {
  scanner: string;
  input_type: string;
  condition: string;
}

interface Playbook {
  id: string;
  name: string;
  description: string;
  steps: PlaybookStep[];
  is_public: boolean;
}

const ALL_SCANNERS = [
  { id: "holehe", name: "Holehe", input_type: "email", desc: "Email registration check (120+ services)" },
  { id: "hibp", name: "HIBP Breaches", input_type: "email", desc: "Data breach lookup" },
  { id: "maigret", name: "Maigret", input_type: "username", desc: "Username search (3000+ sites)" },
  { id: "vat_status", name: "VAT Status", input_type: "nip", desc: "Polish VAT registry (Biała Lista)" },
  { id: "playwright_krs", name: "KRS Registry", input_type: "nip", desc: "Polish company registry" },
  { id: "playwright_ceidg", name: "CEIDG", input_type: "nip", desc: "Sole proprietorship registry" },
  { id: "whois", name: "WHOIS", input_type: "domain", desc: "Domain ownership data" },
  { id: "dns_lookup", name: "DNS Lookup", input_type: "domain", desc: "A, MX, NS, TXT records" },
  { id: "cert_transparency", name: "Cert Transparency", input_type: "domain", desc: "Subdomain discovery via CT logs" },
  { id: "virustotal", name: "VirusTotal", input_type: "domain", desc: "Threat intelligence (needs API key)" },
  { id: "shodan", name: "Shodan", input_type: "ip_address", desc: "Open ports and services" },
  { id: "geoip", name: "GeoIP", input_type: "ip_address", desc: "IP geolocation" },
  { id: "phone_lookup", name: "Phone Lookup", input_type: "phone", desc: "Carrier and line type" },
  { id: "google_account", name: "Google Account", input_type: "email", desc: "Google services discovery (Calendar, Workspace, Gravatar)" },
  { id: "linkedin", name: "LinkedIn", input_type: "username", desc: "LinkedIn profile search" },
  { id: "twitter", name: "Twitter/X", input_type: "username", desc: "Twitter/X profile check" },
  { id: "facebook", name: "Facebook", input_type: "username", desc: "Facebook profile check" },
  { id: "instagram", name: "Instagram", input_type: "username", desc: "Instagram profile data extraction" },
];

const INPUT_TYPES = [
  { value: "email", label: "Email" },
  { value: "username", label: "Username" },
  { value: "nip", label: "NIP" },
  { value: "domain", label: "Domain" },
  { value: "ip_address", label: "IP Address" },
  { value: "phone", label: "Phone" },
];

const stepIcons: Record<string, string> = {
  email: "\u{1F4E7}", nip: "\u{1F3E2}", domain: "\u{1F310}", ip_address: "\u{1F4E1}", username: "\u{1F464}", phone: "\u{1F4F1}",
};

interface StepRunResult {
  step_index: number;
  scanner: string;
  status: "queued" | "skipped";
  input_type: string;
  condition: string;
}

interface PlaybookRun {
  run_id: string;
  playbook_id: string;
  playbook_name: string;
  seed_value: string;
  seed_type: string;
  started_at: string;
  status: "queued" | "running" | "completed" | "failed";
  step_results: StepRunResult[];
}

const RUN_STATUS_ICON: Record<string, React.ReactNode> = {
  completed: <CheckCircle2 className="h-3.5 w-3.5" style={{ color: "var(--success-500)" }} />,
  queued: <Clock className="h-3.5 w-3.5" style={{ color: "var(--info-500)" }} />,
  running: <Clock className="h-3.5 w-3.5" style={{ color: "var(--warning-500)" }} />,
  failed: <AlertCircle className="h-3.5 w-3.5" style={{ color: "var(--danger-500)" }} />,
};

function usePlaybookRuns(playbookId: string | null) {
  return useQuery({
    queryKey: ["playbook-runs", playbookId],
    queryFn: async () => {
      const res = await apiClient.get<PlaybookRun[]>(`/playbooks/${playbookId}/runs`);
      return res.data;
    },
    enabled: !!playbookId,
    staleTime: 30_000,
  });
}

function PlaybookRunHistory({ playbookId }: { playbookId: string }) {
  const { data: runs, isLoading } = usePlaybookRuns(playbookId);

  if (isLoading) return null;
  if (!runs || runs.length === 0) {
    return (
      <p className="text-xs py-2" style={{ color: "var(--text-tertiary)" }}>
        No runs yet. Use this playbook to create a run.
      </p>
    );
  }

  return (
    <div className="space-y-1.5">
      {runs.slice(0, 5).map((run) => (
        <div
          key={run.run_id}
          className="flex items-center gap-2 rounded-md px-3 py-2"
          style={{ background: "var(--bg-overlay)" }}
        >
          {RUN_STATUS_ICON[run.status] ?? RUN_STATUS_ICON.queued}
          <span className="flex-1 min-w-0 text-xs font-mono truncate" style={{ color: "var(--text-primary)" }}>
            {run.seed_value}
          </span>
          <Badge variant="neutral" size="sm">{run.step_results.length} steps</Badge>
          <span className="text-[10px]" style={{ color: "var(--text-tertiary)" }}>
            {formatDistanceToNow(new Date(run.started_at), { addSuffix: true })}
          </span>
        </div>
      ))}
    </div>
  );
}

export function PlaybooksPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { data: playbooks } = usePlaybooks();
  const [activePlaybook, setActivePlaybook] = useState<Playbook | null>(null);
  const [seedValue, setSeedValue] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [expandedHistoryId, setExpandedHistoryId] = useState<string | null>(null);

  // Create playbook form state
  const [newName, setNewName] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [newSteps, setNewSteps] = useState<PlaybookStep[]>([]);
  const [selectedInputType, setSelectedInputType] = useState("email");

  const executeMutation = useMutation({
    mutationFn: async ({ playbookId, seedVal, seedType }: { playbookId: string; seedVal: string; seedType: string }) => {
      const res = await apiClient.post<PlaybookRun>(`/playbooks/${playbookId}/execute`, {
        seed_value: seedVal,
        seed_type: seedType,
      });
      return res.data;
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["playbook-runs", data.playbook_id] });
      toast.success(`Playbook queued — ${data.step_results.length} steps`);
    },
    onError: () => toast.error("Playbook execution failed"),
  });

  const createInvMutation = useMutation({
    mutationFn: async (data: any) => {
      const res = await apiClient.post("/investigations/", data);
      return res.data;
    },
  });

  const startMutation = useMutation({
    mutationFn: async (id: string) => { await apiClient.post(`/investigations/${id}/start`); },
  });

  const savePlaybookMutation = useMutation({
    mutationFn: async (data: { name: string; description: string; steps: PlaybookStep[] }) => {
      const res = await apiClient.post("/playbooks/", data);
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["playbooks"] });
      toast.success("Playbook created");
      setShowCreate(false);
      resetCreateForm();
    },
    onError: () => toast.error("Failed to create playbook"),
  });

  const resetCreateForm = () => {
    setNewName("");
    setNewDesc("");
    setNewSteps([]);
    setSelectedInputType("email");
  };

  const handleUsePlaybook = async () => {
    if (!activePlaybook || !seedValue.trim()) return;
    const inputType = activePlaybook.steps[0]?.input_type || "email";
    const scanners = activePlaybook.steps.map((s) => s.scanner);
    try {
      // Fire execute endpoint to log the run
      executeMutation.mutate({
        playbookId: activePlaybook.id,
        seedVal: seedValue.trim(),
        seedType: inputType,
      });
      // Create and start investigation
      const inv = await createInvMutation.mutateAsync({
        title: `${activePlaybook.name} — ${seedValue}`,
        seed_inputs: [{ type: inputType, value: seedValue.trim() }],
        tags: ["playbook"],
        enabled_scanners: scanners,
      });
      await startMutation.mutateAsync(inv.id);
      toast.success(`Playbook "${activePlaybook.name}" started`);
      navigate(`/investigations/${inv.id}`);
    } catch { toast.error("Failed to run playbook"); }
  };

  const addStep = (scannerId: string) => {
    const scanner = ALL_SCANNERS.find((s) => s.id === scannerId);
    if (!scanner) return;
    if (newSteps.some((s) => s.scanner === scannerId)) return;
    setNewSteps([...newSteps, { scanner: scannerId, input_type: scanner.input_type, condition: "always" }]);
  };

  const removeStep = (index: number) => {
    setNewSteps(newSteps.filter((_, i) => i !== index));
  };

  const availableScanners = ALL_SCANNERS.filter(
    (s) => s.input_type === selectedInputType && !newSteps.some((st) => st.scanner === s.id),
  );

  const isRunning = createInvMutation.isPending || startMutation.isPending;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>Playbooks</h1>
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
            Pre-configured scan workflows for common investigation types
          </p>
        </div>
        <Button leftIcon={<Plus className="h-4 w-4" />} onClick={() => setShowCreate(true)}>
          Create Playbook
        </Button>
      </div>

      {/* Run playbook input */}
      {activePlaybook && (
        <Card className="border-brand-500/30">
          <CardBody className="space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Zap className="h-4 w-4" style={{ color: "var(--brand-500)" }} />
                <span className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>{activePlaybook.name}</span>
              </div>
              <button onClick={() => { setActivePlaybook(null); setSeedValue(""); }} className="rounded p-1 hover:bg-bg-overlay">
                <X className="h-4 w-4" style={{ color: "var(--text-tertiary)" }} />
              </button>
            </div>
            <p className="text-xs" style={{ color: "var(--text-secondary)" }}>
              Enter a {activePlaybook.steps[0]?.input_type || "value"} to scan with: {activePlaybook.steps.map((s) => s.scanner).join(", ")}
            </p>
            <div className="flex gap-2">
              <Input
                placeholder={
                  activePlaybook.steps[0]?.input_type === "email" ? "user@example.com" :
                  activePlaybook.steps[0]?.input_type === "nip" ? "5261040828" :
                  activePlaybook.steps[0]?.input_type === "domain" ? "example.com" :
                  activePlaybook.steps[0]?.input_type === "ip_address" ? "8.8.8.8" : "Enter value..."
                }
                value={seedValue}
                onChange={(e) => setSeedValue(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleUsePlaybook()}
                mono
              />
              <Button onClick={handleUsePlaybook} loading={isRunning} disabled={!seedValue.trim()}>Run</Button>
            </div>
          </CardBody>
        </Card>
      )}

      {/* Create Playbook Modal */}
      {showCreate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm" onClick={() => setShowCreate(false)}>
          <div
            className="w-full max-w-lg rounded-xl border shadow-lg"
            style={{ background: "var(--bg-surface)", borderColor: "var(--border-default)" }}
            onClick={(e) => e.stopPropagation()}
          >
              <div className="flex items-center justify-between border-b px-6 py-4" style={{ borderColor: "var(--border-subtle)" }}>
                <h2 className="text-base font-semibold" style={{ color: "var(--text-primary)" }}>Create Custom Playbook</h2>
                <button onClick={() => { setShowCreate(false); resetCreateForm(); }} className="rounded-md p-1 hover:bg-bg-overlay">
                  <X className="h-4 w-4" style={{ color: "var(--text-secondary)" }} />
                </button>
              </div>

              <div className="max-h-[60vh] overflow-y-auto px-6 py-4 space-y-4">
                <Input label="Playbook Name" placeholder="My Custom Playbook" value={newName} onChange={(e) => setNewName(e.target.value)} />
                <div>
                  <label className="mb-1.5 block text-sm font-medium" style={{ color: "var(--text-secondary)" }}>Description</label>
                  <textarea
                    className="block w-full rounded-md border px-3 py-2 text-sm"
                    style={{ background: "var(--bg-elevated)", borderColor: "var(--border-default)", color: "var(--text-primary)" }}
                    rows={2}
                    placeholder="What does this playbook do?"
                    value={newDesc}
                    onChange={(e) => setNewDesc(e.target.value)}
                  />
                </div>

                {/* Steps */}
                <div>
                  <p className="mb-2 text-sm font-medium" style={{ color: "var(--text-secondary)" }}>
                    Scan Steps ({newSteps.length})
                  </p>

                  {newSteps.length > 0 && (
                    <div className="mb-3 space-y-1">
                      {newSteps.map((step, i) => {
                        const scanner = ALL_SCANNERS.find((s) => s.id === step.scanner);
                        return (
                          <div
                            key={i}
                            className="flex items-center gap-2 rounded-md border px-3 py-2"
                            style={{ background: "var(--bg-elevated)", borderColor: "var(--border-subtle)" }}
                          >
                            <GripVertical className="h-3 w-3 shrink-0" style={{ color: "var(--text-tertiary)" }} />
                            <span className="text-xs font-medium" style={{ color: "var(--text-primary)" }}>
                              {i + 1}. {scanner?.name ?? step.scanner}
                            </span>
                            <Badge variant="neutral" size="sm">{step.input_type}</Badge>
                            <span className="flex-1 text-xs" style={{ color: "var(--text-tertiary)" }}>{scanner?.desc}</span>
                            <button onClick={() => removeStep(i)} className="rounded p-0.5 hover:bg-bg-overlay">
                              <Trash2 className="h-3 w-3" style={{ color: "var(--danger-500)" }} />
                            </button>
                          </div>
                        );
                      })}
                    </div>
                  )}

                  {/* Add step */}
                  <div className="space-y-2">
                    <div className="flex gap-2">
                      <select
                        value={selectedInputType}
                        onChange={(e) => setSelectedInputType(e.target.value)}
                        className="rounded-md border px-2 py-1.5 text-xs"
                        style={{ background: "var(--bg-elevated)", borderColor: "var(--border-default)", color: "var(--text-primary)" }}
                      >
                        {INPUT_TYPES.map((t) => (
                          <option key={t.value} value={t.value}>{t.label}</option>
                        ))}
                      </select>
                    </div>
                    <div className="grid grid-cols-2 gap-1">
                      {availableScanners.map((s) => (
                        <button
                          key={s.id}
                          onClick={() => addStep(s.id)}
                          className="flex items-center gap-2 rounded-md border px-2 py-1.5 text-left text-xs transition-colors hover:bg-bg-overlay"
                          style={{ borderColor: "var(--border-subtle)", color: "var(--text-primary)" }}
                        >
                          <Plus className="h-3 w-3 shrink-0" style={{ color: "var(--brand-500)" }} />
                          <div>
                            <span className="font-medium">{s.name}</span>
                            <p className="text-[10px]" style={{ color: "var(--text-tertiary)" }}>{s.desc}</p>
                          </div>
                        </button>
                      ))}
                      {availableScanners.length === 0 && (
                        <p className="col-span-2 py-2 text-center text-xs" style={{ color: "var(--text-tertiary)" }}>
                          All {selectedInputType} scanners added
                        </p>
                      )}
                    </div>
                  </div>
                </div>
              </div>

              <div className="flex items-center justify-between border-t px-6 py-4" style={{ borderColor: "var(--border-subtle)" }}>
                <Button variant="ghost" onClick={() => { setShowCreate(false); resetCreateForm(); }}>Cancel</Button>
                <Button
                  onClick={() => savePlaybookMutation.mutate({ name: newName, description: newDesc, steps: newSteps })}
                  loading={savePlaybookMutation.isPending}
                  disabled={!newName.trim() || newSteps.length === 0}
                >
                  Save Playbook
                </Button>
              </div>
          </div>
        </div>
      )}

      {/* Playbook grid */}
      <div className="grid gap-4 sm:grid-cols-2">
        {(playbooks ?? []).map((pb: Playbook) => (
          <Card key={pb.id} hover>
            <CardBody className="space-y-3">
              <div>
                <div className="flex items-center gap-2">
                  <Zap className="h-4 w-4" style={{ color: "var(--brand-500)" }} />
                  <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>{pb.name}</h3>
                  {pb.is_public ? (
                    <Badge variant="neutral" size="sm">System</Badge>
                  ) : (
                    <Badge variant="brand" size="sm">Custom</Badge>
                  )}
                </div>
                <p className="mt-1 text-xs" style={{ color: "var(--text-secondary)" }}>{pb.description}</p>
              </div>
              <div className="flex flex-wrap gap-1">
                {(pb.steps || []).map((step, i) => (
                  <Badge key={i} variant="neutral" size="sm">
                    {stepIcons[step.input_type] || "\u{1F50D}"} {step.scanner}
                  </Badge>
                ))}
              </div>
              <div className="flex gap-2">
                <Button
                  variant="secondary" size="sm"
                  leftIcon={<Play className="h-3.5 w-3.5" />}
                  className="flex-1"
                  onClick={() => { setActivePlaybook(pb); setSeedValue(""); }}
                >
                  Use Playbook
                </Button>
                <Button
                  variant="ghost" size="sm"
                  leftIcon={<History className="h-3.5 w-3.5" />}
                  onClick={() => setExpandedHistoryId(expandedHistoryId === pb.id ? null : pb.id)}
                  aria-pressed={expandedHistoryId === pb.id}
                >
                  History
                </Button>
              </div>

              {expandedHistoryId === pb.id && (
                <div className="border-t pt-3" style={{ borderColor: "var(--border-subtle)" }}>
                  <p className="text-[10px] font-semibold uppercase tracking-wider mb-2" style={{ color: "var(--text-tertiary)" }}>
                    Recent Runs
                  </p>
                  <PlaybookRunHistory playbookId={pb.id} />
                </div>
              )}
            </CardBody>
          </Card>
        ))}
      </div>
    </div>
  );
}
