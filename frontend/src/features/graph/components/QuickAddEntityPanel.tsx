import {
  useState,
  useCallback,
  useMemo,
  type ChangeEvent,
} from "react";
import { X, Plus, AlertCircle, CheckCircle2 } from "lucide-react";
import { Button } from "@/shared/components/Button";
import { Badge } from "@/shared/components/Badge";
import { Input } from "@/shared/components/Input";
import apiClient from "@/shared/api/client";

interface ManualEntity {
  type: string;
  value: string;
  notes: string;
  confidence: number;
}

interface ParsedLine {
  raw: string;
  entity: ManualEntity | null;
  error: string | null;
}

interface QuickAddEntityPanelProps {
  investigationId: string;
  open: boolean;
  onClose: () => void;
  onEntitiesAdded: (count: number) => void;
}

const VALID_TYPES = ["domain", "ip", "email", "username", "url", "phone"] as const;
type ValidType = (typeof VALID_TYPES)[number];

const TYPE_EXAMPLES: Record<ValidType, string> = {
  domain: "domain:example.com",
  ip: "ip:192.168.1.1",
  email: "email:user@example.com",
  username: "username:johndoe",
  url: "url:https://example.com/path",
  phone: "phone:+48123456789",
};

function parseLine(raw: string): ParsedLine {
  const trimmed = raw.trim();
  if (!trimmed) return { raw, entity: null, error: "Empty line" };

  const colonIdx = trimmed.indexOf(":");
  if (colonIdx === -1) {
    return { raw, entity: null, error: 'Missing ":" separator (format: type:value)' };
  }

  const type = trimmed.slice(0, colonIdx).trim().toLowerCase();
  const value = trimmed.slice(colonIdx + 1).trim();

  if (!VALID_TYPES.includes(type as ValidType)) {
    return {
      raw,
      entity: null,
      error: `Unknown type "${type}". Valid: ${VALID_TYPES.join(", ")}`,
    };
  }

  if (!value) {
    return { raw, entity: null, error: "Value cannot be empty" };
  }

  return {
    raw,
    entity: { type, value, notes: "", confidence: 0.7 },
    error: null,
  };
}

export function QuickAddEntityPanel({
  investigationId,
  open,
  onClose,
  onEntitiesAdded,
}: QuickAddEntityPanelProps) {
  const [mode, setMode] = useState<"bulk" | "single">("single");
  const [bulkText, setBulkText] = useState("");
  const [singleType, setSingleType] = useState<string>(VALID_TYPES[0]);
  const [singleValue, setSingleValue] = useState("");
  const [singleNotes, setSingleNotes] = useState("");
  const [singleConfidence, setSingleConfidence] = useState(0.7);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitSuccess, setSubmitSuccess] = useState(false);

  const parsedLines = useMemo<ParsedLine[]>(() => {
    if (mode !== "bulk" || !bulkText.trim()) return [];
    return bulkText
      .split("\n")
      .filter((l) => l.trim())
      .map(parseLine);
  }, [mode, bulkText]);

  const validEntities = useMemo(
    () => parsedLines.filter((l) => l.entity !== null).map((l) => l.entity as ManualEntity),
    [parsedLines],
  );

  const invalidCount = parsedLines.filter((l) => l.error !== null).length;

  const handleBulkChange = useCallback((e: ChangeEvent<HTMLTextAreaElement>) => {
    setBulkText(e.target.value);
    setSubmitError(null);
    setSubmitSuccess(false);
  }, []);

  const handleSubmit = useCallback(async () => {
    setSubmitError(null);
    setSubmitSuccess(false);
    setIsSubmitting(true);

    try {
      let entities: ManualEntity[] = [];

      if (mode === "bulk") {
        entities = validEntities;
      } else {
        if (!singleValue.trim()) {
          setSubmitError("Value is required");
          setIsSubmitting(false);
          return;
        }
        entities = [
          {
            type: singleType,
            value: singleValue.trim(),
            notes: singleNotes,
            confidence: singleConfidence,
          },
        ];
      }

      if (entities.length === 0) {
        setSubmitError("No valid entities to add");
        setIsSubmitting(false);
        return;
      }

      await apiClient.post(
        `/investigations/${investigationId}/nodes`,
        {
          nodes: entities.map((e) => ({
            ...e,
            provenance: "manual",
          })),
        },
      );

      setSubmitSuccess(true);
      onEntitiesAdded(entities.length);
      setBulkText("");
      setSingleValue("");
      setSingleNotes("");

      setTimeout(() => {
        onClose();
        setSubmitSuccess(false);
      }, 1200);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Failed to add entities";
      setSubmitError(message);
    } finally {
      setIsSubmitting(false);
    }
  }, [
    mode,
    validEntities,
    singleType,
    singleValue,
    singleNotes,
    singleConfidence,
    investigationId,
    onEntitiesAdded,
    onClose,
  ]);

  if (!open) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-40 bg-black/40"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Sheet panel */}
      <div
        className="fixed right-0 top-0 z-50 flex h-full w-full max-w-sm flex-col border-l shadow-2xl"
        style={{
          background: "var(--bg-surface)",
          borderColor: "var(--border-default)",
        }}
        role="dialog"
        aria-modal="true"
        aria-label="Add entities manually"
      >
        {/* Header */}
        <div
          className="flex items-center justify-between border-b px-5 py-4"
          style={{ borderColor: "var(--border-subtle)" }}
        >
          <div>
            <h2
              className="text-sm font-semibold"
              style={{ color: "var(--text-primary)" }}
            >
              Add Entities
            </h2>
            <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>
              Manually add nodes to the graph
            </p>
          </div>
          <button
            onClick={onClose}
            aria-label="Close panel"
            className="rounded-md p-1 transition-colors hover:bg-bg-overlay"
          >
            <X className="h-4 w-4" style={{ color: "var(--text-secondary)" }} />
          </button>
        </div>

        {/* Mode tabs */}
        <div
          className="flex border-b"
          style={{ borderColor: "var(--border-subtle)" }}
          role="tablist"
          aria-label="Add mode"
        >
          {(["single", "bulk"] as const).map((m) => (
            <button
              key={m}
              role="tab"
              aria-selected={mode === m}
              onClick={() => setMode(m)}
              className={`flex-1 py-2.5 text-xs font-medium transition-colors ${
                mode === m
                  ? "border-b-2 border-brand-500 text-text-primary"
                  : "text-text-tertiary hover:text-text-secondary"
              }`}
            >
              {m === "single" ? "Single Entity" : "Bulk Paste"}
            </button>
          ))}
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto px-5 py-4">
          {mode === "single" ? (
            <div className="space-y-4">
              {/* Type selector */}
              <div className="space-y-1.5">
                <label
                  className="block text-sm font-medium"
                  style={{ color: "var(--text-secondary)" }}
                >
                  Type
                </label>
                <select
                  value={singleType}
                  onChange={(e) => setSingleType(e.target.value)}
                  aria-label="Entity type"
                  className="block w-full rounded-md border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                  style={{
                    background: "var(--bg-elevated)",
                    borderColor: "var(--border-default)",
                    color: "var(--text-primary)",
                  }}
                >
                  {VALID_TYPES.map((t) => (
                    <option key={t} value={t}>
                      {t.charAt(0).toUpperCase() + t.slice(1)}
                    </option>
                  ))}
                </select>
              </div>

              {/* Value */}
              <Input
                label="Value"
                placeholder={`e.g. ${TYPE_EXAMPLES[singleType as ValidType]?.split(":").slice(1).join(":")}`}
                value={singleValue}
                onChange={(e) => setSingleValue(e.target.value)}
              />

              {/* Notes */}
              <div className="space-y-1.5">
                <label
                  className="block text-sm font-medium"
                  style={{ color: "var(--text-secondary)" }}
                >
                  Notes
                  <span className="ml-1 text-xs font-normal" style={{ color: "var(--text-tertiary)" }}>
                    (optional)
                  </span>
                </label>
                <textarea
                  value={singleNotes}
                  onChange={(e) => setSingleNotes(e.target.value)}
                  rows={3}
                  placeholder="Analyst notes..."
                  aria-label="Entity notes"
                  className="block w-full resize-none rounded-md border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                  style={{
                    background: "var(--bg-elevated)",
                    borderColor: "var(--border-default)",
                    color: "var(--text-primary)",
                  }}
                />
              </div>

              {/* Confidence */}
              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <label
                    className="text-sm font-medium"
                    style={{ color: "var(--text-secondary)" }}
                  >
                    Confidence
                  </label>
                  <span
                    className="text-xs font-mono"
                    style={{ color: "var(--text-secondary)" }}
                  >
                    {Math.round(singleConfidence * 100)}%
                  </span>
                </div>
                <input
                  type="range"
                  min={0}
                  max={100}
                  value={Math.round(singleConfidence * 100)}
                  onChange={(e) =>
                    setSingleConfidence(parseInt(e.target.value) / 100)
                  }
                  aria-label="Confidence level"
                  className="w-full accent-[var(--brand-500)]"
                />
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              {/* Format hint */}
              <div
                className="rounded-md border px-3 py-2"
                style={{
                  borderColor: "var(--border-subtle)",
                  background: "var(--bg-elevated)",
                }}
              >
                <p
                  className="mb-1 text-xs font-medium"
                  style={{ color: "var(--text-tertiary)" }}
                >
                  Format: <code className="font-mono">type:value</code> — one per line
                </p>
                <div className="space-y-0.5">
                  {Object.values(TYPE_EXAMPLES).map((ex) => (
                    <p
                      key={ex}
                      className="text-xs font-mono"
                      style={{ color: "var(--text-tertiary)" }}
                    >
                      {ex}
                    </p>
                  ))}
                </div>
              </div>

              {/* Textarea */}
              <div className="space-y-1.5">
                <label
                  className="block text-sm font-medium"
                  style={{ color: "var(--text-secondary)" }}
                >
                  Paste entities
                </label>
                <textarea
                  value={bulkText}
                  onChange={handleBulkChange}
                  rows={10}
                  placeholder={"domain:evil.com\nip:1.2.3.4\nemail:bad@actor.org"}
                  aria-label="Bulk entity input"
                  className="block w-full resize-none rounded-md border px-3 py-2 font-mono text-xs focus:outline-none focus:ring-2 focus:ring-brand-500"
                  style={{
                    background: "var(--bg-elevated)",
                    borderColor: "var(--border-default)",
                    color: "var(--text-primary)",
                  }}
                />
              </div>

              {/* Parse preview */}
              {parsedLines.length > 0 && (
                <div className="space-y-1">
                  <div className="flex items-center justify-between">
                    <span
                      className="text-xs font-medium"
                      style={{ color: "var(--text-secondary)" }}
                    >
                      Preview
                    </span>
                    <div className="flex gap-2">
                      <Badge variant="success" size="sm">
                        {validEntities.length} valid
                      </Badge>
                      {invalidCount > 0 && (
                        <Badge variant="danger" size="sm">
                          {invalidCount} invalid
                        </Badge>
                      )}
                    </div>
                  </div>
                  <div
                    className="max-h-40 overflow-y-auto rounded-md border"
                    style={{ borderColor: "var(--border-subtle)" }}
                  >
                    {parsedLines.map((line, idx) => (
                      <div
                        key={idx}
                        className="flex items-start gap-2 px-3 py-1.5"
                        style={{
                          background: line.error
                            ? "rgba(239,68,68,0.05)"
                            : "rgba(34,197,94,0.04)",
                          borderBottom: "1px solid var(--border-subtle)",
                        }}
                      >
                        {line.error ? (
                          <AlertCircle
                            className="mt-0.5 h-3 w-3 shrink-0"
                            style={{ color: "var(--danger-500, #ef4444)" }}
                          />
                        ) : (
                          <CheckCircle2
                            className="mt-0.5 h-3 w-3 shrink-0"
                            style={{ color: "var(--success-500, #22c55e)" }}
                          />
                        )}
                        <div className="min-w-0 flex-1">
                          <p
                            className="truncate font-mono text-xs"
                            style={{ color: "var(--text-primary)" }}
                          >
                            {line.raw}
                          </p>
                          {line.error && (
                            <p
                              className="text-[10px]"
                              style={{ color: "var(--danger-500, #ef4444)" }}
                            >
                              {line.error}
                            </p>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div
          className="border-t px-5 py-4 space-y-2"
          style={{ borderColor: "var(--border-subtle)" }}
        >
          {submitError && (
            <p className="text-xs" style={{ color: "var(--danger-500, #ef4444)" }}>
              {submitError}
            </p>
          )}
          {submitSuccess && (
            <p className="text-xs" style={{ color: "var(--success-500, #22c55e)" }}>
              Entities added successfully!
            </p>
          )}
          <div className="flex gap-2">
            <Button
              variant="ghost"
              size="sm"
              className="flex-1"
              onClick={onClose}
              disabled={isSubmitting}
            >
              Cancel
            </Button>
            <Button
              variant="primary"
              size="sm"
              className="flex-1"
              onClick={handleSubmit}
              loading={isSubmitting}
              leftIcon={<Plus className="h-3.5 w-3.5" />}
              disabled={
                isSubmitting ||
                (mode === "bulk" && validEntities.length === 0) ||
                (mode === "single" && !singleValue.trim())
              }
            >
              {mode === "bulk"
                ? `Add ${validEntities.length} Entit${validEntities.length !== 1 ? "ies" : "y"}`
                : "Add Entity"}
            </Button>
          </div>
        </div>
      </div>
    </>
  );
}
