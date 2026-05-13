import { ExternalLink, Star, GitFork, MapPin, Building2, Mail, Twitter } from "lucide-react";
import type { GitHubIntelScan, GhRepo } from "../types";

interface Props {
  scan: GitHubIntelScan;
}

function RepoCard({ repo }: { repo: GhRepo }) {
  return (
    <a
      href={repo.url}
      target="_blank"
      rel="noopener noreferrer"
      className="block rounded-md border p-3 text-xs hover:border-brand-500/50 transition-colors"
      style={{ borderColor: "var(--border-subtle)", background: "var(--bg-overlay)" }}
    >
      <div className="font-medium truncate" style={{ color: "var(--text-primary)" }}>
        {repo.name}
      </div>
      {repo.description && (
        <div className="mt-0.5 line-clamp-2" style={{ color: "var(--text-tertiary)" }}>
          {repo.description}
        </div>
      )}
      <div className="mt-2 flex gap-3" style={{ color: "var(--text-tertiary)" }}>
        {repo.language && <span>{repo.language}</span>}
        <span className="flex items-center gap-1">
          <Star className="h-3 w-3" /> {repo.stars}
        </span>
        <span className="flex items-center gap-1">
          <GitFork className="h-3 w-3" /> {repo.forks}
        </span>
      </div>
    </a>
  );
}

export function GitHubResults({ scan }: Props) {
  if (!scan.results.length) {
    return (
      <div
        className="rounded-lg border p-8 text-center text-sm"
        style={{ borderColor: "var(--border-subtle)", color: "var(--text-tertiary)" }}
      >
        No GitHub profiles found for "{scan.query}".
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <p className="text-sm" style={{ color: "var(--text-tertiary)" }}>
        Found {scan.total_results} profile{scan.total_results !== 1 ? "s" : ""}
      </p>
      {scan.results.map((profile, idx) => (
        <div
          key={idx}
          className="rounded-lg border p-5 space-y-4"
          style={{ background: "var(--bg-surface)", borderColor: "var(--border-subtle)" }}
        >
          {/* Header */}
          <div className="flex items-start gap-4">
            {profile.avatar_url ? (
              <img
                src={profile.avatar_url}
                alt={profile.username ?? ""}
                className="h-16 w-16 rounded-full object-cover shrink-0"
              />
            ) : (
              <div
                className="flex h-16 w-16 shrink-0 items-center justify-center rounded-full text-2xl font-bold"
                style={{ background: "var(--bg-overlay)", color: "var(--text-secondary)" }}
              >
                {profile.username?.[0]?.toUpperCase() ?? "?"}
              </div>
            )}
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="font-semibold" style={{ color: "var(--text-primary)" }}>
                  {profile.full_name ?? profile.username}
                </span>
                {profile.username && (
                  <span className="text-sm" style={{ color: "var(--text-tertiary)" }}>
                    @{profile.username}
                  </span>
                )}
                {profile.account_type !== "User" && (
                  <span className="rounded-full bg-bg-overlay px-2 py-0.5 text-xs" style={{ color: "var(--text-tertiary)" }}>
                    {profile.account_type}
                  </span>
                )}
              </div>
              {profile.bio && (
                <p className="mt-1 text-sm" style={{ color: "var(--text-secondary)" }}>
                  {profile.bio}
                </p>
              )}
              <div className="mt-2 flex flex-wrap gap-3 text-xs" style={{ color: "var(--text-tertiary)" }}>
                {profile.location && (
                  <span className="flex items-center gap-1">
                    <MapPin className="h-3 w-3" /> {profile.location}
                  </span>
                )}
                {profile.company && (
                  <span className="flex items-center gap-1">
                    <Building2 className="h-3 w-3" /> {profile.company}
                  </span>
                )}
                {profile.email && (
                  <span className="flex items-center gap-1">
                    <Mail className="h-3 w-3" /> {profile.email}
                  </span>
                )}
                {profile.twitter_username && (
                  <span className="flex items-center gap-1">
                    <Twitter className="h-3 w-3" /> @{profile.twitter_username}
                  </span>
                )}
              </div>
            </div>
          </div>

          {/* Stats */}
          <div className="flex gap-4 text-sm" style={{ color: "var(--text-secondary)" }}>
            <span><strong style={{ color: "var(--text-primary)" }}>{profile.followers ?? 0}</strong> followers</span>
            <span><strong style={{ color: "var(--text-primary)" }}>{profile.following ?? 0}</strong> following</span>
            <span><strong style={{ color: "var(--text-primary)" }}>{profile.public_repos ?? 0}</strong> repos</span>
          </div>

          {/* Exposed emails */}
          {profile.emails_in_commits.length > 0 && (
            <div>
              <p className="text-xs font-medium mb-1" style={{ color: "var(--text-secondary)" }}>
                Emails found in commits:
              </p>
              <div className="flex flex-wrap gap-2">
                {profile.emails_in_commits.map((email) => (
                  <span
                    key={email}
                    className="rounded-full px-2 py-0.5 text-xs"
                    style={{ background: "var(--warning-500/10)", color: "var(--warning-500)" }}
                  >
                    {email}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Languages */}
          {profile.languages.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {profile.languages.map((lang) => (
                <span
                  key={lang}
                  className="rounded-full px-2 py-0.5 text-xs"
                  style={{ background: "var(--bg-overlay)", color: "var(--text-secondary)" }}
                >
                  {lang}
                </span>
              ))}
            </div>
          )}

          {/* Top repos */}
          {profile.top_repos.length > 0 && (
            <div>
              <p className="text-xs font-medium mb-2" style={{ color: "var(--text-secondary)" }}>
                Top repositories:
              </p>
              <div className="grid gap-2 sm:grid-cols-2">
                {profile.top_repos.slice(0, 4).map((repo) => (
                  <RepoCard key={repo.name} repo={repo} />
                ))}
              </div>
            </div>
          )}

          {profile.profile_url && (
            <a
              href={profile.profile_url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1 text-xs text-brand-400 hover:underline"
            >
              <ExternalLink className="h-3 w-3" />
              View on GitHub
            </a>
          )}
        </div>
      ))}
    </div>
  );
}
