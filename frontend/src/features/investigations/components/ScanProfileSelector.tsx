import { useState, useCallback, useId } from "react";
import { useQuery } from "@tanstack/react-query";
import { ChevronDown, Plus, AlertCircle, Check } from "lucide-react";
import { Badge } from "@/shared/components/Badge";
import { LoadingSpinner } from "@/shared/components/LoadingSpinner";
import apiClient from "@/shared/api/client";

export interface ScanProfile {
  id: string;
  name: string;
  description: string;
  enabled_scanners: string[];
  proxy_mode: string;
  is_default: boolean;
}

interface ScanProfileSelectorProps {
  value: string | null;
  onChange: (profileId: string | null) => void;
}

async function fetchScanProfiles(): Promise<ScanProfile[]> {
  const { data } = await apiClient.get<ScanProfile[]>("/scan-profiles");
  return data;
}

const NO_PROFILE_VALUE = "__none__";

export function ScanProfileSelector({
  value,
  onChange,
}: ScanProfileSelectorProps) {
  const [open, setOpen] = useState(false);
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const labelId = useId();
  const listId = useId();

  const { data: profiles = [], isLoading, error } = useQuery({
    queryKey: ["scan-profiles"],
    queryFn: fetchScanProfiles,
    staleTime: 60_000,
  });

  const selectedProfile = profiles.find((p) => p.id === value) ?? null;

  const handleSelect = useCallback(
    (profileId: string | null) => {
      onChange(profileId);
      setOpen(false);
    },
    [onChange],
  );

  const buttonLabel = selectedProfile
    ? selectedProfile.name
    : "No profile (run all scanners)";

  return (
    <div className="relative">
      {/* Trigger */}
      <button
        id={labelId}
        type="button"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={listId}
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between rounded-md border px-3 py-2 text-sm transition-colors hover:bg-bg-elevated focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
        style={{
          background: "var(--bg-elevated)",
          borderColor: "var(--border-default)",
          color: "var(--text-primary)",
        }}
      >
        <div className="flex min-w-0 items-center gap-2">
          {isLoading ? (
            <LoadingSpinner size="sm" />
          ) : (
            <>
              <span className="truncate">{buttonLabel}</span>
              {selectedProfile?.is_default && (
                <Badge variant="brand" size="sm">
                  Default
                </Badge>
              )}
              {selectedProfile && (
                <Badge variant="neutral" size="sm">
                  {selectedProfile.enabled_scanners.length} scanners
                </Badge>
              )}
            </>
          )}
        </div>
        <ChevronDown
          className={`ml-2 h-4 w-4 shrink-0 transition-transform ${open ? "rotate-180" : ""}`}
          style={{ color: "var(--text-tertiary)" }}
        />
      </button>

      {/* Dropdown */}
      {open && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 z-40"
            onClick={() => setOpen(false)}
            aria-hidden="true"
          />

          <div
            id={listId}
            role="listbox"
            aria-labelledby={labelId}
            className="absolute left-0 top-full z-50 mt-1 w-full overflow-hidden rounded-lg border shadow-xl"
            style={{
              background: "var(--bg-surface)",
              borderColor: "var(--border-default)",
              minWidth: 280,
            }}
          >
            {error ? (
              <div
                className="flex items-center gap-2 px-4 py-3"
                style={{ color: "var(--danger-500, #ef4444)" }}
              >
                <AlertCircle className="h-4 w-4 shrink-0" />
                <p className="text-sm">Failed to load scan profiles</p>
              </div>
            ) : (
              <>
                {/* No profile option */}
                <button
                  role="option"
                  aria-selected={value === null}
                  onClick={() => handleSelect(null)}
                  className="flex w-full items-center gap-3 px-4 py-2.5 text-left text-sm transition-colors hover:bg-bg-overlay"
                  style={{ color: "var(--text-primary)" }}
                >
                  <span
                    className="flex h-4 w-4 shrink-0 items-center justify-center rounded-full border"
                    style={{ borderColor: "var(--border-default)" }}
                  >
                    {value === null && (
                      <Check className="h-2.5 w-2.5" style={{ color: "var(--brand-500)" }} />
                    )}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="font-medium">No profile</p>
                    <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>
                      Run all available scanners
                    </p>
                  </div>
                </button>

                {profiles.length > 0 && (
                  <div
                    className="my-1 h-px"
                    style={{ background: "var(--border-subtle)" }}
                  />
                )}

                {/* Profile options */}
                {profiles.map((profile) => (
                  <div
                    key={profile.id}
                    className="relative"
                    onMouseEnter={() => setHoveredId(profile.id)}
                    onMouseLeave={() => setHoveredId(null)}
                  >
                    <button
                      role="option"
                      aria-selected={value === profile.id}
                      onClick={() => handleSelect(profile.id)}
                      className="flex w-full items-center gap-3 px-4 py-2.5 text-left text-sm transition-colors hover:bg-bg-overlay"
                      style={{ color: "var(--text-primary)" }}
                    >
                      <span
                        className="flex h-4 w-4 shrink-0 items-center justify-center rounded-full border"
                        style={{ borderColor: "var(--border-default)" }}
                      >
                        {value === profile.id && (
                          <Check
                            className="h-2.5 w-2.5"
                            style={{ color: "var(--brand-500)" }}
                          />
                        )}
                      </span>

                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          <p className="truncate font-medium">{profile.name}</p>
                          {profile.is_default && (
                            <Badge variant="brand" size="sm">
                              Default
                            </Badge>
                          )}
                          <Badge variant="neutral" size="sm">
                            {profile.enabled_scanners.length}
                          </Badge>
                        </div>
                        {profile.description && (
                          <p
                            className="truncate text-xs"
                            style={{ color: "var(--text-tertiary)" }}
                          >
                            {profile.description}
                          </p>
                        )}
                      </div>
                    </button>

                    {/* Scanner tooltip on hover */}
                    {hoveredId === profile.id &&
                      profile.enabled_scanners.length > 0 && (
                        <div
                          className="absolute left-full top-0 z-50 ml-2 w-48 rounded-lg border px-3 py-2 shadow-lg"
                          style={{
                            background: "var(--bg-surface)",
                            borderColor: "var(--border-default)",
                          }}
                          role="tooltip"
                          aria-label={`Enabled scanners for ${profile.name}`}
                        >
                          <p
                            className="mb-1.5 text-[10px] font-semibold uppercase tracking-wider"
                            style={{ color: "var(--text-tertiary)" }}
                          >
                            Enabled Scanners
                          </p>
                          <ul className="space-y-0.5">
                            {profile.enabled_scanners.map((scanner) => (
                              <li
                                key={scanner}
                                className="text-xs"
                                style={{ color: "var(--text-secondary)" }}
                              >
                                • {scanner}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                  </div>
                ))}

                {/* Create new profile */}
                <div
                  className="border-t"
                  style={{ borderColor: "var(--border-subtle)" }}
                >
                  <a
                    href="/settings/scan-profiles/new"
                    className="flex items-center gap-2 px-4 py-2.5 text-sm transition-colors hover:bg-bg-overlay"
                    style={{ color: "var(--brand-500)" }}
                    onClick={() => setOpen(false)}
                  >
                    <Plus className="h-3.5 w-3.5" />
                    Create new profile
                  </a>
                </div>
              </>
            )}
          </div>
        </>
      )}
    </div>
  );
}
