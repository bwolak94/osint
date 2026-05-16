import { useState, useEffect } from "react";
import { Clock, Plus, Trash2, PlayCircle, PauseCircle } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import apiClient from "@/shared/api/client";

interface ScheduledJob {
  job_id: string;
  investigation_id: string;
  target: string;
  interval: string;
  next_run: string;
  is_active: boolean;
  description: string | null;
  scanners: string[];
}

export function ScanSchedulerPage() {
  const [jobs, setJobs] = useState<ScheduledJob[]>([]);
  const [loading, setLoading] = useState(false);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({
    investigation_id: "",
    target: "",
    interval: "daily",
    scanners: "shodan_bulk,dns_recon,cert_transparency",
    description: "",
  });

  const fetchJobs = async () => {
    try {
      const { data } = await apiClient.get<ScheduledJob[]>("/api/v1/scan-scheduler/jobs");
      setJobs(data);
    } catch (_) { /* ignore */ }
  };

  useEffect(() => { fetchJobs(); }, []);

  const handleCreate = async () => {
    if (!form.investigation_id.trim() || !form.target.trim()) return;
    setCreating(true);
    try {
      await apiClient.post("/api/v1/scan-scheduler/jobs", {
        ...form,
        scanners: form.scanners.split(",").map((s) => s.trim()).filter(Boolean),
      });
      await fetchJobs();
      setForm({ investigation_id: "", target: "", interval: "daily", scanners: "shodan_bulk,dns_recon,cert_transparency", description: "" });
    } catch (_) { /* ignore */ } finally {
      setCreating(false);
    }
  };

  const handleDelete = async (jobId: string) => {
    await apiClient.delete(`/api/v1/scan-scheduler/jobs/${jobId}`);
    setJobs((prev) => prev.filter((j) => j.job_id !== jobId));
  };

  const handleToggle = async (jobId: string) => {
    const { data } = await apiClient.patch<ScheduledJob>(`/api/v1/scan-scheduler/jobs/${jobId}/toggle`);
    setJobs((prev) => prev.map((j) => j.job_id === jobId ? data : j));
  };

  const intervalColor: Record<string, string> = {
    hourly: "bg-red-900/50 text-red-300",
    daily: "bg-blue-900/50 text-blue-300",
    weekly: "bg-green-900/50 text-green-300",
    monthly: "bg-purple-900/50 text-purple-300",
  };

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      <div className="flex items-center gap-3">
        <Clock className="h-7 w-7 text-blue-400" />
        <div>
          <h1 className="text-2xl font-bold text-white">Scan Scheduler</h1>
          <p className="text-sm text-gray-400">Schedule recurring OSINT scans on hourly, daily, weekly, or monthly intervals</p>
        </div>
      </div>

      <Card className="bg-gray-900 border-gray-700">
        <CardHeader><CardTitle className="text-sm">Create Scheduled Scan</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <Input placeholder="Investigation ID" value={form.investigation_id}
              onChange={(e) => setForm((p) => ({ ...p, investigation_id: e.target.value }))}
              className="bg-gray-800 border-gray-700 text-white" />
            <Input placeholder="Target (domain, email, IP)" value={form.target}
              onChange={(e) => setForm((p) => ({ ...p, target: e.target.value }))}
              className="bg-gray-800 border-gray-700 text-white" />
            <Input placeholder="Scanners (comma-separated)" value={form.scanners}
              onChange={(e) => setForm((p) => ({ ...p, scanners: e.target.value }))}
              className="bg-gray-800 border-gray-700 text-white" />
            <Select value={form.interval} onValueChange={(v) => setForm((p) => ({ ...p, interval: v }))}>
              <SelectTrigger className="bg-gray-800 border-gray-700 text-white">
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="bg-gray-800 border-gray-700">
                <SelectItem value="hourly">Hourly</SelectItem>
                <SelectItem value="daily">Daily</SelectItem>
                <SelectItem value="weekly">Weekly</SelectItem>
                <SelectItem value="monthly">Monthly</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <Input placeholder="Description (optional)" value={form.description}
            onChange={(e) => setForm((p) => ({ ...p, description: e.target.value }))}
            className="bg-gray-800 border-gray-700 text-white" />
          <Button onClick={handleCreate} disabled={creating} className="bg-blue-600 hover:bg-blue-700">
            <Plus className="h-4 w-4 mr-2" />{creating ? "Creating..." : "Create Schedule"}
          </Button>
        </CardContent>
      </Card>

      <div className="space-y-3">
        <h2 className="text-sm font-medium text-gray-400">{jobs.length} scheduled jobs</h2>
        {jobs.map((job) => (
          <Card key={job.job_id} className={`bg-gray-900 ${job.is_active ? "border-gray-700" : "border-gray-800 opacity-60"}`}>
            <CardContent className="pt-4">
              <div className="flex items-start justify-between">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <p className="text-white font-medium font-mono text-sm">{job.target}</p>
                    <Badge className={intervalColor[job.interval] || "bg-gray-700 text-gray-300"}>
                      {job.interval}
                    </Badge>
                    {!job.is_active && <Badge className="bg-gray-700 text-gray-400">paused</Badge>}
                  </div>
                  <p className="text-xs text-gray-500">Next: {new Date(job.next_run).toLocaleString()}</p>
                  {job.description && <p className="text-xs text-gray-400">{job.description}</p>}
                </div>
                <div className="flex gap-2">
                  <button onClick={() => handleToggle(job.job_id)} className="text-gray-400 hover:text-white transition-colors">
                    {job.is_active ? <PauseCircle className="h-5 w-5" /> : <PlayCircle className="h-5 w-5 text-green-400" />}
                  </button>
                  <button onClick={() => handleDelete(job.job_id)} className="text-gray-400 hover:text-red-400 transition-colors">
                    <Trash2 className="h-5 w-5" />
                  </button>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
        {jobs.length === 0 && (
          <p className="text-center text-gray-500 py-8">No scheduled scans yet</p>
        )}
      </div>
    </div>
  );
}
