import { useState } from "react";
import { GitMerge, Plus, X, Search, Link2 } from "lucide-react";
import { useCorrelation } from "./hooks";
import { Badge } from "@/shared/components/Badge";
import { Button } from "@/shared/components/Button";
import { Input } from "@/shared/components/Input";
import { Card, CardBody, CardHeader } from "@/shared/components/Card";

const confColor = (c: number): string =>
  c >= 0.8 ? "var(--success-400)" : c >= 0.6 ? "var(--warning-400)" : "var(--danger-400)";

const typeLabel: Record<string, string> = {
  email_to_domain: "Email → Domain",
  ip_to_org: "IP → Org",
  username_cross_platform: "Username Cross-Platform",
  phone_to_person: "Phone → Person",
  domain_to_company: "Domain → Company",
};

export function CorrelationPage() {
  const [inputs, setInputs] = useState<string[]>(["", ""]);
  const [newInput, setNewInput] = useState("");
  const correlate = useCorrelation();

  const validInputs = inputs.filter((i) => i.trim());

  const addInput = () => {
    if (newInput.trim()) {
      setInputs((p) => [...p.filter((i) => i.trim()), newInput.trim(), ""]);
      setNewInput("");
    }
  };

  const removeInput = (idx: number) => setInputs((p) => p.filter((_, i) => i !== idx));

  const updateInput = (idx: number, val: string) =>
    setInputs((p) => p.map((v, i) => (i === idx ? val : v)));

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3">
        <GitMerge className="h-6 w-6" style={{ color: "var(--brand-500)" }} />
        <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>
          OSINT Correlation Engine
        </h1>
      </div>

      <Card>
        <CardHeader>
          <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
            Input Indicators
          </h3>
        </CardHeader>
        <CardBody className="space-y-2">
          {inputs.map((inp, i) => (
            <div key={i} className="flex gap-2">
              <Input
                placeholder={`Indicator ${i + 1} (email, IP, domain, username...)`}
                value={inp}
                onChange={(e) => updateInput(i, e.target.value)}
              />
              {inputs.length > 2 && (
                <button
                  onClick={() => removeInput(i)}
                  className="shrink-0 p-2 rounded hover:bg-bg-overlay"
                >
                  <X className="h-4 w-4" style={{ color: "var(--text-tertiary)" }} />
                </button>
              )}
            </div>
          ))}
          <div className="flex gap-2 pt-1">
            <div className="flex-1">
              <Input
                placeholder="Add another indicator..."
                value={newInput}
                onChange={(e) => setNewInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && addInput()}
              />
            </div>
            <Button variant="ghost" leftIcon={<Plus className="h-4 w-4" />} onClick={addInput}>
              Add
            </Button>
            <Button
              onClick={() => correlate.mutate(validInputs)}
              disabled={validInputs.length < 2 || correlate.isPending}
              leftIcon={<Search className="h-4 w-4" />}
            >
              {correlate.isPending ? "Correlating..." : `Correlate ${validInputs.length} Inputs`}
            </Button>
          </div>
        </CardBody>
      </Card>

      {correlate.data && (
        <div className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-3">
            {[
              { label: "Total Matches", value: correlate.data.total_matches },
              { label: "High Confidence", value: correlate.data.high_confidence_matches },
              { label: "Clusters", value: correlate.data.entity_clusters.length },
            ].map(({ label, value }) => (
              <div
                key={label}
                className="rounded-xl border p-4 text-center"
                style={{ background: "var(--bg-surface)", borderColor: "var(--border-subtle)" }}
              >
                <p className="text-3xl font-bold" style={{ color: "var(--text-primary)" }}>
                  {value}
                </p>
                <p className="text-xs mt-1" style={{ color: "var(--text-tertiary)" }}>
                  {label}
                </p>
              </div>
            ))}
          </div>

          {correlate.data.entity_clusters.length > 0 && (
            <Card>
              <CardHeader>
                <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
                  Entity Clusters
                </h3>
              </CardHeader>
              <CardBody className="space-y-3">
                {correlate.data.entity_clusters.map((c) => (
                  <div
                    key={c.cluster_id}
                    className="rounded-lg border p-3"
                    style={{ background: "var(--bg-elevated)", borderColor: "var(--border-subtle)" }}
                  >
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>
                        {c.label}
                      </span>
                      <Badge variant="neutral" size="sm">
                        {Math.round(c.confidence * 100)}% confidence
                      </Badge>
                    </div>
                    <div className="flex flex-wrap gap-1">
                      {c.entities.map((e) => (
                        <Badge key={e} variant="info" size="sm">
                          {e}
                        </Badge>
                      ))}
                    </div>
                  </div>
                ))}
              </CardBody>
            </Card>
          )}

          <Card>
            <CardHeader>
              <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
                Correlation Matches
              </h3>
            </CardHeader>
            <div className="divide-y" style={{ borderColor: "var(--border-subtle)" }}>
              {correlate.data.matches
                .sort((a, b) => b.confidence - a.confidence)
                .map((m) => (
                  <div key={m.id} className="px-4 py-3">
                    <div className="flex items-center justify-between gap-3 mb-1">
                      <span
                        className="text-xs font-medium"
                        style={{ color: "var(--text-secondary)" }}
                      >
                        {typeLabel[m.type] ?? m.type}
                      </span>
                      <span
                        className="text-sm font-bold"
                        style={{ color: confColor(m.confidence) }}
                      >
                        {Math.round(m.confidence * 100)}%
                      </span>
                    </div>
                    <div className="flex items-center gap-2 text-sm">
                      <span className="font-mono" style={{ color: "var(--text-primary)" }}>
                        {m.source_value}
                      </span>
                      <Link2
                        className="h-3 w-3 shrink-0"
                        style={{ color: "var(--text-tertiary)" }}
                      />
                      <span className="font-mono" style={{ color: "var(--brand-400)" }}>
                        {m.target_value}
                      </span>
                    </div>
                    <div className="mt-1 flex flex-wrap gap-1">
                      {m.evidence.map((e, i) => (
                        <span key={i} className="text-xs" style={{ color: "var(--text-tertiary)" }}>
                          · {e}
                        </span>
                      ))}
                    </div>
                  </div>
                ))}
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}
