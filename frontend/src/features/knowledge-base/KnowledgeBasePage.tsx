import { useState } from "react";
import { BookOpen, Search, Plus, X, Tag, Eye } from "lucide-react";
import { Badge } from "@/shared/components/Badge";
import { Button } from "@/shared/components/Button";
import { Card, CardHeader, CardBody } from "@/shared/components/Card";
import { Input } from "@/shared/components/Input";
import { useKbArticles, useCreateArticle } from "./hooks";
import type { KbArticle } from "./types";

const SEV_VARIANT: Record<string, "danger" | "warning" | "info" | "neutral"> = {
  critical: "danger",
  high: "danger",
  medium: "warning",
  low: "info",
};

const CATEGORIES = ["web", "active-directory", "authentication", "post-exploitation", "network", "mobile", "cloud", "other"];

function ArticleCard({ article, onClick }: { article: KbArticle; onClick: () => void }) {
  return (
    <button onClick={onClick} className="w-full text-left rounded-xl border p-4 transition-colors hover:bg-bg-overlay" style={{ background: "var(--bg-surface)", borderColor: "var(--border-subtle)" }}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-semibold text-sm" style={{ color: "var(--text-primary)" }}>{article.title}</span>
            <Badge variant={SEV_VARIANT[article.severity_context] ?? "neutral"} size="sm">{article.severity_context}</Badge>
          </div>
          <p className="mt-1 text-xs truncate" style={{ color: "var(--text-tertiary)" }}>{article.content.slice(0, 120)}...</p>
          <div className="mt-2 flex flex-wrap gap-1">
            <Badge variant="neutral" size="sm">{article.category}</Badge>
            {article.tags.map((t) => <Badge key={t} variant="neutral" size="sm"><Tag className="h-2.5 w-2.5 mr-0.5" />{t}</Badge>)}
          </div>
        </div>
        <div className="text-xs shrink-0 flex items-center gap-1" style={{ color: "var(--text-tertiary)" }}>
          <Eye className="h-3 w-3" />{article.views}
        </div>
      </div>
    </button>
  );
}

export function KnowledgeBasePage() {
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("");
  const [selected, setSelected] = useState<KbArticle | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [title, setTitle] = useState("");
  const [cat, setCat] = useState("web");
  const [content, setContent] = useState("");
  const [tags, setTags] = useState("");

  const { data: articles = [], isLoading } = useKbArticles(search || undefined, category || undefined);
  const createArticle = useCreateArticle();

  const handleCreate = () => {
    if (!title.trim() || !content.trim()) return;
    createArticle.mutate({
      title: title.trim(),
      category: cat,
      content: content.trim(),
      tags: tags.split(",").map((t) => t.trim()).filter(Boolean),
    }, {
      onSuccess: () => { setShowForm(false); setTitle(""); setContent(""); setTags(""); },
    });
  };

  if (selected) {
    return (
      <div className="space-y-4">
        <button onClick={() => setSelected(null)} className="flex items-center gap-2 text-sm" style={{ color: "var(--brand-400)" }}>
          ← Back to Knowledge Base
        </button>
        <Card>
          <CardHeader>
            <div className="flex items-start justify-between gap-3">
              <div>
                <h2 className="text-lg font-bold" style={{ color: "var(--text-primary)" }}>{selected.title}</h2>
                <div className="mt-2 flex flex-wrap gap-2">
                  <Badge variant="neutral" size="sm">{selected.category}</Badge>
                  <Badge variant={SEV_VARIANT[selected.severity_context] ?? "neutral"} size="sm">{selected.severity_context}</Badge>
                  {selected.tags.map((t) => <Badge key={t} variant="neutral" size="sm">{t}</Badge>)}
                </div>
              </div>
              <div className="text-xs flex items-center gap-1 shrink-0" style={{ color: "var(--text-tertiary)" }}>
                <Eye className="h-3 w-3" />{selected.views} views
              </div>
            </div>
          </CardHeader>
          <CardBody>
            <p className="text-sm leading-relaxed whitespace-pre-wrap" style={{ color: "var(--text-secondary)" }}>{selected.content}</p>
          </CardBody>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <BookOpen className="h-6 w-6" style={{ color: "var(--brand-500)" }} />
          <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>Pentest Knowledge Base</h1>
          <Badge variant="neutral" size="sm">{articles.length} articles</Badge>
        </div>
        <Button leftIcon={<Plus className="h-4 w-4" />} onClick={() => setShowForm((p) => !p)}>
          Add Article
        </Button>
      </div>

      <div className="flex flex-wrap gap-3">
        <div className="flex-1">
          <Input
            placeholder="Search techniques, tags..."
            prefixIcon={<Search className="h-4 w-4" />}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            suffixIcon={search ? <button onClick={() => setSearch("")}><X className="h-4 w-4" /></button> : undefined}
          />
        </div>
        <div className="flex flex-wrap gap-1">
          <button
            onClick={() => setCategory("")}
            className={`rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors ${!category ? "bg-brand-900 text-brand-400" : "text-text-secondary hover:bg-bg-overlay"}`}
          >All</button>
          {CATEGORIES.map((c) => (
            <button
              key={c}
              onClick={() => setCategory(c === category ? "" : c)}
              className={`rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors ${category === c ? "bg-brand-900 text-brand-400" : "text-text-secondary hover:bg-bg-overlay"}`}
            >{c}</button>
          ))}
        </div>
      </div>

      {showForm && (
        <Card>
          <CardBody className="space-y-3">
            <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Add Knowledge Article</h3>
            <Input placeholder="Title" value={title} onChange={(e) => setTitle(e.target.value)} />
            <div className="flex flex-wrap gap-1">
              {CATEGORIES.map((c) => (
                <button key={c} onClick={() => setCat(c)}
                  className={`rounded px-2.5 py-1 text-xs font-medium transition-colors ${cat === c ? "bg-brand-900 text-brand-400" : "text-text-secondary hover:bg-bg-overlay"}`}
                >{c}</button>
              ))}
            </div>
            <textarea
              placeholder="Content / technique details..."
              value={content}
              onChange={(e) => setContent(e.target.value)}
              rows={5}
              className="w-full rounded-md border px-3 py-2 text-sm resize-none"
              style={{ background: "var(--bg-elevated)", borderColor: "var(--border-default)", color: "var(--text-primary)" }}
            />
            <Input placeholder="Tags (comma-separated)" value={tags} onChange={(e) => setTags(e.target.value)} />
            <div className="flex gap-2">
              <Button size="sm" onClick={handleCreate} loading={createArticle.isPending}>Create</Button>
              <Button size="sm" variant="ghost" onClick={() => setShowForm(false)}>Cancel</Button>
            </div>
          </CardBody>
        </Card>
      )}

      {isLoading ? (
        <div className="py-12 text-center text-sm" style={{ color: "var(--text-tertiary)" }}>Loading...</div>
      ) : articles.length === 0 ? (
        <Card><CardBody><p className="text-center text-sm" style={{ color: "var(--text-tertiary)" }}>No articles found.</p></CardBody></Card>
      ) : (
        <div className="space-y-2">
          {articles.map((a) => <ArticleCard key={a.id} article={a} onClick={() => setSelected(a)} />)}
        </div>
      )}
    </div>
  );
}
