import { motion, AnimatePresence } from "framer-motion";
import { X, Expand, Scan, MessageSquare, Play } from "lucide-react";
import { Button } from "@/shared/components/Button";
import { Badge } from "@/shared/components/Badge";
import { DataBadge } from "@/shared/components/DataBadge";
import { ConfidenceIndicator } from "@/shared/components/osint/ConfidenceIndicator";
import { NodeTypeIcon } from "@/shared/components/osint/NodeTypeIcon";
import type { OsintNodeData } from "../types";

interface NodeDetailPanelProps {
  node: OsintNodeData | null;
  connectedNodes: { id: string; type: string; label: string; relation: string }[];
  onClose: () => void;
  onExpandNode: (nodeId: string) => void;
  onRunTransform?: (nodeId: string, transformName: string) => void;
}

/** Available transforms based on node type */
function getAvailableTransforms(type: string): { name: string; label: string; description: string }[] {
  const common = [
    { name: "expand_all", label: "Expand All", description: "Discover all connected entities" },
  ];

  const typeSpecific: Record<string, { name: string; label: string; description: string }[]> = {
    person: [
      { name: "find_emails", label: "Find Email Addresses", description: "Search for associated email addresses" },
      { name: "find_social", label: "Find Social Profiles", description: "Discover social media accounts" },
      { name: "find_phones", label: "Find Phone Numbers", description: "Search for phone numbers" },
      { name: "find_companies", label: "Find Companies", description: "Discover company affiliations" },
    ],
    email: [
      { name: "check_breaches", label: "Check Breaches", description: "Search in known data breaches" },
      { name: "resolve_domain", label: "Resolve Domain", description: "Extract and resolve email domain" },
      { name: "find_owner", label: "Find Owner", description: "Identify the email owner" },
    ],
    domain: [
      { name: "find_subdomains", label: "Find Subdomains", description: "Enumerate subdomains" },
      { name: "dns_lookup", label: "DNS Lookup", description: "Resolve DNS records" },
      { name: "whois_lookup", label: "WHOIS Lookup", description: "Get registration information" },
      { name: "find_certificates", label: "Find Certificates", description: "Discover SSL certificates" },
    ],
    ip: [
      { name: "port_scan", label: "Port Scan", description: "Scan for open ports" },
      { name: "reverse_dns", label: "Reverse DNS", description: "Resolve IP to hostname" },
      { name: "geolocate", label: "Geolocate", description: "Find geographic location" },
      { name: "find_asn", label: "Find ASN", description: "Identify the ASN" },
    ],
    phone: [
      { name: "lookup_carrier", label: "Lookup Carrier", description: "Identify phone carrier" },
      { name: "find_owner", label: "Find Owner", description: "Search for phone owner" },
    ],
    username: [
      { name: "find_profiles", label: "Find Profiles", description: "Search across platforms" },
      { name: "find_emails", label: "Find Emails", description: "Discover associated emails" },
    ],
    company: [
      { name: "find_employees", label: "Find Employees", description: "Discover known employees" },
      { name: "find_domains", label: "Find Domains", description: "Discover company domains" },
      { name: "find_registration", label: "Registration Info", description: "Look up NIP/REGON/KRS" },
    ],
  };

  return [...common, ...(typeSpecific[type] ?? [])];
}

export function NodeDetailPanel({ node, connectedNodes, onClose, onExpandNode, onRunTransform }: NodeDetailPanelProps) {
  const transforms = node ? getAvailableTransforms(node.type) : [];

  return (
    <AnimatePresence>
      {node && (
        <motion.div
          initial={{ x: "100%" }}
          animate={{ x: 0 }}
          exit={{ x: "100%" }}
          transition={{ type: "spring", damping: 25, stiffness: 300 }}
          className="absolute right-0 top-0 bottom-0 z-10 flex w-[380px] flex-col border-l overflow-hidden"
          style={{ background: "var(--bg-surface)", borderColor: "var(--border-subtle)" }}
        >
          {/* Header */}
          <div className="flex items-center justify-between border-b px-4 py-3" style={{ borderColor: "var(--border-subtle)" }}>
            <div className="flex items-center gap-2">
              <NodeTypeIcon type={node.type} size="md" />
              <div>
                <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
                  {node.label}
                </h3>
                <p className="text-xs capitalize" style={{ color: "var(--text-tertiary)" }}>
                  {node.type.replace(/_/g, " ")}
                </p>
              </div>
            </div>
            <button onClick={onClose} className="rounded-md p-1 transition-colors hover:bg-bg-overlay">
              <X className="h-4 w-4" style={{ color: "var(--text-secondary)" }} />
            </button>
          </div>

          {/* Content */}
          <div className="flex-1 overflow-y-auto px-4 py-4 space-y-5">
            {/* Confidence */}
            <div>
              <p className="mb-1 text-xs font-medium uppercase tracking-wide" style={{ color: "var(--text-tertiary)" }}>
                Confidence
              </p>
              <ConfidenceIndicator value={node.confidence} />
            </div>

            {/* Weight / Child Count stats */}
            {(node.weight != null && node.weight > 0 || node.childCount != null && node.childCount > 0) && (
              <div className="flex gap-4">
                {node.weight != null && node.weight > 0 && (
                  <div>
                    <p className="text-xs font-medium uppercase tracking-wide" style={{ color: "var(--text-tertiary)" }}>
                      Connections
                    </p>
                    <p className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
                      {node.weight}
                    </p>
                  </div>
                )}
                {node.childCount != null && node.childCount > 0 && (
                  <div>
                    <p className="text-xs font-medium uppercase tracking-wide" style={{ color: "var(--text-tertiary)" }}>
                      Children
                    </p>
                    <p className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
                      {node.childCount}
                    </p>
                  </div>
                )}
              </div>
            )}

            {/* Properties */}
            {Object.keys(node.properties).length > 0 && (
              <div>
                <p className="mb-2 text-xs font-medium uppercase tracking-wide" style={{ color: "var(--text-tertiary)" }}>
                  Properties
                </p>
                <div className="space-y-1.5">
                  {Object.entries(node.properties).map(([key, value]) => (
                    <div key={key} className="flex items-start justify-between gap-2">
                      <span className="text-xs" style={{ color: "var(--text-secondary)" }}>{key}</span>
                      <DataBadge value={String(value)} />
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Sources */}
            <div>
              <p className="mb-2 text-xs font-medium uppercase tracking-wide" style={{ color: "var(--text-tertiary)" }}>
                Sources
              </p>
              <div className="flex flex-wrap gap-1">
                {node.sources.map((s) => (
                  <Badge key={s} variant="neutral" size="sm">{s}</Badge>
                ))}
              </div>
            </div>

            {/* Available Transforms */}
            {transforms.length > 0 && (
              <div>
                <p className="mb-2 text-xs font-medium uppercase tracking-wide" style={{ color: "var(--text-tertiary)" }}>
                  Transforms
                </p>
                <div className="space-y-1">
                  {transforms.map((t) => (
                    <button
                      key={t.name}
                      onClick={() => onRunTransform?.(node.id, t.name)}
                      className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-xs transition-colors hover:bg-bg-overlay"
                    >
                      <Play className="h-3 w-3 shrink-0" style={{ color: "var(--brand-500)" }} />
                      <div className="flex-1 min-w-0">
                        <span className="block truncate font-medium" style={{ color: "var(--text-primary)" }}>
                          {t.label}
                        </span>
                        <span className="block truncate" style={{ color: "var(--text-tertiary)" }}>
                          {t.description}
                        </span>
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Connected nodes */}
            {connectedNodes.length > 0 && (
              <div>
                <p className="mb-2 text-xs font-medium uppercase tracking-wide" style={{ color: "var(--text-tertiary)" }}>
                  Connected ({connectedNodes.length})
                </p>
                <div className="space-y-1">
                  {connectedNodes.map((cn) => (
                    <button
                      key={cn.id}
                      onClick={() => onExpandNode(cn.id)}
                      className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-xs transition-colors hover:bg-bg-overlay"
                    >
                      <NodeTypeIcon type={cn.type} size="sm" />
                      <span className="flex-1 truncate" style={{ color: "var(--text-primary)" }}>{cn.label}</span>
                      <span className="text-[10px] uppercase" style={{ color: "var(--text-tertiary)" }}>{cn.relation}</span>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Actions */}
          <div className="border-t px-4 py-3 space-y-2" style={{ borderColor: "var(--border-subtle)" }}>
            <Button variant="secondary" size="sm" className="w-full" leftIcon={<Expand className="h-3.5 w-3.5" />} onClick={() => onExpandNode(node.id)}>
              Expand Connections
            </Button>
            <div className="flex gap-2">
              <Button variant="ghost" size="sm" className="flex-1" leftIcon={<Scan className="h-3.5 w-3.5" />}>
                Re-scan
              </Button>
              <Button variant="ghost" size="sm" className="flex-1" leftIcon={<MessageSquare className="h-3.5 w-3.5" />}>
                Annotate
              </Button>
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
