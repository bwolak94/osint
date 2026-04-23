/**
 * NewsBoard — displays news articles returned by the news pipeline.
 *
 * Memoised: re-renders only when `result` changes (result is stable after
 * the pipeline completes). Uses useTranslation("news") for i18n.
 */

import { memo, useId, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { ExternalLink, Shield, Tag } from "lucide-react";
import type { SynergyChain } from "../types";
import { SynergySuggestionCard } from "./SynergySuggestionCard";
import { approveSynergyChain, dismissSynergySignal } from "../api";

export interface NewsArticle {
  id?: string;
  url?: string;
  title: string;
  summary?: string;
  source_domain?: string;
  published_at?: string;
  image_url?: string;
  credibility_score?: number;
  relevance_score?: number;
  tags?: string[];
  action_relevance_score?: number;
}

interface NewsBoardProps {
  articles: NewsArticle[];
  synergyChains?: SynergyChain[];
  taskId?: string;
}

function CredibilityBar({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  const color =
    score >= 0.8 ? "var(--success-500)" :
    score >= 0.6 ? "var(--warning-500)" :
    "var(--danger-500)";
  return (
    <div className="flex items-center gap-2">
      <div
        className="h-1.5 w-16 rounded-full overflow-hidden"
        style={{ background: "var(--bg-overlay)" }}
      >
        <div
          className="h-full rounded-full transition-all"
          style={{ width: `${pct}%`, background: color }}
        />
      </div>
      <span className="text-xs" style={{ color: "var(--text-tertiary)" }}>
        {pct}%
      </span>
    </div>
  );
}

export const NewsBoard = memo(function NewsBoard({
  articles,
  synergyChains = [],
  taskId = "",
}: NewsBoardProps) {
  const { t } = useTranslation("news");
  const labelId = useId();
  const synergyLabelId = useId();

  const handleApprove = useCallback(
    async (_chainId: string) => {
      if (taskId) await approveSynergyChain(taskId);
    },
    [taskId],
  );

  const handleDismiss = useCallback(
    async (_chainId: string, eventId: string) => {
      await dismissSynergySignal(eventId, "me");
    },
    [],
  );

  const pendingChains = synergyChains.filter((c) => c.status === "pending");

  if (articles.length === 0 && pendingChains.length === 0) {
    return (
      <p className="text-sm italic" style={{ color: "var(--text-tertiary)" }}>
        {t("no_articles")}
      </p>
    );
  }

  return (
    <div className="space-y-6">
      {/* Phase 3: Synergy Suggestions */}
      {pendingChains.length > 0 && (
        <section aria-labelledby={synergyLabelId}>
          <h3
            id={synergyLabelId}
            className="mb-3 text-sm font-semibold uppercase tracking-wide"
            style={{ color: "var(--warning-500)" }}
          >
            AI Suggestions · {pendingChains.length}
          </h3>
          <ol className="space-y-3">
            {pendingChains.map((chain) => (
              <li key={chain.chain_id}>
                <SynergySuggestionCard
                  chain={chain}
                  taskId={taskId}
                  onApprove={handleApprove}
                  onDismiss={handleDismiss}
                />
              </li>
            ))}
          </ol>
        </section>
      )}

      {/* Articles list */}
      {articles.length === 0 ? null : (
    <section aria-labelledby={labelId}>
      <h3
        id={labelId}
        className="mb-3 text-sm font-semibold uppercase tracking-wide"
        style={{ color: "var(--text-tertiary)" }}
      >
        {t("title")} · {articles.length}
      </h3>
      <ol className="space-y-3">
        {articles.map((article, idx) => (
          <li
            key={article.id ?? idx}
            className="rounded-xl border p-4 shadow-sm"
            style={{
              background: "var(--bg-surface)",
              borderColor:
                (article.action_relevance_score ?? 0) > 0.75
                  ? "var(--warning-500)"
                  : "var(--border-default)",
            }}
          >
            <div className="flex items-start justify-between gap-2">
              {article.image_url && (
                <img
                  src={article.image_url}
                  alt=""
                  aria-hidden="true"
                  className="h-14 w-14 shrink-0 rounded-lg object-cover"
                  loading="lazy"
                  onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
                />
              )}
              <div className="flex-1 min-w-0">
                <p
                  className="font-medium leading-snug"
                  style={{ color: "var(--text-primary)" }}
                >
                  {article.title}
                </p>
                {article.source_domain && (
                  <p className="mt-0.5 text-xs" style={{ color: "var(--text-tertiary)" }}>
                    {article.source_domain}
                    {article.published_at && ` · ${article.published_at}`}
                  </p>
                )}
              </div>
              {article.url && (
                <a
                  href={article.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  aria-label={t("read_more")}
                  className="shrink-0 rounded p-1 transition-colors hover:bg-bg-overlay"
                >
                  <ExternalLink
                    className="h-4 w-4"
                    style={{ color: "var(--text-tertiary)" }}
                    aria-hidden="true"
                  />
                </a>
              )}
            </div>

            {article.summary && (
              <p
                className="mt-2 text-sm leading-relaxed"
                style={{ color: "var(--text-secondary)" }}
              >
                {article.summary}
              </p>
            )}

            <div className="mt-3 flex flex-wrap items-center gap-3">
              {article.credibility_score !== undefined && (
                <div className="flex items-center gap-1.5">
                  <Shield
                    className="h-3.5 w-3.5"
                    style={{ color: "var(--text-tertiary)" }}
                    aria-hidden="true"
                  />
                  <span className="text-xs" style={{ color: "var(--text-tertiary)" }}>
                    {t("credibility")}
                  </span>
                  <CredibilityBar score={article.credibility_score} />
                </div>
              )}
              {article.tags && article.tags.length > 0 && (
                <div className="flex items-center gap-1 flex-wrap">
                  <Tag
                    className="h-3.5 w-3.5"
                    style={{ color: "var(--text-tertiary)" }}
                    aria-hidden="true"
                  />
                  {article.tags.map((tag) => (
                    <span
                      key={tag}
                      className="rounded px-1.5 py-0.5 text-xs"
                      style={{
                        background: "var(--bg-overlay)",
                        color: "var(--text-secondary)",
                      }}
                    >
                      {tag}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </li>
        ))}
      </ol>
    </section>
      )}
    </div>
  );
});
