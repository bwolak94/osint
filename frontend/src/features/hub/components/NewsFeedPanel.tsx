/**
 * NewsFeedPanel — live news feed + RAG chat for the News module.
 *
 * Left panel has tabs:
 *   Feed | Bookmarks | Trending | Sources | Topics
 *
 * Right panel: RAG chat (unchanged).
 */

import { memo, useState, useCallback, useId, useRef, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  AlertCircle,
  Bookmark,
  BookmarkCheck,
  ChevronLeft,
  ChevronRight,
  ExternalLink,
  Loader2,
  Newspaper,
  Play,
  RefreshCw,
  Rss,
  Search,
  Send,
  Tag,
  TrendingUp,
} from "lucide-react";

import {
  getNewsFeed,
  askNewsRag,
  addNewsBookmark,
  getNewsBookmarks,
  triggerNewsScrape,
} from "../api";
import type { NewsBookmark, NewsRagResponse, StoredNewsArticle } from "../types";

import { NewsSourcesPanel } from "./NewsSourcesPanel";
import { NewsBookmarksPanel } from "./NewsBookmarksPanel";
import { NewsTrendingPanel } from "./NewsTrendingPanel";
import { NewsTopicsPanel } from "./NewsTopicsPanel";
import { QueueStatusBadge } from "./QueueStatusBadge";

const PAGE_SIZE = 20;

const EXAMPLE_PROMPTS = [
  "What are the latest cybersecurity threats?",
  "Summarize recent AI breakthroughs",
  "Any news about data breaches this week?",
  "What geopolitical events should I know about?",
];

type FeedTab = "feed" | "bookmarks" | "trending" | "sources" | "topics";

const TAB_CONFIG: { id: FeedTab; label: string; icon: React.ReactNode }[] = [
  { id: "feed", label: "Feed", icon: <Newspaper className="h-3 w-3" /> },
  { id: "bookmarks", label: "Saved", icon: <Bookmark className="h-3 w-3" /> },
  { id: "trending", label: "Trending", icon: <TrendingUp className="h-3 w-3" /> },
  { id: "sources", label: "Sources", icon: <Rss className="h-3 w-3" /> },
  { id: "topics", label: "Topics", icon: <Tag className="h-3 w-3" /> },
];

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  sources?: NewsRagResponse["sources"];
}

// ── Article card ─────────────────────────────────────────────────────────────

interface ArticleCardProps {
  article: StoredNewsArticle;
  isBookmarked: boolean;
  onBookmark: (article: StoredNewsArticle) => void;
}

const ArticleCard = memo(function ArticleCard({
  article,
  isBookmarked,
  onBookmark,
}: ArticleCardProps) {
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
            <ExternalLink className="h-3 w-3 mt-0.5 shrink-0 opacity-60" aria-hidden="true" />
          </a>

          {article.summary && (
            <p className="mt-1 text-xs line-clamp-2" style={{ color: "var(--text-secondary)" }}>
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

        <div className="flex flex-col items-end gap-1 shrink-0">
          {article.credibility_score > 0 && (
            <span
              className="text-xs px-1.5 py-0.5 rounded-full"
              style={{
                background:
                  article.credibility_score >= 0.8 ? "var(--success-50)" : "var(--warning-50)",
                color:
                  article.credibility_score >= 0.8 ? "var(--success-600)" : "var(--warning-600)",
              }}
            >
              {Math.round(article.credibility_score * 100)}%
            </span>
          )}

          {/* Bookmark button */}
          <button
            onClick={() => onBookmark(article)}
            className="rounded p-0.5 hover:opacity-70 transition-opacity"
            aria-label={isBookmarked ? "Remove bookmark" : "Bookmark article"}
            title={isBookmarked ? "Bookmarked" : "Bookmark"}
          >
            {isBookmarked ? (
              <BookmarkCheck
                className="h-3.5 w-3.5"
                style={{ color: "var(--brand-500)" }}
              />
            ) : (
              <Bookmark
                className="h-3.5 w-3.5"
                style={{ color: "var(--text-tertiary)" }}
              />
            )}
          </button>
        </div>
      </div>
    </article>
  );
});

// ── Pagination controls ───────────────────────────────────────────────────────

interface PaginationProps {
  page: number;
  total: number;
  pageSize: number;
  onPageChange: (page: number) => void;
  disabled?: boolean;
}

function Pagination({ page, total, pageSize, onPageChange, disabled }: PaginationProps) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  if (totalPages <= 1) return null;

  return (
    <div className="flex items-center justify-between flex-shrink-0 pt-1">
      <button
        onClick={() => onPageChange(page - 1)}
        disabled={disabled || page === 0}
        className="flex items-center gap-1 rounded-lg px-2 py-1 text-xs transition-opacity disabled:opacity-40 hover:opacity-70"
        style={{ color: "var(--text-secondary)" }}
        aria-label="Previous page"
      >
        <ChevronLeft className="h-3 w-3" aria-hidden="true" />
        Prev
      </button>
      <span className="text-xs" style={{ color: "var(--text-tertiary)" }}>
        {page + 1} / {totalPages}
      </span>
      <button
        onClick={() => onPageChange(page + 1)}
        disabled={disabled || page >= totalPages - 1}
        className="flex items-center gap-1 rounded-lg px-2 py-1 text-xs transition-opacity disabled:opacity-40 hover:opacity-70"
        style={{ color: "var(--text-secondary)" }}
        aria-label="Next page"
      >
        Next
        <ChevronRight className="h-3 w-3" aria-hidden="true" />
      </button>
    </div>
  );
}

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
          <div
            className="mt-2 pt-2 space-y-0.5"
            style={{ borderTop: "1px solid rgba(255,255,255,0.2)" }}
          >
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
  const qc = useQueryClient();
  const [activeTab, setActiveTab] = useState<FeedTab>("feed");
  const [chatQuery, setChatQuery] = useState("");
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]);
  const [tagFilter, setTagFilter] = useState("");
  const [page, setPage] = useState(0);
  const [scrapeMsg, setScrapeMsg] = useState<string | null>(null);

  const feedLabelId = useId();
  const chatLabelId = useId();
  const chatBottomRef = useRef<HTMLDivElement>(null);

  const handleTagChange = useCallback((value: string) => {
    setTagFilter(value);
    setPage(0);
  }, []);

  // When a trending tag is clicked, switch to feed tab and apply filter
  const handleTrendingTagSelect = useCallback((tag: string) => {
    setTagFilter(tag);
    setPage(0);
    setActiveTab("feed");
  }, []);

  const feedQuery = useQuery({
    queryKey: ["news", "feed", tagFilter, page],
    queryFn: () =>
      getNewsFeed({
        limit: PAGE_SIZE,
        offset: page * PAGE_SIZE,
        ...(tagFilter.trim() ? { tag: tagFilter.trim() } : {}),
      }),
    refetchInterval: 5 * 60 * 1000,
    staleTime: 60_000,
    enabled: activeTab === "feed",
  });

  // Load bookmarks to know which articles are already saved
  const { data: bookmarksData } = useQuery<NewsBookmark[]>({
    queryKey: ["news", "bookmarks"],
    queryFn: getNewsBookmarks,
    staleTime: 60_000,
  });
  const bookmarkedIds = new Set((bookmarksData ?? []).map((b) => b.article_id));

  const bookmarkMutation = useMutation({
    mutationFn: (article: StoredNewsArticle) =>
      addNewsBookmark(article.article_id, {
        url: article.url,
        title: article.title,
        source_domain: article.source_domain,
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["news", "bookmarks"] }),
  });

  const scrapeMutation = useMutation({
    mutationFn: triggerNewsScrape,
    onSuccess: (data) => {
      setScrapeMsg(`Scrape queued (${data.task_id.slice(0, 8)}…)`);
      setTimeout(() => setScrapeMsg(null), 4000);
      // Invalidate feed after a short delay to pick up new articles
      setTimeout(
        () => qc.invalidateQueries({ queryKey: ["news", "feed"] }),
        5000,
      );
    },
    onError: () => {
      setScrapeMsg("Failed to trigger scrape");
      setTimeout(() => setScrapeMsg(null), 3000);
    },
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
        { role: "assistant", content: "Something went wrong. Please try again." },
      ]);
    },
  });

  useEffect(() => {
    chatBottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatHistory, askMutation.isPending]);

  const handleAsk = useCallback(
    (question?: string) => {
      const q = (question ?? chatQuery).trim();
      if (!q || askMutation.isPending) return;
      setChatHistory((prev) => [...prev, { role: "user", content: q }]);
      setChatQuery("");
      askMutation.mutate(q);
    },
    [chatQuery, askMutation],
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleAsk();
      }
    },
    [handleAsk],
  );

  const articles: StoredNewsArticle[] = (feedQuery.data?.articles ?? []).filter((a) => {
    if (!tagFilter.trim()) return true;
    const q = tagFilter.trim().toLowerCase();
    return (
      a.tags?.some((t) => t.toLowerCase().includes(q)) ||
      a.title.toLowerCase().includes(q) ||
      a.source_domain.toLowerCase().includes(q)
    );
  });

  const total = feedQuery.data?.total ?? 0;
  const isEmpty = !feedQuery.isLoading && !feedQuery.isError && articles.length === 0;

  return (
    <div className="flex flex-1 gap-4 overflow-hidden">
      {/* ── Left: tabbed panels ────────────────────────────────────── */}
      <section
        className="flex flex-1 flex-col gap-3 overflow-hidden"
        aria-labelledby={feedLabelId}
      >
        {/* Tab bar + queue status */}
        <div className="flex items-center justify-between gap-2 flex-shrink-0">
          <div className="flex items-center gap-1 rounded-lg p-0.5" style={{ background: "var(--bg-elevated)" }}>
            {TAB_CONFIG.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className="flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs font-medium transition-all"
                style={
                  activeTab === tab.id
                    ? { background: "var(--bg-surface)", color: "var(--brand-500)", boxShadow: "0 1px 3px rgba(0,0,0,0.1)" }
                    : { color: "var(--text-tertiary)" }
                }
                aria-pressed={activeTab === tab.id}
              >
                {tab.icon}
                {tab.label}
              </button>
            ))}
          </div>

          <QueueStatusBadge />
        </div>

        {/* Feed-specific controls */}
        {activeTab === "feed" && (
          <div className="flex items-center justify-between gap-2 flex-shrink-0">
            <div className="flex items-center gap-2">
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
              {total > 0 && !feedQuery.isLoading && (
                <span className="text-xs" style={{ color: "var(--text-tertiary)" }}>
                  ({total})
                </span>
              )}
            </div>

            <div className="flex items-center gap-2">
              {scrapeMsg && (
                <span className="text-xs" style={{ color: "var(--success-500)" }}>
                  {scrapeMsg}
                </span>
              )}

              <input
                type="text"
                placeholder="Filter articles…"
                value={tagFilter}
                onChange={(e) => handleTagChange(e.target.value)}
                className="text-xs rounded-lg border px-2 py-1 w-32"
                style={{
                  background: "var(--bg-input)",
                  borderColor: "var(--border-default)",
                  color: "var(--text-primary)",
                }}
                aria-label="Filter articles by tag, title, or source"
              />

              {/* Manual scrape trigger */}
              <button
                onClick={() => scrapeMutation.mutate()}
                disabled={scrapeMutation.isPending}
                className="rounded-lg p-1.5 hover:opacity-70 transition-opacity disabled:opacity-40"
                title="Trigger news scrape"
                aria-label="Trigger news scrape"
                style={{ background: "var(--bg-elevated)" }}
              >
                {scrapeMutation.isPending ? (
                  <Loader2 className="h-3 w-3 animate-spin" style={{ color: "var(--brand-500)" }} />
                ) : (
                  <Play className="h-3 w-3" style={{ color: "var(--brand-500)" }} />
                )}
              </button>

              {/* Refresh */}
              <button
                onClick={() => feedQuery.refetch()}
                className="rounded-lg p-1 hover:opacity-70 transition-opacity"
                title="Refresh feed"
                aria-label="Refresh news feed"
              >
                <RefreshCw
                  className={`h-3.5 w-3.5 ${feedQuery.isFetching ? "animate-spin" : ""}`}
                  style={{ color: "var(--text-tertiary)" }}
                  aria-hidden="true"
                />
              </button>
            </div>
          </div>
        )}

        {/* Tab content */}
        <div className="flex-1 overflow-y-auto">
          {/* ── Feed tab ── */}
          {activeTab === "feed" && (
            <div className="flex flex-col h-full gap-2">
              {/* Error state */}
              {feedQuery.isError && (
                <div
                  className="flex items-center gap-2 rounded-xl border px-4 py-3 flex-shrink-0"
                  style={{ borderColor: "var(--danger-500)", background: "var(--danger-50)" }}
                  role="alert"
                >
                  <AlertCircle className="h-4 w-4 shrink-0" style={{ color: "var(--danger-500)" }} />
                  <p className="text-xs" style={{ color: "var(--danger-600)" }}>
                    Failed to load articles.{" "}
                    <button onClick={() => feedQuery.refetch()} className="underline hover:opacity-70">
                      Retry
                    </button>
                  </p>
                </div>
              )}

              <div className="flex-1 overflow-y-auto space-y-2 pr-1">
                {isEmpty ? (
                  <div
                    className="flex flex-col items-center justify-center py-16 gap-3 rounded-xl border border-dashed"
                    style={{ borderColor: "var(--border-subtle)" }}
                  >
                    <Newspaper className="h-8 w-8" style={{ color: "var(--text-tertiary)" }} />
                    <p className="text-sm text-center max-w-xs" style={{ color: "var(--text-tertiary)" }}>
                      {tagFilter.trim()
                        ? `No articles match "${tagFilter}".`
                        : "No articles yet. Click ▶ to trigger a scrape or wait for the scheduled run."}
                    </p>
                  </div>
                ) : (
                  articles.map((art, idx) => (
                    <ArticleCard
                      key={art.article_id ?? idx}
                      article={art}
                      isBookmarked={bookmarkedIds.has(art.article_id)}
                      onBookmark={bookmarkMutation.mutate}
                    />
                  ))
                )}
              </div>

              <Pagination
                page={page}
                total={total}
                pageSize={PAGE_SIZE}
                onPageChange={setPage}
                disabled={feedQuery.isLoading || feedQuery.isFetching}
              />
            </div>
          )}

          {/* ── Bookmarks tab ── */}
          {activeTab === "bookmarks" && <NewsBookmarksPanel />}

          {/* ── Trending tab ── */}
          {activeTab === "trending" && (
            <NewsTrendingPanel onTagSelect={handleTrendingTagSelect} />
          )}

          {/* ── Sources tab ── */}
          {activeTab === "sources" && <NewsSourcesPanel />}

          {/* ── Topics tab ── */}
          {activeTab === "topics" && <NewsTopicsPanel />}
        </div>
      </section>

      {/* ── Right: RAG Chat ────────────────────────────────────────── */}
      <section
        className="w-80 shrink-0 flex flex-col rounded-xl border overflow-hidden"
        style={{ background: "var(--bg-surface)", borderColor: "var(--border-subtle)" }}
        aria-labelledby={chatLabelId}
      >
        {/* Chat header */}
        <div
          className="px-4 py-3 border-b flex items-center gap-2 flex-shrink-0"
          style={{ borderColor: "var(--border-subtle)" }}
        >
          <Search className="h-4 w-4 shrink-0" style={{ color: "var(--brand-500)" }} aria-hidden="true" />
          <span id={chatLabelId} className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
            Ask the News
          </span>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-3 space-y-3" aria-live="polite">
          {chatHistory.length === 0 ? (
            <div className="space-y-2">
              <p className="text-xs text-center py-4" style={{ color: "var(--text-tertiary)" }}>
                Ask a question and get answers sourced from stored articles.
              </p>
              <div className="space-y-1.5">
                {EXAMPLE_PROMPTS.map((prompt) => (
                  <button
                    key={prompt}
                    onClick={() => handleAsk(prompt)}
                    disabled={askMutation.isPending}
                    className="w-full text-left text-xs rounded-lg border px-3 py-2 transition-colors hover:opacity-80 disabled:opacity-40"
                    style={{
                      background: "var(--bg-elevated)",
                      borderColor: "var(--border-subtle)",
                      color: "var(--text-secondary)",
                    }}
                  >
                    {prompt}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            chatHistory.map((msg, i) => <ChatBubble key={i} message={msg} />)
          )}

          {askMutation.isPending && (
            <div className="flex items-center gap-2 px-3 py-2">
              <Loader2 className="h-3 w-3 animate-spin" style={{ color: "var(--brand-500)" }} aria-hidden="true" />
              <span className="text-xs" style={{ color: "var(--text-tertiary)" }}>
                Searching articles…
              </span>
            </div>
          )}
          <div ref={chatBottomRef} />
        </div>

        {/* Chat input */}
        <div className="p-3 border-t flex-shrink-0" style={{ borderColor: "var(--border-subtle)" }}>
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
              onClick={() => handleAsk()}
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
