import { useState } from "react";
import {
  Archive,
  Plus,
  Trash2,
  Lock,
  FileText,
  Camera,
  Globe,
  AlignLeft,
  Code,
  Terminal,
} from "lucide-react";
import { useEvidenceLocker, useCreateEvidenceLocker, useDeleteEvidenceLocker } from "./hooks";
import type { EvidenceItem } from "./types";
import { Badge } from "@/shared/components/Badge";
import { Button } from "@/shared/components/Button";
import { Input } from "@/shared/components/Input";

const typeIcons: Record<string, React.ElementType> = {
  screenshot: Camera,
  document: FileText,
  url: Globe,
  note: AlignLeft,
  artifact: Code,
  log: Terminal,
};

interface EvidenceCardProps {
  item: EvidenceItem;
  onDelete: (id: string) => void;
}

function EvidenceCard({ item, onDelete }: EvidenceCardProps) {
  const [expanded, setExpanded] = useState(false);
  const Icon = typeIcons[item.type] ?? FileText;

  return (
    <div
      className="rounded-lg border"
      style={{ background: "var(--bg-surface)", borderColor: "var(--border-default)" }}
    >
      <button className="w-full p-4 text-left" onClick={() => setExpanded(!expanded)}>
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-start gap-3 min-w-0">
            <Icon className="h-4 w-4 mt-0.5 shrink-0" style={{ color: "var(--brand-400)" }} />
            <div className="min-w-0">
              <p className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>
                {item.title}
              </p>
              <p className="text-xs" style={{ color: "var(--text-secondary)" }}>
                {item.description}
              </p>
              <div className="flex flex-wrap gap-1 mt-1">
                <Badge variant="neutral" size="sm">
                  {item.type}
                </Badge>
                {item.is_admissible && (
                  <Badge variant="neutral" size="sm">
                    <Lock className="inline h-2.5 w-2.5 mr-0.5" />
                    Admissible
                  </Badge>
                )}
                {(item.tags ?? []).map((t) => (
                  <Badge key={t} variant="neutral" size="sm">
                    {t}
                  </Badge>
                ))}
              </div>
            </div>
          </div>
          <button
            onClick={(e) => {
              e.stopPropagation();
              onDelete(item.id);
            }}
            className="shrink-0 p-1 rounded hover:bg-danger-900"
          >
            <Trash2 className="h-3.5 w-3.5" style={{ color: "var(--danger-400)" }} />
          </button>
        </div>
      </button>
      {expanded && (
        <div className="border-t px-4 pb-4" style={{ borderColor: "var(--border-subtle)" }}>
          <p
            className="text-xs font-medium mt-3 mb-2"
            style={{ color: "var(--text-secondary)" }}
          >
            Chain of Custody
          </p>
          {(item.chain_of_custody ?? []).map((c, i) => (
            <div key={i} className="text-xs" style={{ color: "var(--text-tertiary)" }}>
              {new Date(c.timestamp).toLocaleString()} —{" "}
              <strong>{c.action}</strong> by {c.user}: {c.notes}
            </div>
          ))}
          {item.hash_sha256 && (
            <p
              className="mt-2 font-mono text-xs break-all"
              style={{ color: "var(--text-tertiary)" }}
            >
              SHA256: {item.hash_sha256}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

interface AddEvidenceFormProps {
  onClose: () => void;
}

function AddEvidenceForm({ onClose }: AddEvidenceFormProps) {
  const [title, setTitle] = useState("");
  const [type, setType] = useState("note");
  const [description, setDescription] = useState("");
  const [tags, setTags] = useState("");
  const create = useCreateEvidenceLocker();

  const handleSubmit = () => {
    if (!title.trim()) return;
    create.mutate(
      {
        title: title.trim(),
        type,
        description: description.trim(),
        tags: tags
          .split(",")
          .map((t) => t.trim())
          .filter(Boolean),
      },
      { onSuccess: onClose },
    );
  };

  return (
    <div
      className="rounded-lg border p-4 space-y-3"
      style={{ background: "var(--bg-elevated)", borderColor: "var(--border-default)" }}
    >
      <Input
        placeholder="Evidence title..."
        value={title}
        onChange={(e) => setTitle(e.target.value)}
      />
      <select
        value={type}
        onChange={(e) => setType(e.target.value)}
        className="w-full rounded-md border px-3 py-2 text-sm"
        style={{
          background: "var(--bg-surface)",
          borderColor: "var(--border-default)",
          color: "var(--text-primary)",
        }}
      >
        {["screenshot", "document", "url", "note", "artifact", "log"].map((t) => (
          <option key={t} value={t}>
            {t}
          </option>
        ))}
      </select>
      <textarea
        value={description}
        onChange={(e) => setDescription(e.target.value)}
        placeholder="Description..."
        rows={3}
        className="w-full rounded-md border px-3 py-2 text-sm resize-none"
        style={{
          background: "var(--bg-surface)",
          borderColor: "var(--border-default)",
          color: "var(--text-primary)",
        }}
      />
      <Input
        placeholder="Tags (comma-separated)..."
        value={tags}
        onChange={(e) => setTags(e.target.value)}
      />
      <div className="flex gap-2 justify-end">
        <Button variant="ghost" onClick={onClose}>
          Cancel
        </Button>
        <Button onClick={handleSubmit} disabled={!title.trim() || create.isPending}>
          {create.isPending ? "Saving..." : "Log Evidence"}
        </Button>
      </div>
    </div>
  );
}

export function EvidenceLockerPage() {
  const { data: items = [], isLoading } = useEvidenceLocker();
  const deleteEvidence = useDeleteEvidenceLocker();
  const [showAdd, setShowAdd] = useState(false);
  const [typeFilter, setTypeFilter] = useState("all");

  const filtered = typeFilter === "all" ? items : items.filter((i) => i.type === typeFilter);

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Archive className="h-6 w-6" style={{ color: "var(--brand-500)" }} />
          <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>
            Evidence Locker
          </h1>
          <Badge variant="neutral" size="sm">
            {items.length}
          </Badge>
        </div>
        <Button leftIcon={<Plus className="h-4 w-4" />} onClick={() => setShowAdd(!showAdd)}>
          Log Evidence
        </Button>
      </div>

      {showAdd && <AddEvidenceForm onClose={() => setShowAdd(false)} />}

      <div className="flex gap-2 flex-wrap">
        {["all", "screenshot", "document", "url", "note", "artifact", "log"].map((t) => (
          <button
            key={t}
            onClick={() => setTypeFilter(t)}
            className={`rounded-md px-3 py-1.5 text-xs font-medium transition-all ${
              typeFilter === t
                ? "bg-brand-900 text-brand-400"
                : "text-text-secondary hover:bg-bg-overlay"
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {isLoading ? (
        <div className="py-8 text-center text-sm" style={{ color: "var(--text-tertiary)" }}>
          Loading evidence...
        </div>
      ) : filtered.length === 0 ? (
        <div
          className="rounded-xl border py-16 text-center"
          style={{ borderColor: "var(--border-subtle)" }}
        >
          <Archive
            className="mx-auto h-10 w-10 mb-3"
            style={{ color: "var(--text-tertiary)" }}
          />
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
            No evidence logged yet. Start logging screenshots, documents, and artifacts.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {filtered.map((item) => (
            <EvidenceCard
              key={item.id}
              item={item}
              onDelete={(id) => deleteEvidence.mutate(id)}
            />
          ))}
        </div>
      )}
    </div>
  );
}
