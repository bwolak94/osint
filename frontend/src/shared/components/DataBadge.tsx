import { useState } from "react";
import { Check, Copy } from "lucide-react";

interface DataBadgeProps {
  value: string;
  type?: "email" | "nip" | "phone" | "ip" | "hash" | "default";
}

export function DataBadge({ value, type: _type = "default" }: DataBadgeProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(value);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <button
      onClick={handleCopy}
      className="group inline-flex items-center gap-1.5 rounded border px-2 py-1 font-mono text-[12px] transition-all hover:border-brand-500/30"
      style={{
        background: "var(--bg-elevated)",
        borderColor: "var(--border-subtle)",
        color: "var(--text-primary)",
      }}
      title="Click to copy"
    >
      <span className="truncate max-w-[200px]">{value}</span>
      {copied ? (
        <Check className="h-3 w-3 shrink-0" style={{ color: "var(--success-500)" }} />
      ) : (
        <Copy
          className="h-3 w-3 shrink-0 opacity-0 transition-opacity group-hover:opacity-100"
          style={{ color: "var(--text-tertiary)" }}
        />
      )}
    </button>
  );
}
