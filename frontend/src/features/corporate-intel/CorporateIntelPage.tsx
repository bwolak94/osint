import { useState } from "react";
import { Building2, Search, AlertTriangle } from "lucide-react";
import { useCorporateProfile } from "./hooks";
import { Badge } from "@/shared/components/Badge";
import { Button } from "@/shared/components/Button";
import { Input } from "@/shared/components/Input";
import { Card, CardBody, CardHeader } from "@/shared/components/Card";

export function CorporateIntelPage() {
  const [company, setCompany] = useState("");
  const profile = useCorporateProfile();

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3">
        <Building2 className="h-6 w-6" style={{ color: "var(--brand-500)" }} />
        <h1
          className="text-xl font-semibold"
          style={{ color: "var(--text-primary)" }}
        >
          Corporate Intelligence
        </h1>
      </div>

      <Card>
        <CardBody>
          <div className="flex gap-3">
            <div className="flex-1">
              <Input
                placeholder="Company name..."
                prefixIcon={<Building2 className="h-4 w-4" />}
                value={company}
                onChange={(e) => setCompany(e.target.value)}
                onKeyDown={(e) =>
                  e.key === "Enter" &&
                  company.trim() &&
                  profile.mutate({ company: company.trim() })
                }
              />
            </div>
            <Button
              onClick={() => profile.mutate({ company: company.trim() })}
              disabled={!company.trim() || profile.isPending}
              leftIcon={<Search className="h-4 w-4" />}
            >
              {profile.isPending ? "Profiling..." : "Profile Company"}
            </Button>
          </div>
        </CardBody>
      </Card>

      {profile.data && (
        <div className="space-y-4">
          <Card>
            <CardBody>
              <div className="flex items-start justify-between gap-4">
                <div>
                  <h2
                    className="text-xl font-bold"
                    style={{ color: "var(--text-primary)" }}
                  >
                    {profile.data.company_name}
                  </h2>
                  <p
                    className="text-sm"
                    style={{ color: "var(--text-secondary)" }}
                  >
                    {profile.data.industry} &middot; {profile.data.country}{" "}
                    &middot; Est. {profile.data.founded_year}
                  </p>
                  <p
                    className="text-sm mt-1"
                    style={{ color: "var(--brand-400)" }}
                  >
                    {profile.data.website}
                  </p>
                </div>
                <div className="text-right shrink-0">
                  <p
                    className="text-sm"
                    style={{ color: "var(--text-secondary)" }}
                  >
                    {profile.data.employee_count_range} employees
                  </p>
                  <p
                    className="text-sm"
                    style={{ color: "var(--text-secondary)" }}
                  >
                    {profile.data.revenue_range} revenue
                  </p>
                  <p
                    className="text-xs mt-1"
                    style={{ color: "var(--text-tertiary)" }}
                  >
                    {profile.data.open_jobs} open roles
                  </p>
                </div>
              </div>
              {profile.data.risk_indicators.length > 0 && (
                <div
                  className="mt-3 rounded-lg border p-3"
                  style={{
                    background: "var(--danger-900)",
                    borderColor: "var(--danger-500)",
                  }}
                >
                  {profile.data.risk_indicators.map((r, i) => (
                    <div
                      key={i}
                      className="flex items-start gap-2 text-xs"
                      style={{ color: "var(--danger-400)" }}
                    >
                      <AlertTriangle className="h-3 w-3 mt-0.5 shrink-0" />
                      {r}
                    </div>
                  ))}
                </div>
              )}
            </CardBody>
          </Card>

          <div className="grid gap-4 md:grid-cols-2">
            <Card>
              <CardHeader>
                <h3
                  className="text-sm font-semibold"
                  style={{ color: "var(--text-primary)" }}
                >
                  Key Executives
                </h3>
              </CardHeader>
              <CardBody className="space-y-3">
                {profile.data.executives.map((e) => (
                  <div key={e.name} className="flex items-start justify-between">
                    <div>
                      <p
                        className="text-sm font-medium"
                        style={{ color: "var(--text-primary)" }}
                      >
                        {e.name}
                      </p>
                      <p
                        className="text-xs"
                        style={{ color: "var(--text-tertiary)" }}
                      >
                        {e.title}
                      </p>
                      {e.email_pattern && (
                        <p
                          className="text-xs font-mono"
                          style={{ color: "var(--brand-400)" }}
                        >
                          {e.email_pattern}
                        </p>
                      )}
                    </div>
                    {e.linkedin_found && (
                      <Badge variant="info" size="sm">
                        LinkedIn
                      </Badge>
                    )}
                  </div>
                ))}
              </CardBody>
            </Card>

            <Card>
              <CardHeader>
                <h3
                  className="text-sm font-semibold"
                  style={{ color: "var(--text-primary)" }}
                >
                  Technologies
                </h3>
              </CardHeader>
              <CardBody>
                <div className="flex flex-wrap gap-2">
                  {profile.data.technologies.map((t) => (
                    <Badge key={t} variant="neutral">
                      {t}
                    </Badge>
                  ))}
                </div>
                <div className="mt-3">
                  <p
                    className="text-xs font-medium mb-1"
                    style={{ color: "var(--text-secondary)" }}
                  >
                    Known Domains
                  </p>
                  {profile.data.domains.map((d) => (
                    <p
                      key={d}
                      className="text-xs font-mono"
                      style={{ color: "var(--text-tertiary)" }}
                    >
                      {d}
                    </p>
                  ))}
                </div>
              </CardBody>
            </Card>

            <Card>
              <CardHeader>
                <h3
                  className="text-sm font-semibold"
                  style={{ color: "var(--text-primary)" }}
                >
                  Subsidiaries ({profile.data.subsidiaries.length})
                </h3>
              </CardHeader>
              <CardBody className="space-y-2">
                {profile.data.subsidiaries.map((s) => (
                  <div
                    key={s.name}
                    className="flex items-center justify-between"
                  >
                    <div>
                      <p
                        className="text-sm"
                        style={{ color: "var(--text-primary)" }}
                      >
                        {s.name}
                      </p>
                      <p
                        className="text-xs"
                        style={{ color: "var(--text-tertiary)" }}
                      >
                        {s.country}
                        {s.registration_number
                          ? ` \u00b7 ${s.registration_number}`
                          : ""}
                      </p>
                    </div>
                    <Badge
                      variant={s.active ? "neutral" : "danger"}
                      size="sm"
                    >
                      {s.active ? "Active" : "Inactive"}
                    </Badge>
                  </div>
                ))}
              </CardBody>
            </Card>
          </div>
        </div>
      )}

      {!profile.data && !profile.isPending && (
        <div
          className="rounded-xl border py-16 text-center"
          style={{ borderColor: "var(--border-subtle)" }}
        >
          <Building2
            className="mx-auto h-10 w-10 mb-3"
            style={{ color: "var(--text-tertiary)" }}
          />
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
            Profile any company to get executives, tech stack, subsidiaries and
            risk indicators
          </p>
        </div>
      )}
    </div>
  );
}
