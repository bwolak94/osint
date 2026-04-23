/**
 * MarkdownContent — lightweight inline markdown renderer.
 *
 * Handles the subset of Markdown that agent results commonly produce:
 *   - # / ## / ### headings
 *   - **bold**, *italic*, `inline code`
 *   - Bullet lists (- item / * item)
 *   - Numbered lists (1. item)
 *   - Blank-line-separated paragraphs
 *
 * No external dependencies — avoids a Docker rebuild for react-markdown.
 */

import { memo, type ReactNode } from "react";

interface MarkdownContentProps {
  content: string;
  className?: string;
}

// Apply inline formatting: bold, italic, inline-code, links
function applyInline(text: string): ReactNode[] {
  const parts: React.ReactNode[] = [];
  // Pattern priority: **bold**, *italic*, `code`, [link](url)
  const re = /(\*\*(.+?)\*\*|\*(.+?)\*|`([^`]+)`|\[([^\]]+)\]\(([^)]+)\))/g;
  let last = 0;
  let match: RegExpExecArray | null;

  while ((match = re.exec(text)) !== null) {
    if (match.index > last) {
      parts.push(text.slice(last, match.index));
    }
    if (match[2]) {
      parts.push(<strong key={match.index}>{match[2]}</strong>);
    } else if (match[3]) {
      parts.push(<em key={match.index}>{match[3]}</em>);
    } else if (match[4]) {
      parts.push(
        <code
          key={match.index}
          className="rounded px-1 py-0.5 text-xs font-mono"
          style={{ background: "var(--bg-elevated)", color: "var(--text-primary)" }}
        >
          {match[4]}
        </code>,
      );
    } else if (match[5] && match[6]) {
      parts.push(
        <a
          key={match.index}
          href={match[6]}
          target="_blank"
          rel="noopener noreferrer"
          className="underline hover:opacity-80"
          style={{ color: "var(--brand-500)" }}
        >
          {match[5]}
        </a>,
      );
    }
    last = match.index + match[0].length;
  }

  if (last < text.length) {
    parts.push(text.slice(last));
  }

  return parts;
}

// Parse a block of text lines into React elements
function parseBlock(lines: string[], keyPrefix: string): ReactNode[] {
  const nodes: ReactNode[] = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];

    // Headings
    const h3 = line.match(/^###\s+(.+)/);
    const h2 = line.match(/^##\s+(.+)/);
    const h1 = line.match(/^#\s+(.+)/);
    if (h1) {
      nodes.push(
        <h2 key={`${keyPrefix}-h1-${i}`} className="text-base font-bold mt-3 mb-1" style={{ color: "var(--text-primary)" }}>
          {applyInline(h1[1])}
        </h2>,
      );
      i++;
      continue;
    }
    if (h2) {
      nodes.push(
        <h3 key={`${keyPrefix}-h2-${i}`} className="text-sm font-semibold mt-2 mb-1" style={{ color: "var(--text-primary)" }}>
          {applyInline(h2[1])}
        </h3>,
      );
      i++;
      continue;
    }
    if (h3) {
      nodes.push(
        <h4 key={`${keyPrefix}-h3-${i}`} className="text-xs font-semibold mt-2 mb-0.5 uppercase tracking-wide" style={{ color: "var(--text-secondary)" }}>
          {applyInline(h3[1])}
        </h4>,
      );
      i++;
      continue;
    }

    // Bullet lists
    if (/^[-*]\s+/.test(line)) {
      const items: string[] = [];
      while (i < lines.length && /^[-*]\s+/.test(lines[i])) {
        items.push(lines[i].replace(/^[-*]\s+/, ""));
        i++;
      }
      nodes.push(
        <ul key={`${keyPrefix}-ul-${i}`} className="list-disc list-inside space-y-0.5 my-1 pl-2">
          {items.map((item, idx) => (
            <li key={idx} className="text-sm" style={{ color: "var(--text-secondary)" }}>
              {applyInline(item)}
            </li>
          ))}
        </ul>,
      );
      continue;
    }

    // Numbered lists
    if (/^\d+\.\s+/.test(line)) {
      const items: string[] = [];
      while (i < lines.length && /^\d+\.\s+/.test(lines[i])) {
        items.push(lines[i].replace(/^\d+\.\s+/, ""));
        i++;
      }
      nodes.push(
        <ol key={`${keyPrefix}-ol-${i}`} className="list-decimal list-inside space-y-0.5 my-1 pl-2">
          {items.map((item, idx) => (
            <li key={idx} className="text-sm" style={{ color: "var(--text-secondary)" }}>
              {applyInline(item)}
            </li>
          ))}
        </ol>,
      );
      continue;
    }

    // Horizontal rule
    if (/^---+$/.test(line.trim())) {
      nodes.push(<hr key={`${keyPrefix}-hr-${i}`} className="my-2 border-t" style={{ borderColor: "var(--border-subtle)" }} />);
      i++;
      continue;
    }

    // Empty line — skip (paragraph breaks are implicit between blocks)
    if (line.trim() === "") {
      i++;
      continue;
    }

    // Regular paragraph
    nodes.push(
      <p key={`${keyPrefix}-p-${i}`} className="text-sm leading-relaxed" style={{ color: "var(--text-secondary)" }}>
        {applyInline(line)}
      </p>,
    );
    i++;
  }

  return nodes;
}

export const MarkdownContent = memo(function MarkdownContent({
  content,
  className = "",
}: MarkdownContentProps) {
  const lines = content.split("\n");
  const nodes = parseBlock(lines, "md");

  return (
    <div className={`space-y-1 ${className}`}>
      {nodes}
    </div>
  );
});
