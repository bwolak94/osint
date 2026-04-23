/**
 * NewsFeedPanel — live news feed + RAG chat for the News module.
 *
 * Left panel:  scrollable article cards fetched from /hub/news/articles
 * Right panel: RAG chat box (ask questions about stored articles)
 *
 * Browsing works without an OpenAI key — only the RAG chat requires one.
 */

import { memo, useState, useCallback, useId } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import {
  ExternalLink,
  Loader2,
  Newspaper,
  RefreshCw,
  Search,
  Send,
} from "lucide-react";

import { getNewsFeed, askNewsRag } from "../api";
import type { NewsRagResponse, StoredNewsArticle } from "../types";

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  sources?: NewsRagResponse["sources"];
}

// ── Article card ─────────────────────────────────────────────────────────────

interface ArticleCardProps {
  article: StoredNewsArticle;
}

const ArticleCard = memo(function ArticleCard({ article }: ArticleCardProps) {
  const tags: string[] = Array.isArray(article.tags) ? article.tags : [];

  return (
    <article
      className="rounded-xl border p-3 transition-colors hover:border-opacity-70"
      style={{ background: "var(--bg-surface)", borderColor: "var(--border-subtle)" }}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <a
            href={article.url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm font-medium hover:underline inline-flex items-start gap-1 leading-snug"
            style={{ color: "var(--text-primary)" }}
          >
            <span className="line-clamp-2">{article.title}</span>
            <ExternalLink
              className="h-3 w-3 mt-0.5 shrink-0 opacity-60"
              aria-hidden="true"
            />
          </a>

          {article.summary && (
            <p
              className="mt-1 text-xs line-clamp-2"
              style={{ color: "var(--text-secondary)" }}
            >
              {article.summary}
            </p>
          )}

          <div className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1">
            <span className="text-xs" style={{ color: "var(--text-tertiary)" }}>
              {article.source_domain}
            </span>
            {tags.slice(0, 3).map((t) => (
              <span
                key={t}
                className="text-xs px-1.5 py-0.5 rounded-full"
                style={{ background: "var(--brand-50)", color: "var(--brand-600)" }}
              >
                {t}
              </span>
            ))}
          </div>
        </div>

        {article.credibility_score > 0 && (
          <span
            className="shrink-0 text-xs px-1.5 py-0.5 rounded-full"
            style={{
              background:
                article.credibility_score >= 0.8
                  ? "var(--success-50)"
                  : "var(--warning-50)",
              color:
                article.credibility_score >= 0.8
                  ? "var(--success-600)"
                  : "var(--warning-600)",
            }}
          >
            {Math.round(article.credibility_score * 100)}%
          </span>
        )}
      </div>
    </article>
  );
});

// ── Chat bubble ──────────────────────────────────────────────────────────────

interface ChatBubbleProps {
  message: ChatMessage;
}

function ChatBubble({ message }: ChatBubbleProps) {
  const isUser = message.role === "user";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[90%] rounded-xl px-3 py-2 text-xs ${
          isUser ? "rounded-br-sm" : "rounded-bl-sm"
        }`}
        style={
          isUser
            ? { background: "var(--brand-500)", color: "white" }
            : {
                background: "var(--bg-elevated)",
                color: "var(--text-secondary)",
                border: "1px solid var(--border-subtle)",
              }
        }
      >
        <p className="whitespace-pre-wrap">{message.content}</p>

        {message.sources && message.sources.length > 0 && (
          <div className="mt-2 pt-2 space-y-0.5" style={{ borderTop: "1px solid rgba(255,255,255,0.2)" }}>
            {message.sources.map((s, i) => (
              <a
                key={i}
                href={s.url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1 hover:underline opacity-80 truncate"
              >
                <ExternalLink className="h-2.5 w-2.5 shrink-0" aria-hidden="true" />
                <span className="truncate">
                  [{i + 1}] {s.source_domain}
                </span>
              </a>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Main component ───────────────────────────────────────────────────────────

export const NewsFeedPanel = memo(function NewsFeedPanel() {
  const [chatQuery, setChatQuery] = useState("");
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]);
  const [tagFilter, setTagFilter] = useState("");

  const feedLabelId = useId();
  const chatLabelId = useId();

  const feedQuery = useQuery({
    queryKey: ["news", "feed", tagFilter],
    queryFn: () => getNewsFeed({ limit: 30, tag: tagFilter || undefined }),
    refetchInterval: 5 * 60 * 1000, // refresh every 5 min
    staleTime: 60_000,
  });

  const askMutation = useMutation({
    mutationFn: (q: string) => askNewsRag({ query: q, top_k: 5 }),
    onSuccess: (data, variables) => {
      setChatHistory((prev) => [
        ...prev,
        { role: "user", content: variables },
        { role: "assistant", content: data.answer, sources: data.sources },
      ]);
      setChatQuery("");
    },
    onError: () => {
      setChatHistory((prev) => [
        ...prev,
        {
          role: "assistant",
          content: "Something went wrong. Please try again.",
        },
      ]);
    },
  });

  const handleAsk = useCallback(() => {
    const q = chatQuery.trim();
    if (!q || askMutation.isPending) return;
    // Optimistically add the user message immediately
    setChatHistory((prev) => [...prev, { role: "user", content: q }]);
    setChatQuery("");
    askMutation.mutate(q);
  }, [chatQuery, askMutation]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleAsk();
      }
    },
    [handleAsk],
  );

  const articles: StoredNewsArticle[] = feedQuery.data?.articles ?? [];
  const isEmpty = !feedQuery.isLoading && articles.length === 0;

  return (
    <div className="flex flex-1 gap-4 overflow-hidden">
      {/* ── Left: Article feed ─────────────────────────────────────── */}
      <section
        className="flex flex-1 flex-col gap-3 overflow-hidden"
        aria-labelledby={feedLabelId}
      >
        {/* Feed header */}
        <div className="flex items-center justify-between gap-2 flex-shrink-0">
          <div className="flex items-center gap-2">
            <Newspaper
              className="h-4 w-4 shrink-0"
              style={{ color: "var(--brand-500)" }}
              aria-hidden="true"
            />
            <span
              id={feedLabelId}
              className="text-sm font-semibold"
              style={{ color: "var(--text-primary)" }}
            >
              Live News Feed
            </span>
            {feedQuery.isLoading && (
              <Loader2
                className="h-3 w-3 animate-spin"
                style={{ color: "var(--text-tertiary)" }}
                aria-label="Loading articles"
              />
            )}
          </div>

          <div className="flex items-center gap-2">
            <input
              type="text"
              placeholder="Filter by tag…"
              value={tagFilter}
              onChange={(e) => setTagFilter(e.target.value)}
              className="text-xs rounded-lg border px-2 py-1 w-28"
              style={{
                background: "var(--bg-input)",
                borderColor: "var(--border-default)",
                color: "var(--text-primary)",
              }}
              aria-label="Filter articles by tag"
            />
            <button
              onClick={() => feedQuery.refetch()}
              className="rounded-lg p-1 hover:opacity-70 transition-opacity"
              title="Refresh feed"
              aria-label="Refresh news feed"
            >
              <RefreshCw
                className="h-3.5 w-3.5"
                style={{ color: "var(--text-tertiary)" }}
                aria-hidden="true"
              />
            </button>
          </div>
        </div>

        {/* Articles list */}
        <div className="flex-1 overflow-y-auto space-y-2 pr-1">
          {isEmpty ? (
            <div
              className="flex flex-col items-center justify-center py-16 gap-3 rounded-xl border border-dashed"
              style={{ borderColor: "var(--border-subtle)" }}
            >
              <Newspaper
                className="h-8 w-8"
                style={{ color: "var(--text-tertiary)" }}
                aria-hidden="true"
              />
              <p
                className="text-sm text-center max-w-xs"
                style={{ color: "var(--text-tertiary)" }}
              >
                No articles yet. The scraper runs every 30 minutes — check back
                soon or trigger it manually from the Celery worker.
              </p>
            </div>
          ) : (
            articles.map((art, idx) => (
              <ArticleCard key={art.article_id ?? idx} article={art} />
            ))
          )}
        </div>
      </section>

      {/* ── Right: RAG Chat ────────────────────────────────────────── */}
      <section
        className="w-80 shrink-0 flex flex-col rounded-xl border overflow-hidden"
        style={{
          background: "var(--bg-surface)",
          borderColor: "var(--border-subtle)",
        }}
        aria-labelledby={chatLabelId}
      >
        {/* Chat header */}
        <div
          className="px-4 py-3 border-b flex items-center gap-2 flex-shrink-0"
          style={{ borderColor: "var(--border-subtle)" }}
        >
          <Search
            className="h-4 w-4 shrink-0"
            style={{ color: "var(--brand-500)" }}
            aria-hidden="true"
          />
          <span
            id={chatLabelId}
            className="text-sm font-semibold"
            style={{ color: "var(--text-primary)" }}
          >
            Ask the News
          </span>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-3 space-y-3">
          {chatHistory.length === 0 && (
            <p
              className="text-xs text-center py-8"
              style={{ color: "var(--text-tertiary)" }}
            >
              Ask a question and get answers sourced from stored articles.
            </p>
          )}

          {chatHistory.map((msg, i) => (
            <ChatBubble key={i} message={msg} />
          ))}

          {askMutation.isPending && (
            <div className="flex items-center gap-2 px-3 py-2">
              <Loader2
                className="h-3 w-3 animate-spin"
                style={{ color: "var(--brand-500)" }}
                aria-hidden="true"
              />
              <span className="text-xs" style={{ color: "var(--text-tertiary)" }}>
                Searching articles…
              </span>
            </div>
          )}
        </div>

        {/* Chat input */}
        <div
          className="p-3 border-t flex-shrink-0"
          style={{ borderColor: "var(--border-subtle)" }}
        >
          <div className="flex gap-2">
            <input
              type="text"
              value={chatQuery}
              onChange={(e) => setChatQuery(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask about news…"
              className="flex-1 text-sm rounded-lg border px-3 py-2 min-w-0"
              style={{
                background: "var(--bg-input)",
                borderColor: "var(--border-default)",
                color: "var(--text-primary)",
              }}
              disabled={askMutation.isPending}
              aria-label="News RAG query"
            />
            <button
              onClick={handleAsk}
              disabled={!chatQuery.trim() || askMutation.isPending}
              className="rounded-lg p-2 transition-opacity disabled:opacity-40"
              style={{ background: "var(--brand-500)", color: "white" }}
              aria-label="Send question"
            >
              <Send className="h-4 w-4" aria-hidden="true" />
            </button>
          </div>
        </div>
      </section>
    </div>
  );
});
