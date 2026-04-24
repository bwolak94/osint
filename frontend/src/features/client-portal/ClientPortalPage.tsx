import { useState } from "react";
import { Globe, Plus, Copy, Check, Mail, Eye } from "lucide-react";
import { useClientPortals, useCreatePortal, useInviteClient } from "./hooks";
import type { ClientPortal } from "./types";
import { Badge } from "@/shared/components/Badge";
import { Button } from "@/shared/components/Button";
import { Input } from "@/shared/components/Input";
import { Card, CardBody, CardHeader } from "@/shared/components/Card";

const SECTIONS = [
  "executive_summary",
  "findings",
  "remediation_status",
  "timeline",
  "appendix",
];

function PortalCard({ portal }: { portal: ClientPortal }) {
  const [copied, setCopied] = useState(false);
  const [email, setEmail] = useState("");
  const [showInvite, setShowInvite] = useState(false);
  const invite = useInviteClient();

  const portalUrl = `${window.location.origin}/portal/${portal.access_token}`;

  const copy = () => {
    navigator.clipboard.writeText(portalUrl);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div
      className="rounded-lg border p-4"
      style={{
        background: "var(--bg-surface)",
        borderColor: "var(--border-default)",
      }}
    >
      <div className="flex items-start justify-between mb-3">
        <div>
          <p className="font-medium" style={{ color: "var(--text-primary)" }}>
            {portal.name}
          </p>
          <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>
            Client: {portal.client_name} · Eng: {portal.engagement_id}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span
            className="flex items-center gap-1 text-xs"
            style={{ color: "var(--text-tertiary)" }}
          >
            <Eye className="h-3 w-3" />
            {portal.view_count}
          </span>
          <Badge variant="neutral" size="sm">
            {portal.status}
          </Badge>
        </div>
      </div>
      <div className="flex flex-wrap gap-1 mb-3">
        {(portal.allowed_sections ?? []).map((s) => (
          <Badge key={s} variant="neutral" size="sm">
            {s.replace("_", " ")}
          </Badge>
        ))}
      </div>
      <div className="flex gap-2">
        <button
          onClick={copy}
          className="flex items-center gap-1.5 text-xs"
          style={{ color: "var(--brand-400)" }}
        >
          {copied ? (
            <Check className="h-3 w-3" />
          ) : (
            <Copy className="h-3 w-3" />
          )}
          {copied ? "Copied!" : "Copy Link"}
        </button>
        <button
          onClick={() => setShowInvite(!showInvite)}
          className="flex items-center gap-1.5 text-xs"
          style={{ color: "var(--text-secondary)" }}
        >
          <Mail className="h-3 w-3" /> Invite Client
        </button>
      </div>
      {showInvite && (
        <div className="flex gap-2 mt-2">
          <Input
            placeholder="client@company.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          <Button
            size="sm"
            onClick={() =>
              invite.mutate(
                { portalId: portal.id, email },
                {
                  onSuccess: () => {
                    setEmail("");
                    setShowInvite(false);
                  },
                }
              )
            }
            disabled={!email || invite.isPending}
          >
            Send
          </Button>
        </div>
      )}
    </div>
  );
}

export function ClientPortalPage() {
  const { data: portals = [] } = useClientPortals();
  const create = useCreatePortal();
  const [showCreate, setShowCreate] = useState(false);
  const [name, setName] = useState("");
  const [clientName, setClientName] = useState("");
  const [engId, setEngId] = useState("");
  const [sections, setSections] = useState([
    "executive_summary",
    "findings",
    "remediation_status",
  ]);

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Globe className="h-6 w-6" style={{ color: "var(--brand-500)" }} />
          <h1
            className="text-xl font-semibold"
            style={{ color: "var(--text-primary)" }}
          >
            Client Portal
          </h1>
          <Badge variant="neutral" size="sm">
            {portals.length} portals
          </Badge>
        </div>
        <Button
          leftIcon={<Plus className="h-4 w-4" />}
          onClick={() => setShowCreate(!showCreate)}
        >
          New Portal
        </Button>
      </div>

      {showCreate && (
        <Card>
          <CardHeader>
            <h3
              className="text-sm font-semibold"
              style={{ color: "var(--text-primary)" }}
            >
              Create Client Portal
            </h3>
          </CardHeader>
          <CardBody className="space-y-3">
            <div className="grid gap-3 sm:grid-cols-3">
              <Input
                placeholder="Portal name..."
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
              <Input
                placeholder="Client name..."
                value={clientName}
                onChange={(e) => setClientName(e.target.value)}
              />
              <Input
                placeholder="Engagement ID..."
                value={engId}
                onChange={(e) => setEngId(e.target.value)}
              />
            </div>
            <div>
              <p
                className="text-xs font-medium mb-2"
                style={{ color: "var(--text-secondary)" }}
              >
                Accessible Sections
              </p>
              <div className="flex flex-wrap gap-2">
                {SECTIONS.map((s) => (
                  <button
                    key={s}
                    onClick={() =>
                      setSections((prev) =>
                        prev.includes(s)
                          ? prev.filter((x) => x !== s)
                          : [...prev, s]
                      )
                    }
                    className="rounded px-3 py-1.5 text-xs font-medium transition-all"
                    style={{
                      background: sections.includes(s)
                        ? "var(--brand-900)"
                        : "var(--bg-elevated)",
                      color: sections.includes(s)
                        ? "var(--brand-400)"
                        : "var(--text-secondary)",
                      border: "1px solid",
                      borderColor: sections.includes(s)
                        ? "var(--brand-500)"
                        : "var(--border-default)",
                    }}
                  >
                    {s.replace("_", " ")}
                  </button>
                ))}
              </div>
            </div>
            <div className="flex gap-2 justify-end">
              <Button variant="ghost" onClick={() => setShowCreate(false)}>
                Cancel
              </Button>
              <Button
                onClick={() =>
                  create.mutate(
                    {
                      name,
                      client_name: clientName,
                      engagement_id: engId,
                      allowed_sections: sections,
                    },
                    { onSuccess: () => setShowCreate(false) }
                  )
                }
                disabled={!name || !clientName || create.isPending}
              >
                Create Portal
              </Button>
            </div>
          </CardBody>
        </Card>
      )}

      {portals.length === 0 && !showCreate ? (
        <div
          className="rounded-xl border py-16 text-center"
          style={{ borderColor: "var(--border-subtle)" }}
        >
          <Globe
            className="mx-auto h-10 w-10 mb-3"
            style={{ color: "var(--text-tertiary)" }}
          />
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
            Create secure portals to share findings and remediation status with
            clients
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {portals.map((p) => (
            <PortalCard key={p.id} portal={p} />
          ))}
        </div>
      )}
    </div>
  );
}
