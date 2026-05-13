import { ExternalLink, MapPin, Briefcase, GraduationCap, Users } from "lucide-react";
import type { LinkedInIntelScan } from "../types";

interface Props {
  scan: LinkedInIntelScan;
}

export function LinkedInResults({ scan }: Props) {
  if (!scan.results.length) {
    return (
      <div
        className="rounded-lg border p-8 text-center text-sm"
        style={{ borderColor: "var(--border-subtle)", color: "var(--text-tertiary)" }}
      >
        No LinkedIn profiles found for "{scan.query}".
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <p className="text-sm" style={{ color: "var(--text-tertiary)" }}>
        Found {scan.total_results} profile{scan.total_results !== 1 ? "s" : ""}
      </p>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {scan.results.map((profile, idx) => (
          <div
            key={idx}
            className="flex flex-col gap-3 rounded-lg border p-4 transition-colors hover:border-brand-500/50"
            style={{ background: "var(--bg-surface)", borderColor: "var(--border-subtle)" }}
          >
            {/* Avatar + name */}
            <div className="flex items-start gap-3">
              {profile.profile_pic_url ? (
                <img
                  src={profile.profile_pic_url}
                  alt={profile.full_name ?? ""}
                  className="h-12 w-12 rounded-full object-cover shrink-0"
                />
              ) : (
                <div
                  className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full text-lg font-bold"
                  style={{ background: "var(--bg-overlay)", color: "var(--text-secondary)" }}
                >
                  {profile.full_name?.[0] ?? "?"}
                </div>
              )}
              <div className="min-w-0">
                <p className="truncate font-semibold text-sm" style={{ color: "var(--text-primary)" }}>
                  {profile.full_name ?? profile.username ?? "Unknown"}
                </p>
                {profile.headline && (
                  <p className="text-xs line-clamp-2" style={{ color: "var(--text-secondary)" }}>
                    {profile.headline}
                  </p>
                )}
              </div>
            </div>

            {/* Details */}
            <div className="space-y-1.5 text-xs" style={{ color: "var(--text-tertiary)" }}>
              {profile.location && (
                <div className="flex items-center gap-1.5">
                  <MapPin className="h-3.5 w-3.5 shrink-0" />
                  <span className="truncate">{profile.location}</span>
                </div>
              )}
              {profile.company && (
                <div className="flex items-center gap-1.5">
                  <Briefcase className="h-3.5 w-3.5 shrink-0" />
                  <span className="truncate">{profile.company}</span>
                </div>
              )}
              {profile.school && (
                <div className="flex items-center gap-1.5">
                  <GraduationCap className="h-3.5 w-3.5 shrink-0" />
                  <span className="truncate">{profile.school}</span>
                </div>
              )}
              {profile.connections && (
                <div className="flex items-center gap-1.5">
                  <Users className="h-3.5 w-3.5 shrink-0" />
                  <span>{profile.connections} connections</span>
                </div>
              )}
            </div>

            {profile.profile_url && (
              <a
                href={profile.profile_url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1 text-xs text-brand-400 hover:underline mt-auto"
              >
                <ExternalLink className="h-3 w-3" />
                View Profile
              </a>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
