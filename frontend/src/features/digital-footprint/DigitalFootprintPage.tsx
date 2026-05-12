import { useState } from "react";
import { Fingerprint, Search, AlertCircle, CheckCircle, XCircle } from "lucide-react";
import { useFootprintScore } from "./hooks";
import type { FootprintCategory } from "./types";
import { Badge } from "@/shared/components/Badge";
import { Button } from "@/shared/components/Button";
import { Input } from "@/shared/components/Input";
import { Card, CardBody, CardHeader } from "@/shared/components/Card";

const riskVariant: Record<string, "danger" | "warning" | "info" | "neutral"> =
  {
    critical: "danger",
    high: "danger",
    medium: "warning",
    low: "neutral",
  };

function scoreColor(score: number): string {
  if (score > 80) return "var(--danger-400)";
  if (score > 60) return "var(--warning-400)";
  if (score > 40) return "var(--brand-400)";
  return "var(--success-400)";
}

function CategoryBar({ cat }: { cat: FootprintCategory }) {
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between">
        <span
          className="text-sm font-medium"
          style={{ color: "var(--text-primary)" }}
        >
          {cat.name}
        </span>
        <div className="flex items-center gap-2">
          <Badge variant={(riskVariant[cat.risk] ?? "neutral") as "success" | "warning" | "danger" | "info" | "neutral" | "brand"} size="sm">
            {cat.risk}
          </Badge>
          <span
            className="text-sm font-mono"
            style={{ color: scoreColor(cat.score) }}
          >
            {cat.score}
          </span>
        </div>
      </div>
      <div
        className="h-2 rounded-full overflow-hidden"
        style={{ background: "var(--bg-elevated)" }}
      >
        <div
          className="h-full rounded-full transition-all duration-700"
          style={{ width: `${cat.score}%`, background: scoreColor(cat.score) }}
        />
      </div>
      <ul className="mt-1 space-y-0.5">
        {cat.findings.map((f, i) => (
          <li
            key={i}
            className="flex items-center gap-1.5 text-xs"
            style={{ color: "var(--text-tertiary)" }}
          >
            <AlertCircle
              className="h-3 w-3 shrink-0"
              style={{ color: "var(--warning-400)" }}
            />
            {f}
          </li>
        ))}
      </ul>
    </div>
  );
}

export function DigitalFootprintPage() {
  const [target, setTarget] = useState("");
  const score = useFootprintScore();

  const handleAnalyze = () => {
    if (target.trim()) score.mutate(target.trim());
  };

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3">
        <Fingerprint
          className="h-6 w-6"
          style={{ color: "var(--brand-500)" }}
        />
        <h1
          className="text-xl font-semibold"
          style={{ color: "var(--text-primary)" }}
        >
          Digital Footprint Score
        </h1>
      </div>

      <Card>
        <CardBody>
          <div className="flex gap-3">
            <div className="flex-1">
              <Input
                placeholder="Email, name, domain, username..."
                prefixIcon={<Search className="h-4 w-4" />}
                value={target}
                onChange={(e) => setTarget(e.target.value)}
                onKeyDown={(e) =>
                  e.key === "Enter" && target.trim() && handleAnalyze()
                }
              />
            </div>
            <Button
              onClick={handleAnalyze}
              disabled={!target.trim() || score.isPending}
              leftIcon={<Fingerprint className="h-4 w-4" />}
            >
              {score.isPending ? "Analyzing..." : "Analyze"}
            </Button>
          </div>
        </CardBody>
      </Card>

      {score.data && (
        <div className="space-y-4">
          <div
            className="rounded-2xl border p-6 text-center"
            style={{
              background: "var(--bg-surface)",
              borderColor: "var(--border-default)",
            }}
          >
            <div
              className="text-6xl font-bold mb-2"
              style={{ color: scoreColor(score.data.overall_score) }}
            >
              {score.data.overall_score}
            </div>
            <p
              className="text-sm font-medium mb-1"
              style={{ color: "var(--text-secondary)" }}
            >
              Exposure Score for{" "}
              <strong style={{ color: "var(--text-primary)" }}>
                {score.data.target}
              </strong>
            </p>
            <Badge variant={(riskVariant[score.data.risk_level] ?? "neutral") as "success" | "warning" | "danger" | "info" | "neutral" | "brand"}>
              {score.data.risk_level.toUpperCase()} EXPOSURE
            </Badge>
            <p
              className="mt-2 text-xs"
              style={{ color: "var(--text-tertiary)" }}
            >
              Found on {score.data.data_broker_count} data broker sites
            </p>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <Card>
              <CardHeader>
                <h3
                  className="text-sm font-semibold"
                  style={{ color: "var(--text-primary)" }}
                >
                  Category Breakdown
                </h3>
              </CardHeader>
              <CardBody className="space-y-4">
                {score.data.categories.map((c) => (
                  <CategoryBar key={c.name} cat={c} />
                ))}
              </CardBody>
            </Card>

            <div className="space-y-4">
              <Card>
                <CardHeader>
                  <h3
                    className="text-sm font-semibold"
                    style={{ color: "var(--text-primary)" }}
                  >
                    Social Profiles
                  </h3>
                </CardHeader>
                <CardBody className="space-y-2">
                  {score.data.social_profiles.map((p) => (
                    <div
                      key={p.platform}
                      className="flex items-center justify-between"
                    >
                      <span
                        className="text-sm"
                        style={{ color: "var(--text-primary)" }}
                      >
                        {p.platform}
                      </span>
                      {p.url_found ? (
                        <CheckCircle
                          className="h-4 w-4"
                          style={{ color: "var(--warning-400)" }}
                        />
                      ) : (
                        <XCircle
                          className="h-4 w-4"
                          style={{ color: "var(--success-400)" }}
                        />
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
                    Recommendations
                  </h3>
                </CardHeader>
                <CardBody>
                  <ul className="space-y-2">
                    {score.data.recommendations.map((r, i) => (
                      <li
                        key={i}
                        className="flex items-start gap-2 text-sm"
                        style={{ color: "var(--text-secondary)" }}
                      >
                        <span
                          className="shrink-0 font-bold"
                          style={{ color: "var(--brand-400)" }}
                        >
                          {i + 1}.
                        </span>
                        {r}
                      </li>
                    ))}
                  </ul>
                </CardBody>
              </Card>
            </div>
          </div>
        </div>
      )}

      {!score.data && !score.isPending && (
        <div
          className="rounded-xl border py-16 text-center"
          style={{ borderColor: "var(--border-subtle)" }}
        >
          <Fingerprint
            className="mx-auto h-10 w-10 mb-3"
            style={{ color: "var(--text-tertiary)" }}
          />
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
            Analyze any target's digital exposure footprint
          </p>
        </div>
      )}
    </div>
  );
}
