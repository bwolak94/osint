import { useState } from "react";
import { Users, Plus, Copy, Check, Wifi } from "lucide-react";
import { useCollabSessions, useOnlineUsers, useCreateSession } from "./hooks";
import type { CollabSession } from "./types";
import { Badge } from "@/shared/components/Badge";
import { Button } from "@/shared/components/Button";
import { Input } from "@/shared/components/Input";
import { Card, CardBody, CardHeader } from "@/shared/components/Card";

function SessionCard({ session }: { session: CollabSession }) {
  const [copied, setCopied] = useState(false);
  const onlineCount = (session.participants ?? []).filter((p) => p.online).length;

  const copyLink = () => {
    navigator.clipboard.writeText(window.location.origin + session.share_link);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div
      className="rounded-lg border p-4"
      style={{ background: "var(--bg-surface)", borderColor: "var(--border-default)" }}
    >
      <div className="flex items-start justify-between">
        <div>
          <p className="font-medium" style={{ color: "var(--text-primary)" }}>
            {session.name}
          </p>
          <p className="text-xs mt-0.5" style={{ color: "var(--text-tertiary)" }}>
            Investigation: {session.investigation_id}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1">
            <Wifi className="h-3 w-3" style={{ color: "var(--success-400)" }} />
            <span className="text-xs" style={{ color: "var(--success-400)" }}>
              {onlineCount} online
            </span>
          </div>
          <Badge variant="neutral" size="sm">
            {session.status}
          </Badge>
        </div>
      </div>
      <div className="flex flex-wrap gap-1 mt-3">
        {(session.participants ?? []).map((p) => (
          <div
            key={p.user}
            className="flex items-center gap-1 rounded-full px-2 py-0.5 text-xs"
            style={{
              background: "var(--bg-elevated)",
              color: p.online ? "var(--success-400)" : "var(--text-tertiary)",
            }}
          >
            <div
              className={`h-1.5 w-1.5 rounded-full ${p.online ? "" : "opacity-40"}`}
              style={{ background: p.online ? "var(--success-400)" : "var(--text-tertiary)" }}
            />
            {p.user} {p.role === "owner" ? "(owner)" : ""}
          </div>
        ))}
      </div>
      <button
        onClick={copyLink}
        className="mt-3 flex items-center gap-1.5 text-xs transition-colors"
        style={{ color: "var(--brand-400)" }}
      >
        {copied ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
        {copied ? "Copied!" : "Copy share link"}
      </button>
    </div>
  );
}

export function CollaborationPage() {
  const { data: sessions = [] } = useCollabSessions();
  const { data: onlineData } = useOnlineUsers();
  const create = useCreateSession();
  const [showCreate, setShowCreate] = useState(false);
  const [name, setName] = useState("");
  const [invId, setInvId] = useState("");

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Users className="h-6 w-6" style={{ color: "var(--brand-500)" }} />
          <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>
            Real-time Collaboration
          </h1>
          {onlineData && (
            <Badge variant="neutral" size="sm">
              <Wifi className="inline h-3 w-3 mr-1" style={{ color: "var(--success-400)" }} />
              {onlineData.total_online} online
            </Badge>
          )}
        </div>
        <Button
          leftIcon={<Plus className="h-4 w-4" />}
          onClick={() => setShowCreate(!showCreate)}
        >
          New Session
        </Button>
      </div>

      {onlineData?.users && onlineData.users.length > 0 && (
        <Card>
          <CardHeader>
            <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
              Team Online Now
            </h3>
          </CardHeader>
          <CardBody>
            <div className="flex flex-wrap gap-3">
              {onlineData.users.map((u) => (
                <div key={u.user} className="flex items-center gap-2">
                  <div
                    className="flex h-8 w-8 items-center justify-center rounded-full text-sm font-bold"
                    style={{ background: "var(--brand-900)", color: "var(--brand-400)" }}
                  >
                    {u.avatar}
                  </div>
                  <div>
                    <p className="text-sm" style={{ color: "var(--text-primary)" }}>
                      {u.user}
                    </p>
                    <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>
                      {u.current_page}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </CardBody>
        </Card>
      )}

      {showCreate && (
        <Card>
          <CardBody className="space-y-3">
            <div className="grid gap-3 sm:grid-cols-2">
              <Input
                placeholder="Session name..."
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
              <Input
                placeholder="Investigation ID..."
                value={invId}
                onChange={(e) => setInvId(e.target.value)}
              />
            </div>
            <div className="flex gap-2 justify-end">
              <Button variant="ghost" onClick={() => setShowCreate(false)}>
                Cancel
              </Button>
              <Button
                onClick={() =>
                  create.mutate(
                    { name, investigationId: invId },
                    { onSuccess: () => setShowCreate(false) }
                  )
                }
                disabled={!name || create.isPending}
              >
                Create Session
              </Button>
            </div>
          </CardBody>
        </Card>
      )}

      {sessions.length === 0 && !showCreate ? (
        <div
          className="rounded-xl border py-16 text-center"
          style={{ borderColor: "var(--border-subtle)" }}
        >
          <Users
            className="mx-auto h-10 w-10 mb-3"
            style={{ color: "var(--text-tertiary)" }}
          />
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
            Create a collaboration session to work with your team in real-time
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {sessions.map((s) => (
            <SessionCard key={s.id} session={s} />
          ))}
        </div>
      )}
    </div>
  );
}
