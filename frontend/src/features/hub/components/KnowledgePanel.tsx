/**
 * KnowledgePanel — document upload and knowledge base management.
 *
 * Supports file upload (PDF, Markdown, plain text) and URL ingestion.
 * Shows ingestion progress via the hub agent stream.
 */

import { memo, useId, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useMutation } from "@tanstack/react-query";
import { Upload, Link, FileText, Loader2 } from "lucide-react";
import apiClient from "@/shared/api/client";

interface IngestResponse {
  job_id: string;
  doc_id: string;
  status: string;
}

async function ingestFile(file: File): Promise<IngestResponse> {
  const form = new FormData();
  form.append("file", file);
  const { data } = await apiClient.post<IngestResponse>("/knowledge/ingest", form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

async function ingestUrl(url: string): Promise<IngestResponse> {
  const { data } = await apiClient.post<IngestResponse>("/knowledge/ingest", { url });
  return data;
}

export const KnowledgePanel = memo(function KnowledgePanel() {
  const { t } = useTranslation("knowledge");
  const labelId = useId();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [url, setUrl] = useState("");
  const [lastJobId, setLastJobId] = useState<string | null>(null);

  const fileMutation = useMutation({
    mutationFn: ingestFile,
    onSuccess: (data) => setLastJobId(data.job_id),
  });

  const urlMutation = useMutation({
    mutationFn: ingestUrl,
    onSuccess: (data) => setLastJobId(data.job_id),
  });

  const isPending = fileMutation.isPending || urlMutation.isPending;

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) fileMutation.mutate(file);
  }

  function handleUrlSubmit() {
    if (url.trim()) urlMutation.mutate(url.trim());
  }

  return (
    <section aria-labelledby={labelId} className="flex flex-col gap-4">
      <h3
        id={labelId}
        className="text-sm font-semibold uppercase tracking-wide"
        style={{ color: "var(--text-tertiary)" }}
      >
        {t("title")}
      </h3>

      {/* File drop zone */}
      <button
        type="button"
        onClick={() => fileInputRef.current?.click()}
        disabled={isPending}
        className={`flex flex-col items-center gap-2 rounded-xl border-2 border-dashed p-6 text-center transition-colors
          ${isPending ? "cursor-not-allowed opacity-60" : "hover:border-brand-400 cursor-pointer"}`}
        style={{ borderColor: "var(--border-default)", background: "var(--bg-surface)" }}
        aria-label={t("upload_label")}
      >
        {isPending ? (
          <Loader2
            className="h-8 w-8 animate-spin"
            style={{ color: "var(--brand-500)" }}
            aria-hidden="true"
          />
        ) : (
          <Upload className="h-8 w-8" style={{ color: "var(--text-tertiary)" }} aria-hidden="true" />
        )}
        <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
          {isPending ? t("ingesting") : t("drag_drop")}
        </p>
        <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>
          PDF, Markdown, plain text
        </p>
      </button>
      <input
        ref={fileInputRef}
        type="file"
        accept=".pdf,.md,.markdown,.txt"
        className="sr-only"
        onChange={handleFileChange}
        aria-hidden="true"
      />

      {/* URL ingestion */}
      <div className="flex gap-2">
        <div className="relative flex-1">
          <Link
            className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2"
            style={{ color: "var(--text-tertiary)" }}
            aria-hidden="true"
          />
          <input
            type="url"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") handleUrlSubmit(); }}
            placeholder={t("url_label")}
            disabled={isPending}
            className="w-full rounded-lg border py-2 pl-9 pr-3 text-sm outline-none"
            style={{
              background: "var(--bg-surface)",
              borderColor: "var(--border-default)",
              color: "var(--text-primary)",
            }}
          />
        </div>
        <button
          type="button"
          onClick={handleUrlSubmit}
          disabled={!url.trim() || isPending}
          className="flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm font-medium transition-all hover:scale-105 disabled:opacity-40"
          style={{ background: "var(--brand-500)", color: "white" }}
        >
          <FileText className="h-4 w-4" aria-hidden="true" />
          {t("ingest_button")}
        </button>
      </div>

      {/* Last job status */}
      {lastJobId && !isPending && (
        <p className="text-xs" style={{ color: "var(--success-500)" }}>
          {t("ingestion_done", { chunks: "—" })} (job: {lastJobId})
        </p>
      )}

      {(fileMutation.isError || urlMutation.isError) && (
        <p className="text-xs" style={{ color: "var(--danger-500)" }}>
          {t("error", { ns: "common" })}
        </p>
      )}
    </section>
  );
});
