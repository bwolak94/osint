import { Terminal, ExternalLink, AlertTriangle, CheckCircle, XCircle } from "lucide-react";
import { useC2Frameworks } from "./hooks";
import { Badge } from "@/shared/components/Badge";
import { Card, CardBody, CardHeader } from "@/shared/components/Card";

export function C2IntegrationPage() {
  const { data: frameworks = [] } = useC2Frameworks();

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3">
        <Terminal
          className="h-6 w-6"
          style={{ color: "var(--brand-500)" }}
        />
        <h1
          className="text-xl font-semibold"
          style={{ color: "var(--text-primary)" }}
        >
          C2 Framework Integration
        </h1>
        <Badge variant="warning" size="sm">
          Authorized Use Only
        </Badge>
      </div>

      <div
        className="flex items-center gap-2 rounded-lg border px-4 py-3"
        style={{
          background: "var(--warning-900)",
          borderColor: "var(--warning-500)",
        }}
      >
        <AlertTriangle
          className="h-4 w-4 shrink-0"
          style={{ color: "var(--warning-400)" }}
        />
        <span className="text-sm" style={{ color: "var(--warning-400)" }}>
          C2 framework integration is for authorized penetration testing
          engagements only. Ensure proper written authorization exists before
          connecting any framework.
        </span>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        {frameworks.map((fw) => (
          <Card key={fw.id}>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Terminal
                    className="h-4 w-4"
                    style={{ color: "var(--brand-400)" }}
                  />
                  <h3
                    className="text-sm font-semibold"
                    style={{ color: "var(--text-primary)" }}
                  >
                    {fw.name}
                  </h3>
                </div>
                <div className="flex items-center gap-2">
                  <Badge
                    variant={fw.type === "commercial" ? "warning" : "neutral"}
                    size="sm"
                  >
                    {fw.type.replace("_", " ")}
                  </Badge>
                  {fw.status === "connected" ? (
                    <CheckCircle
                      className="h-4 w-4"
                      style={{ color: "var(--success-400)" }}
                    />
                  ) : (
                    <XCircle
                      className="h-4 w-4"
                      style={{ color: "var(--text-tertiary)" }}
                    />
                  )}
                </div>
              </div>
            </CardHeader>
            <CardBody className="space-y-3">
              <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
                {fw.description}
              </p>
              <div className="flex flex-wrap gap-1">
                {fw.supported_protocols.map((p) => (
                  <Badge key={p} variant="neutral" size="sm">
                    {p}
                  </Badge>
                ))}
              </div>
              <div className="flex items-center justify-between">
                <Badge
                  variant={fw.status === "connected" ? "neutral" : "danger"}
                  size="sm"
                >
                  {fw.status.replace("_", " ")}
                </Badge>
                <a
                  href={fw.documentation_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-1 text-xs"
                  style={{ color: "var(--brand-400)" }}
                >
                  <ExternalLink className="h-3 w-3" />
                  Documentation
                </a>
              </div>
              <button
                className="w-full rounded-md border py-2 text-sm font-medium transition-colors hover:bg-bg-overlay"
                style={{
                  borderColor: "var(--border-default)",
                  color: "var(--text-secondary)",
                }}
              >
                {fw.status === "connected"
                  ? "Disconnect"
                  : "Configure Connection"}
              </button>
            </CardBody>
          </Card>
        ))}
      </div>
    </div>
  );
}
