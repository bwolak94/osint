import { useState } from "react";
import { Lock, Plus, Eye, Trash2, Tag } from "lucide-react";
import {
  useSecureNotes,
  useCreateNote,
  useDecryptNote,
  useDeleteNote,
} from "./hooks";
import type { SecureNote } from "./types";
import { Badge } from "@/shared/components/Badge";
import { Button } from "@/shared/components/Button";
import { Input } from "@/shared/components/Input";
import { Card, CardBody, CardHeader } from "@/shared/components/Card";

function NoteCard({ note }: { note: SecureNote }) {
  const [revealed, setRevealed] = useState(false);
  const [content, setContent] = useState<string | null>(null);
  const decrypt = useDecryptNote();
  const deleteNote = useDeleteNote();

  const handleReveal = async () => {
    if (revealed) {
      setRevealed(false);
      setContent(null);
      return;
    }
    const c = await decrypt.mutateAsync(note.id);
    setContent(c);
    setRevealed(true);
  };

  return (
    <div
      className="rounded-lg border p-4"
      style={{
        background: "var(--bg-surface)",
        borderColor: "var(--border-default)",
      }}
    >
      <div className="flex items-start justify-between">
        <div className="flex items-start gap-2">
          <Lock
            className="h-4 w-4 mt-0.5 shrink-0"
            style={{ color: "var(--brand-400)" }}
          />
          <div>
            <p
              className="text-sm font-medium"
              style={{ color: "var(--text-primary)" }}
            >
              {note.title}
            </p>
            <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>
              {note.word_count} words ·{" "}
              {new Date(note.created_at).toLocaleDateString()}
            </p>
          </div>
        </div>
        <div className="flex gap-1">
          <button
            onClick={handleReveal}
            className="rounded p-1 hover:bg-bg-overlay"
            aria-label={revealed ? "Hide note content" : "Reveal note content"}
          >
            <Eye
              className="h-3.5 w-3.5"
              style={{ color: "var(--text-tertiary)" }}
            />
          </button>
          <button
            onClick={() => deleteNote.mutate(note.id)}
            className="rounded p-1"
            style={{ background: "transparent" }}
            aria-label="Delete note"
          >
            <Trash2
              className="h-3.5 w-3.5"
              style={{ color: "var(--danger-400)" }}
            />
          </button>
        </div>
      </div>
      {(note.tags ?? []).length > 0 && (
        <div className="flex flex-wrap gap-1 mt-2">
          {(note.tags ?? []).map((t) => (
            <Badge key={t} variant="neutral" size="sm">
              {t}
            </Badge>
          ))}
        </div>
      )}
      {revealed && content && (
        <div
          className="mt-3 rounded border p-3 font-mono text-xs whitespace-pre-wrap"
          style={{
            background: "var(--bg-elevated)",
            borderColor: "var(--border-subtle)",
            color: "var(--text-secondary)",
          }}
        >
          {content}
        </div>
      )}
    </div>
  );
}

export function SecureNotesPage() {
  const { data: notes = [] } = useSecureNotes();
  const create = useCreateNote();
  const [showCreate, setShowCreate] = useState(false);
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [tags, setTags] = useState("");

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Lock className="h-6 w-6" style={{ color: "var(--brand-500)" }} />
          <h1
            className="text-xl font-semibold"
            style={{ color: "var(--text-primary)" }}
          >
            Secure Encrypted Notes
          </h1>
          <Badge variant="neutral" size="sm">
            {notes.length} notes
          </Badge>
        </div>
        <Button
          leftIcon={<Plus className="h-4 w-4" />}
          onClick={() => setShowCreate(!showCreate)}
        >
          New Note
        </Button>
      </div>

      {showCreate && (
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <Lock
                className="h-4 w-4"
                style={{ color: "var(--brand-400)" }}
              />
              <h3
                className="text-sm font-semibold"
                style={{ color: "var(--text-primary)" }}
              >
                New Encrypted Note
              </h3>
            </div>
          </CardHeader>
          <CardBody className="space-y-3">
            <Input
              placeholder="Note title..."
              value={title}
              onChange={(e) => setTitle(e.target.value)}
            />
            <textarea
              value={content}
              onChange={(e) => setContent(e.target.value)}
              placeholder="Sensitive content (will be encrypted at rest)..."
              rows={6}
              className="w-full rounded-md border px-3 py-2 text-sm resize-none font-mono"
              style={{
                background: "var(--bg-surface)",
                borderColor: "var(--border-default)",
                color: "var(--text-primary)",
              }}
            />
            <Input
              placeholder="Tags (comma-separated)..."
              prefixIcon={<Tag className="h-4 w-4" />}
              value={tags}
              onChange={(e) => setTags(e.target.value)}
            />
            <div className="flex gap-2 justify-end">
              <Button variant="ghost" onClick={() => setShowCreate(false)}>
                Cancel
              </Button>
              <Button
                leftIcon={<Lock className="h-4 w-4" />}
                onClick={() =>
                  create.mutate(
                    {
                      title,
                      content,
                      tags: tags
                        .split(",")
                        .map((t) => t.trim())
                        .filter(Boolean),
                    },
                    {
                      onSuccess: () => {
                        setShowCreate(false);
                        setTitle("");
                        setContent("");
                        setTags("");
                      },
                    }
                  )
                }
                disabled={!title || !content || create.isPending}
              >
                {create.isPending ? "Encrypting..." : "Save Encrypted"}
              </Button>
            </div>
          </CardBody>
        </Card>
      )}

      {notes.length === 0 && !showCreate ? (
        <div
          className="rounded-xl border py-16 text-center"
          style={{ borderColor: "var(--border-subtle)" }}
        >
          <Lock
            className="mx-auto h-10 w-10 mb-3"
            style={{ color: "var(--text-tertiary)" }}
          />
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
            Store sensitive notes securely with encryption at rest
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {notes.map((n) => (
            <NoteCard key={n.id} note={n} />
          ))}
        </div>
      )}
    </div>
  );
}
