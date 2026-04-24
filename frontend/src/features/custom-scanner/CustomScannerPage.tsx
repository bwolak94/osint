import { useState } from "react";
import { Cpu, Plus, Play, PlusCircle, CheckCircle } from "lucide-react";
import { Badge } from "@/shared/components/Badge";
import { Button } from "@/shared/components/Button";
import { Card, CardHeader, CardBody } from "@/shared/components/Card";
import { Input } from "@/shared/components/Input";
import { useCustomScanners, useCreateScanner, useAddStep, useRunScanner } from "./hooks";
import type { CustomScanner, ScanResult } from "./types";

const STEP_TYPES = ["http_request", "dns_lookup", "port_check", "regex_extract", "python_script"];
const INPUT_TYPES = ["ip", "domain", "email", "url"];

function ScannerCard({ scanner }: { scanner: CustomScanner }) {
  const addStep = useAddStep();
  const runScanner = useRunScanner();
  const [stepType, setStepType] = useState("http_request");
  const [outputKey, setOutputKey] = useState("");
  const [inputVal, setInputVal] = useState("");
  const [result, setResult] = useState<ScanResult | null>(null);
  const [showStepForm, setShowStepForm] = useState(false);

  const handleAddStep = () => {
    if (!outputKey.trim()) return;
    addStep.mutate({ scannerId: scanner.id, stepType, outputKey: outputKey.trim() }, {
      onSuccess: () => { setOutputKey(""); setShowStepForm(false); },
    });
  };

  const handleRun = () => {
    if (!inputVal.trim()) return;
    runScanner.mutate({ scannerId: scanner.id, inputValue: inputVal.trim() }, {
      onSuccess: (data) => setResult(data),
    });
  };

  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between gap-3">
          <div>
            <div className="flex items-center gap-2">
              <Cpu className="h-4 w-4" style={{ color: "var(--brand-500)" }} />
              <span className="font-semibold text-sm" style={{ color: "var(--text-primary)" }}>{scanner.name}</span>
              <Badge variant="neutral" size="sm">input: {scanner.input_type}</Badge>
              {scanner.enabled && <Badge variant="success" size="sm">enabled</Badge>}
            </div>
            <p className="mt-0.5 text-xs" style={{ color: "var(--text-tertiary)" }}>{scanner.description}</p>
          </div>
          <div className="flex gap-2 shrink-0">
            <Button size="sm" variant="ghost" leftIcon={<PlusCircle className="h-3.5 w-3.5" />} onClick={() => setShowStepForm((p) => !p)}>
              Add Step
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardBody className="space-y-3">
        {scanner.steps.length > 0 && (
          <div className="space-y-1">
            <p className="text-xs font-medium" style={{ color: "var(--text-tertiary)" }}>Pipeline ({scanner.steps.length} steps)</p>
            {scanner.steps.map((step, i) => (
              <div key={step.id} className="flex items-center gap-2 rounded-md px-3 py-1.5" style={{ background: "var(--bg-elevated)" }}>
                <span className="text-xs font-mono" style={{ color: "var(--text-tertiary)" }}>{i + 1}.</span>
                <Badge variant="info" size="sm">{step.type.replace("_", " ")}</Badge>
                <span className="text-xs" style={{ color: "var(--text-secondary)" }}>→ <code>{step.output_key}</code></span>
              </div>
            ))}
          </div>
        )}

        {showStepForm && (
          <div className="space-y-2 rounded-md border p-3" style={{ borderColor: "var(--border-default)" }}>
            <p className="text-xs font-medium" style={{ color: "var(--text-secondary)" }}>Add pipeline step</p>
            <div className="flex flex-wrap gap-1">
              {STEP_TYPES.map((s) => (
                <button
                  key={s}
                  onClick={() => setStepType(s)}
                  className={`rounded px-2 py-1 text-xs transition-colors ${stepType === s ? "bg-brand-900 text-brand-400" : "text-text-secondary hover:bg-bg-overlay"}`}
                >{s.replace("_", " ")}</button>
              ))}
            </div>
            <Input placeholder="Output key (e.g. dns_result)" value={outputKey} onChange={(e) => setOutputKey(e.target.value)} />
            <Button size="sm" onClick={handleAddStep} loading={addStep.isPending}>Add</Button>
          </div>
        )}

        <div className="flex gap-2">
          <Input placeholder={`Test input (${scanner.input_type})`} value={inputVal} onChange={(e) => setInputVal(e.target.value)} />
          <Button size="sm" leftIcon={<Play className="h-3.5 w-3.5" />} onClick={handleRun} loading={runScanner.isPending} disabled={!inputVal.trim()}>
            Run
          </Button>
        </div>

        {result && (
          <div className="rounded-md p-3" style={{ background: "var(--bg-elevated)" }}>
            <div className="flex items-center gap-2 mb-2">
              <CheckCircle className="h-3.5 w-3.5" style={{ color: "var(--success-400)" }} />
              <span className="text-xs font-medium" style={{ color: "var(--success-400)" }}>Scan completed</span>
            </div>
            <pre className="text-xs overflow-x-auto" style={{ color: "var(--text-secondary)" }}>{JSON.stringify(result.results, null, 2)}</pre>
          </div>
        )}

        <div className="flex gap-4 text-xs" style={{ color: "var(--text-tertiary)" }}>
          <span>Runs: {scanner.run_count}</span>
          {scanner.last_run && <span>Last: {new Date(scanner.last_run).toLocaleString()}</span>}
        </div>
      </CardBody>
    </Card>
  );
}

export function CustomScannerPage() {
  const { data: scanners = [], isLoading } = useCustomScanners();
  const createScanner = useCreateScanner();
  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [desc, setDesc] = useState("");
  const [inputType, setInputType] = useState("domain");

  const handleCreate = () => {
    if (!name.trim()) return;
    createScanner.mutate({ name: name.trim(), description: desc.trim(), input_type: inputType }, {
      onSuccess: () => { setShowForm(false); setName(""); setDesc(""); },
    });
  };

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Cpu className="h-6 w-6" style={{ color: "var(--brand-500)" }} />
          <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>Custom Scanner Builder</h1>
          <Badge variant="neutral" size="sm">{scanners.length}</Badge>
        </div>
        <Button leftIcon={<Plus className="h-4 w-4" />} onClick={() => setShowForm((p) => !p)}>
          New Scanner
        </Button>
      </div>

      {showForm && (
        <Card>
          <CardBody className="space-y-3">
            <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Create Scanner</h3>
            <Input placeholder="Scanner name" value={name} onChange={(e) => setName(e.target.value)} />
            <Input placeholder="Description" value={desc} onChange={(e) => setDesc(e.target.value)} />
            <div>
              <p className="mb-2 text-xs font-medium" style={{ color: "var(--text-tertiary)" }}>Input type</p>
              <div className="flex gap-1">
                {INPUT_TYPES.map((t) => (
                  <button key={t} onClick={() => setInputType(t)}
                    className={`rounded-md px-3 py-1 text-xs font-medium transition-colors ${inputType === t ? "bg-brand-900 text-brand-400" : "text-text-secondary hover:bg-bg-overlay"}`}
                  >{t}</button>
                ))}
              </div>
            </div>
            <div className="flex gap-2">
              <Button size="sm" onClick={handleCreate} loading={createScanner.isPending}>Create</Button>
              <Button size="sm" variant="ghost" onClick={() => setShowForm(false)}>Cancel</Button>
            </div>
          </CardBody>
        </Card>
      )}

      {isLoading ? (
        <div className="py-12 text-center text-sm" style={{ color: "var(--text-tertiary)" }}>Loading...</div>
      ) : scanners.length === 0 ? (
        <Card><CardBody><p className="text-center text-sm" style={{ color: "var(--text-tertiary)" }}>No custom scanners yet. Build your first pipeline scanner.</p></CardBody></Card>
      ) : (
        <div className="space-y-4">
          {scanners.map((s) => <ScannerCard key={s.id} scanner={s} />)}
        </div>
      )}
    </div>
  );
}
