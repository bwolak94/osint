import { useState } from "react";
import {
  ClipboardCheck,
  Plus,
  CheckCircle2,
  Circle,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { useAssessments, useMethodologySteps, useCreateAssessment, useCompleteStep } from "./hooks";
import type { Assessment, MethodologyStep } from "./types";
import { Badge } from "@/shared/components/Badge";
import { Button } from "@/shared/components/Button";
import { Input } from "@/shared/components/Input";
import { Card, CardBody, CardHeader } from "@/shared/components/Card";

function StepCard({
  step,
  completed,
  onComplete,
}: {
  step: MethodologyStep;
  completed: boolean;
  onComplete: () => void;
}) {
  const [expanded, setExpanded] = useState(false);
  return (
    <div
      className={`rounded-lg border ${completed ? "opacity-60" : ""}`}
      style={{
        borderColor: completed ? "var(--border-subtle)" : "var(--border-default)",
        background: "var(--bg-surface)",
      }}
    >
      <button
        className="w-full flex items-start gap-3 p-4 text-left"
        onClick={() => setExpanded(!expanded)}
      >
        <button
          onClick={(e) => {
            e.stopPropagation();
            if (!completed) onComplete();
          }}
          className="mt-0.5 shrink-0"
        >
          {completed ? (
            <CheckCircle2 className="h-5 w-5" style={{ color: "var(--success-400)" }} />
          ) : (
            <Circle className="h-5 w-5" style={{ color: "var(--text-tertiary)" }} />
          )}
        </button>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span
              className="text-xs font-medium px-2 py-0.5 rounded"
              style={{ background: "var(--bg-elevated)", color: "var(--text-secondary)" }}
            >
              {step.phase}
            </span>
            {step.required && (
              <Badge variant="danger" size="sm">
                Required
              </Badge>
            )}
          </div>
          <p className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>
            {step.name}
          </p>
          <p className="text-xs mt-0.5" style={{ color: "var(--text-secondary)" }}>
            {step.description}
          </p>
        </div>
        {expanded ? (
          <ChevronUp className="h-4 w-4 shrink-0" style={{ color: "var(--text-tertiary)" }} />
        ) : (
          <ChevronDown className="h-4 w-4 shrink-0" style={{ color: "var(--text-tertiary)" }} />
        )}
      </button>
      {expanded && (
        <div
          className="border-t px-4 pb-4"
          style={{ borderColor: "var(--border-subtle)" }}
        >
          <p
            className="text-xs font-medium mt-3 mb-1"
            style={{ color: "var(--text-secondary)" }}
          >
            Checklist
          </p>
          <ul className="space-y-1">
            {(step.checklist_items ?? []).map((item, i) => (
              <li
                key={i}
                className="flex items-center gap-2 text-xs"
                style={{ color: "var(--text-tertiary)" }}
              >
                <CheckCircle2
                  className="h-3 w-3 shrink-0"
                  style={{ color: completed ? "var(--success-400)" : "var(--text-tertiary)" }}
                />
                {item}
              </li>
            ))}
          </ul>
          {(step.references?.length ?? 0) > 0 && (
            <p className="mt-2 text-xs" style={{ color: "var(--text-tertiary)" }}>
              Ref: {(step.references ?? []).join(", ")}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

function AssessmentDetail({ assessment }: { assessment: Assessment }) {
  const { data: steps = [] } = useMethodologySteps();
  const completeStep = useCompleteStep();

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-3">
        <div
          className="flex-1 h-3 rounded-full overflow-hidden"
          style={{ background: "var(--bg-elevated)" }}
        >
          <div
            className="h-full rounded-full transition-all"
            style={{ width: `${assessment.completion_percentage}%`, background: "var(--brand-500)" }}
          />
        </div>
        <span className="text-sm font-bold" style={{ color: "var(--text-primary)" }}>
          {assessment.completion_percentage}%
        </span>
      </div>
      <div className="space-y-2">
        {steps.map((step) => (
          <StepCard
            key={step.id}
            step={step}
            completed={(assessment.completed_steps ?? []).includes(step.id)}
            onComplete={() =>
              completeStep.mutate({ assessmentId: assessment.id, stepId: step.id })
            }
          />
        ))}
      </div>
    </div>
  );
}

export function MethodologyPage() {
  const { data: assessments = [] } = useAssessments();
  const create = useCreateAssessment();
  const [showCreate, setShowCreate] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [engId, setEngId] = useState("");

  const selected = assessments.find((a) => a.id === selectedId);

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <ClipboardCheck className="h-6 w-6" style={{ color: "var(--brand-500)" }} />
          <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>
            Pentest Methodology
          </h1>
        </div>
        <Button
          leftIcon={<Plus className="h-4 w-4" />}
          onClick={() => setShowCreate(!showCreate)}
        >
          New Assessment
        </Button>
      </div>

      {showCreate && (
        <Card>
          <CardBody className="space-y-3">
            <div className="grid gap-3 sm:grid-cols-2">
              <Input
                placeholder="Assessment name..."
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
                    { name, methodology: "PTES", engagementId: engId },
                    {
                      onSuccess: (a) => {
                        setShowCreate(false);
                        setSelectedId(a.id);
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
          {assessments.map((a) => (
            <button
              key={a.id}
              onClick={() => setSelectedId(a.id === selectedId ? null : a.id)}
              className="w-full rounded-lg border p-3 text-left transition-all"
              style={{
                background: a.id === selectedId ? "var(--brand-900)" : "var(--bg-surface)",
                borderColor: a.id === selectedId ? "var(--brand-500)" : "var(--border-default)",
              }}
            >
              <p className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>
                {a.name}
              </p>
              <p className="text-xs mt-1" style={{ color: "var(--text-tertiary)" }}>
                {a.methodology} · {a.completion_percentage}% complete
              </p>
              <div
                className="mt-2 h-1.5 rounded-full overflow-hidden"
                style={{ background: "var(--bg-elevated)" }}
              >
                <div
                  className="h-full rounded-full"
                  style={{
                    width: `${a.completion_percentage}%`,
                    background: "var(--brand-500)",
                  }}
                />
              </div>
            </button>
          ))}
          {assessments.length === 0 && (
            <p className="text-sm text-center py-8" style={{ color: "var(--text-tertiary)" }}>
              No assessments yet
            </p>
          )}
        </div>
        {selected && (
          <div className="md:col-span-2">
            <Card>
              <CardHeader>
                <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
                  {selected.name}
                </h3>
              </CardHeader>
              <CardBody>
                <AssessmentDetail assessment={selected} />
              </CardBody>
            </Card>
          </div>
        )}
      </div>
    </div>
  );
}
