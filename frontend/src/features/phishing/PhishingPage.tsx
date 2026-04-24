import { useState } from "react";
import { Mail, Plus, Play, AlertTriangle } from "lucide-react";
import {
  usePhishingTemplates,
  usePhishingCampaigns,
  useCreateCampaign,
  useLaunchCampaign,
} from "./hooks";
import type { PhishingCampaign } from "./types";
import { Badge } from "@/shared/components/Badge";
import { Button } from "@/shared/components/Button";
import { Input } from "@/shared/components/Input";

const statusVariant: Record<
  string,
  "neutral" | "info" | "warning" | "danger"
> = {
  draft: "neutral",
  running: "info",
  paused: "warning",
  completed: "neutral",
};

interface CampaignCardProps {
  campaign: PhishingCampaign;
}

function CampaignCard({ campaign }: CampaignCardProps) {
  const launch = useLaunchCampaign();
  const clickRate =
    campaign.sent_count > 0
      ? Math.round((campaign.clicked_count / campaign.sent_count) * 100)
      : 0;
  const openRate =
    campaign.sent_count > 0
      ? Math.round((campaign.opened_count / campaign.sent_count) * 100)
      : 0;

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
            {campaign.name}
          </p>
          <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>
            Auth: {campaign.authorized_by} · Eng: {campaign.engagement_id}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant={(statusVariant[campaign.status] ?? "neutral") as "success" | "warning" | "danger" | "info" | "neutral" | "brand"} size="sm">
            {campaign.status}
          </Badge>
          {campaign.status === "draft" && (
            <Button
              size="sm"
              leftIcon={<Play className="h-3 w-3" />}
              onClick={() => launch.mutate(campaign.id)}
              disabled={launch.isPending}
            >
              Launch
            </Button>
          )}
        </div>
      </div>
      <div className="grid grid-cols-4 gap-2 text-center">
        {[
          { label: "Targets", value: campaign.target_count, danger: false },
          { label: "Sent", value: campaign.sent_count, danger: false },
          { label: "Open Rate", value: `${openRate}%`, danger: false },
          {
            label: "Click Rate",
            value: `${clickRate}%`,
            danger: clickRate > 20,
          },
        ].map(({ label, value, danger }) => (
          <div
            key={label}
            className="rounded p-2"
            style={{ background: "var(--bg-elevated)" }}
          >
            <p
              className="text-sm font-bold"
              style={{
                color: danger ? "var(--danger-400)" : "var(--text-primary)",
              }}
            >
              {value}
            </p>
            <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>
              {label}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}

interface CreateCampaignFormProps {
  onClose: () => void;
}

function CreateCampaignForm({ onClose }: CreateCampaignFormProps) {
  const { data: templates = [] } = usePhishingTemplates();
  const create = useCreateCampaign();
  const [name, setName] = useState("");
  const [templateId, setTemplateId] = useState(templates[0]?.id ?? "t1");
  const [targetCount, setTargetCount] = useState(50);
  const [authorizedBy, setAuthorizedBy] = useState("");
  const [engagementId, setEngagementId] = useState("");

  const handleCreate = () => {
    if (!name.trim() || !authorizedBy.trim() || !engagementId.trim()) return;
    create.mutate(
      {
        name: name.trim(),
        template_id: templateId,
        target_count: targetCount,
        authorized_by: authorizedBy.trim(),
        engagement_id: engagementId.trim(),
      },
      { onSuccess: onClose }
    );
  };

  return (
    <div
      className="rounded-lg border p-4 space-y-3"
      style={{
        background: "var(--bg-elevated)",
        borderColor: "var(--border-default)",
      }}
    >
      <div
        className="flex items-center gap-2 rounded-lg border px-3 py-2"
        style={{
          background: "var(--warning-900)",
          borderColor: "var(--warning-500)",
        }}
      >
        <AlertTriangle
          className="h-4 w-4 shrink-0"
          style={{ color: "var(--warning-400)" }}
        />
        <p className="text-xs" style={{ color: "var(--warning-400)" }}>
          For authorized penetration testing only. Ensure written authorization
          is obtained before launching.
        </p>
      </div>
      <Input
        placeholder="Campaign name..."
        value={name}
        onChange={(e) => setName(e.target.value)}
      />
      <select
        value={templateId}
        onChange={(e) => setTemplateId(e.target.value)}
        className="w-full rounded-md border px-3 py-2 text-sm"
        style={{
          background: "var(--bg-surface)",
          borderColor: "var(--border-default)",
          color: "var(--text-primary)",
        }}
      >
        {templates.map((t) => (
          <option key={t.id} value={t.id}>
            {t.name} ({Math.round(t.success_rate_avg * 100)}% avg)
          </option>
        ))}
      </select>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label
            className="text-xs mb-1 block"
            style={{ color: "var(--text-secondary)" }}
          >
            Target Count
          </label>
          <input
            type="number"
            value={targetCount}
            onChange={(e) => setTargetCount(Number(e.target.value))}
            min={1}
            className="w-full rounded-md border px-3 py-2 text-sm"
            style={{
              background: "var(--bg-surface)",
              borderColor: "var(--border-default)",
              color: "var(--text-primary)",
            }}
          />
        </div>
        <div>
          <label
            className="text-xs mb-1 block"
            style={{ color: "var(--text-secondary)" }}
          >
            Engagement ID
          </label>
          <Input
            value={engagementId}
            onChange={(e) => setEngagementId(e.target.value)}
            placeholder="ENG-2024-001"
          />
        </div>
      </div>
      <Input
        placeholder="Authorized by (name/email)..."
        value={authorizedBy}
        onChange={(e) => setAuthorizedBy(e.target.value)}
      />
      <div className="flex gap-2 justify-end">
        <Button variant="ghost" onClick={onClose}>
          Cancel
        </Button>
        <Button
          onClick={handleCreate}
          disabled={
            !name.trim() ||
            !authorizedBy.trim() ||
            !engagementId.trim() ||
            create.isPending
          }
        >
          {create.isPending ? "Creating..." : "Create Campaign"}
        </Button>
      </div>
    </div>
  );
}

export function PhishingPage() {
  const { data: campaigns = [] } = usePhishingCampaigns();
  const [showCreate, setShowCreate] = useState(false);

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Mail
            className="h-6 w-6"
            style={{ color: "var(--brand-500)" }}
          />
          <h1
            className="text-xl font-semibold"
            style={{ color: "var(--text-primary)" }}
          >
            Phishing Campaign Manager
          </h1>
          <Badge variant="neutral" size="sm">
            Authorized Testing Only
          </Badge>
        </div>
        <Button
          leftIcon={<Plus className="h-4 w-4" />}
          onClick={() => setShowCreate(!showCreate)}
        >
          New Campaign
        </Button>
      </div>

      {showCreate && (
        <CreateCampaignForm onClose={() => setShowCreate(false)} />
      )}

      {campaigns.length === 0 && !showCreate ? (
        <div
          className="rounded-xl border py-16 text-center"
          style={{ borderColor: "var(--border-subtle)" }}
        >
          <Mail
            className="mx-auto h-10 w-10 mb-3"
            style={{ color: "var(--text-tertiary)" }}
          />
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
            No phishing simulations yet. Create one with proper authorization.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {campaigns.map((c) => (
            <CampaignCard key={c.id} campaign={c} />
          ))}
        </div>
      )}
    </div>
  );
}
