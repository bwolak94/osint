import { useState } from "react";
import { Phone, Search, Mail, User } from "lucide-react";
import { usePhoneLookup } from "./hooks";
import { Badge } from "@/shared/components/Badge";
import { Button } from "@/shared/components/Button";
import { Input } from "@/shared/components/Input";
import { Card, CardBody, CardHeader } from "@/shared/components/Card";

const riskVariant: Record<string, "danger" | "warning" | "neutral"> = {
  high: "danger",
  medium: "warning",
  low: "neutral",
};

const spamColor = (score: number): string =>
  score > 70 ? "var(--danger-400)" : score > 40 ? "var(--warning-400)" : "var(--success-400)";

export function PhoneIntelPage() {
  const [phone, setPhone] = useState("");
  const lookup = usePhoneLookup();

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3">
        <Phone className="h-6 w-6" style={{ color: "var(--brand-500)" }} />
        <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>
          Phone Number Intelligence
        </h1>
      </div>

      <Card>
        <CardBody>
          <div className="flex gap-3">
            <div className="flex-1">
              <Input
                placeholder="+1 (555) 555-5555..."
                prefixIcon={<Phone className="h-4 w-4" />}
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                onKeyDown={(e) =>
                  e.key === "Enter" && phone.trim() && lookup.mutate(phone.trim())
                }
              />
            </div>
            <Button
              onClick={() => lookup.mutate(phone.trim())}
              disabled={!phone.trim() || lookup.isPending}
              leftIcon={<Search className="h-4 w-4" />}
            >
              {lookup.isPending ? "Looking up..." : "Lookup"}
            </Button>
          </div>
        </CardBody>
      </Card>

      {lookup.data && (
        <div className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {[
              {
                label: "Spam Score",
                value: lookup.data.spam_score,
                color: spamColor(lookup.data.spam_score),
                suffix: "/100",
              },
              { label: "Spam Reports", value: lookup.data.spam_reports, color: "var(--text-primary)" },
              {
                label: "Breach Count",
                value: lookup.data.breach_count,
                color:
                  lookup.data.breach_count > 0 ? "var(--danger-400)" : "var(--success-400)",
              },
              {
                label: "Social Profiles",
                value: lookup.data.social_profiles_found.length,
                color: "var(--text-primary)",
              },
            ].map(({ label, value, color, suffix }) => (
              <div
                key={label}
                className="rounded-xl border p-4 text-center"
                style={{ background: "var(--bg-surface)", borderColor: "var(--border-subtle)" }}
              >
                <p className="text-3xl font-bold" style={{ color }}>
                  {value}
                  {suffix}
                </p>
                <p className="text-xs mt-1" style={{ color: "var(--text-tertiary)" }}>
                  {label}
                </p>
              </div>
            ))}
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <Card>
              <CardHeader>
                <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
                  Number Details
                </h3>
              </CardHeader>
              <CardBody className="space-y-3">
                {[
                  { label: "Carrier", value: lookup.data.carrier.name },
                  { label: "Line Type", value: lookup.data.line_type },
                  {
                    label: "Country",
                    value: `${lookup.data.country} (${lookup.data.country_code})`,
                  },
                  { label: "Location", value: lookup.data.location ?? "Unknown" },
                  { label: "Timezone", value: lookup.data.timezone },
                ].map(({ label, value }) => (
                  <div key={label} className="flex items-center justify-between">
                    <span className="text-sm" style={{ color: "var(--text-secondary)" }}>
                      {label}
                    </span>
                    <span
                      className="text-sm font-medium"
                      style={{ color: "var(--text-primary)" }}
                    >
                      {value}
                    </span>
                  </div>
                ))}
                <div className="flex flex-wrap gap-2 pt-1">
                  {lookup.data.is_voip && (
                    <Badge variant="warning" size="sm">
                      VoIP
                    </Badge>
                  )}
                  {lookup.data.is_disposable && (
                    <Badge variant="danger" size="sm">
                      Disposable
                    </Badge>
                  )}
                  <Badge variant={(riskVariant[lookup.data.risk_level] ?? "neutral") as "success" | "warning" | "danger" | "info" | "neutral" | "brand"} size="sm">
                    {lookup.data.risk_level.toUpperCase()} RISK
                  </Badge>
                </div>
              </CardBody>
            </Card>

            <Card>
              <CardHeader>
                <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
                  Associated Data
                </h3>
              </CardHeader>
              <CardBody className="space-y-3">
                {lookup.data.social_profiles_found.length > 0 && (
                  <div>
                    <p
                      className="text-xs font-medium mb-1"
                      style={{ color: "var(--text-secondary)" }}
                    >
                      Social Profiles Found
                    </p>
                    <div className="flex flex-wrap gap-1">
                      {lookup.data.social_profiles_found.map((p) => (
                        <Badge key={p} variant="info" size="sm">
                          {p}
                        </Badge>
                      ))}
                    </div>
                  </div>
                )}
                {lookup.data.associated_emails.length > 0 && (
                  <div>
                    <p
                      className="text-xs font-medium mb-1"
                      style={{ color: "var(--text-secondary)" }}
                    >
                      Associated Emails
                    </p>
                    {lookup.data.associated_emails.map((e) => (
                      <div
                        key={e}
                        className="flex items-center gap-1 text-xs font-mono"
                        style={{ color: "var(--text-tertiary)" }}
                      >
                        <Mail className="h-3 w-3" /> {e}
                      </div>
                    ))}
                  </div>
                )}
                {lookup.data.associated_names.length > 0 && (
                  <div>
                    <p
                      className="text-xs font-medium mb-1"
                      style={{ color: "var(--text-secondary)" }}
                    >
                      Associated Names
                    </p>
                    {lookup.data.associated_names.map((n) => (
                      <div
                        key={n}
                        className="flex items-center gap-1 text-xs"
                        style={{ color: "var(--text-tertiary)" }}
                      >
                        <User className="h-3 w-3" /> {n}
                      </div>
                    ))}
                  </div>
                )}
                {lookup.data.social_profiles_found.length === 0 &&
                  lookup.data.associated_emails.length === 0 && (
                    <p
                      className="text-sm text-center py-4"
                      style={{ color: "var(--text-tertiary)" }}
                    >
                      No associated data found
                    </p>
                  )}
              </CardBody>
            </Card>
          </div>
        </div>
      )}

      {!lookup.data && !lookup.isPending && (
        <div
          className="rounded-xl border py-16 text-center"
          style={{ borderColor: "var(--border-subtle)" }}
        >
          <Phone
            className="mx-auto h-10 w-10 mb-3"
            style={{ color: "var(--text-tertiary)" }}
          />
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
            Lookup carrier info, spam scores, and breach data for any phone number
          </p>
        </div>
      )}
    </div>
  );
}
