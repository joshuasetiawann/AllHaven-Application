"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { BookOpenCheck, Database, FileArchive, FileText, RefreshCw, Search, ShieldCheck, Trash2, UploadCloud } from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { PageHeader } from "@/components/layout/PageHeader";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState, ErrorState, Loading } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";
import { useAppDialog } from "@/components/ui/AppDialog";
import { knowledgeApi, ApiException } from "@/lib/api";
import { cn, formatDateTime } from "@/lib/format";
import type { KnowledgeDocument, KnowledgeSearchResult } from "@/types";

function formatSize(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const i = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  const value = bytes / Math.pow(1024, i);
  return `${value.toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
}

function statusTone(status: KnowledgeDocument["status"]): "success" | "warning" | "danger" | "neutral" {
  if (status === "indexed") return "success";
  if (status === "indexing" || status === "uploaded") return "warning";
  if (status === "failed") return "danger";
  return "neutral";
}

export default function AiKnowledgePage() {
  const toast = useToast();
  const dialog = useAppDialog();
  const [documents, setDocuments] = useState<KnowledgeDocument[] | null>(null);
  const [results, setResults] = useState<KnowledgeSearchResult[]>([]);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const load = async () => {
    setError(null);
    try {
      setDocuments(await knowledgeApi.listDocuments());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load knowledge documents.");
    }
  };

  useEffect(() => { void load(); }, []);

  const stats = useMemo(() => {
    const rows = documents ?? [];
    return {
      total: rows.length,
      indexed: rows.filter((d) => d.status === "indexed").length,
      metadataOnly: rows.filter((d) => d.meta?.metadata_only || d.status === "uploaded").length,
      chunks: rows.reduce((sum, d) => sum + d.chunk_count, 0),
    };
  }, [documents]);

  const uploadFile = async (file: File | undefined | null) => {
    if (!file) return;
    setUploading(true);
    setError(null);
    try {
      const doc = await knowledgeApi.uploadDocument(file);
      await load();
      if (doc.status === "indexed") {
        toast.success("File indexed", `${doc.filename} is ready for AI Knowledge search.`);
      } else {
        toast.warning("File stored", `${doc.filename} was uploaded. Text was not extracted, so it is searchable by metadata only.`);
      }
    } catch (err) {
      const message = err instanceof ApiException ? err.message : "Upload failed.";
      setError(message);
      toast.danger("Upload failed", message);
    } finally {
      setUploading(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  };

  const upload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    await uploadFile(event.target.files?.[0]);
  };

  const dropUpload = async (event: React.DragEvent<HTMLButtonElement>) => {
    event.preventDefault();
    setDragging(false);
    await uploadFile(event.dataTransfer.files?.[0]);
  };

  const runSearch = async (event?: React.FormEvent) => {
    event?.preventDefault();
    const q = query.trim();
    if (!q) { setResults([]); return; }
    setLoading(true);
    setError(null);
    try {
      const res = await knowledgeApi.search(q);
      setResults(res.results);
      if (res.results.length === 0) toast.info("No matches", "Try another keyword or upload an indexed text/code file.");
    } catch (err) {
      const message = err instanceof ApiException ? err.message : "Search failed.";
      setError(message);
      toast.danger("Search failed", message);
    } finally {
      setLoading(false);
    }
  };

  const reindex = async (doc: KnowledgeDocument) => {
    setBusyId(doc.id);
    setError(null);
    try {
      const updated = await knowledgeApi.reindex(doc.id);
      await load();
      toast.success("Re-index complete", `${updated.title} now has ${updated.chunk_count} chunks.`);
    } catch (err) {
      const message = err instanceof ApiException ? err.message : "Re-index failed.";
      setError(message);
      toast.danger("Re-index failed", message);
    } finally {
      setBusyId(null);
    }
  };

  const remove = async (doc: KnowledgeDocument) => {
    const ok = await dialog.confirm({
      title: "Delete knowledge document?",
      message: `Delete "${doc.title}" from AI Knowledge? AI models will no longer retrieve it.`,
      confirmLabel: "Delete",
      tone: "danger",
    });
    if (!ok) return;
    setBusyId(doc.id);
    setError(null);
    setDocuments((prev) => prev?.filter((d) => d.id !== doc.id) ?? prev);
    try {
      await knowledgeApi.remove(doc.id);
      toast.success("Knowledge removed", doc.title);
    } catch (err) {
      const message = err instanceof ApiException ? err.message : "Delete failed.";
      setError(message);
      toast.danger("Delete failed", message);
      await load();
    } finally {
      setBusyId(null);
    }
  };

  return (
    <AppShell>
      <PageHeader
        title="AI Knowledge"
        subtitle="Indexed documents available to AI Chat."
        actions={
          <Button onClick={() => inputRef.current?.click()} loading={uploading} disabled={uploading}>
            <UploadCloud size={16} /> Upload
          </Button>
        }
      />

      <input ref={inputRef} type="file" className="hidden" onChange={upload} />

      {error ? <div className="mb-4"><ErrorState message={error} /></div> : null}

      <div className="mb-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <Card padding="sm">
          <p className="label-mono">Documents</p>
          <p className="mt-1 text-2xl font-semibold text-content">{stats.total}</p>
        </Card>
        <Card padding="sm">
          <p className="label-mono">Indexed</p>
          <p className="mt-1 text-2xl font-semibold text-success">{stats.indexed}</p>
        </Card>
        <Card padding="sm">
          <p className="label-mono">Chunks</p>
          <p className="mt-1 text-2xl font-semibold text-primary">{stats.chunks}</p>
        </Card>
      </div>

      <div className="mb-5 grid gap-4 lg:grid-cols-[1fr_380px]">
        <Card className="p-4">
          <form onSubmit={runSearch} className="flex flex-col gap-2 sm:flex-row">
            <div className="relative min-w-0 flex-1">
              <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-content-subtle" />
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search indexed knowledge"
                className="h-10 w-full rounded-lg border border-border bg-surface-input pl-9 pr-3 text-sm text-content focus:border-primary/70 focus:outline-none focus:ring-1 focus:ring-primary/30"
              />
            </div>
            <Button type="submit" loading={loading} className="w-full sm:w-auto"><Search size={15} /> Search</Button>
          </form>
          {results.length ? (
            <div className="mt-4 space-y-2.5">
              {results.map((r) => (
                <div key={r.chunk_id} className="rounded-lg border border-border bg-surface-input p-3">
                  <div className="mb-1 flex flex-wrap items-center gap-2 text-[12px] text-content-subtle">
                    <Badge tone="primary">{r.document_title}</Badge>
                    <span>{r.document_filename}</span>
                    <span>chunk {r.chunk_index}</span>
                  </div>
                  <p className="line-clamp-3 text-sm leading-relaxed text-content-muted">{r.content}</p>
                </div>
              ))}
            </div>
          ) : null}
        </Card>

        <Card className="p-4">
          <button
            type="button"
            onClick={() => inputRef.current?.click()}
            disabled={uploading}
            onDragEnter={(e) => { e.preventDefault(); setDragging(true); }}
            onDragOver={(e) => e.preventDefault()}
            onDragLeave={() => setDragging(false)}
            onDrop={dropUpload}
            className={cn(
              "flex min-h-[170px] w-full flex-col items-center justify-center rounded-lg border border-dashed bg-surface-input px-5 py-6 text-center transition-colors disabled:opacity-60",
              dragging ? "border-primary bg-primary/10" : "border-border hover:border-primary/50",
            )}
          >
            <BookOpenCheck size={24} className="mb-3 text-primary" />
            <span className="text-sm font-medium text-content">{uploading ? "Uploading..." : "Upload document"}</span>
            <span className="mt-1 text-[12px] text-content-subtle">Any file is accepted. Text/code is indexed; binary files are stored as metadata.</span>
          </button>
          <div className="mt-3 grid gap-2 text-[12px] text-content-muted sm:grid-cols-2">
            <div className="rounded-lg border border-border bg-surface-input px-3 py-2">
              <ShieldCheck size={14} className="mb-1 text-success" />
              Secret-like text is protected from indexing.
            </div>
            <div className="rounded-lg border border-border bg-surface-input px-3 py-2">
              <Database size={14} className="mb-1 text-primary" />
              {stats.metadataOnly} metadata-only files stored.
            </div>
          </div>
        </Card>
      </div>

      {!documents ? (
        <Loading />
      ) : documents.length === 0 ? (
        <EmptyState
          title="No knowledge documents"
          description="Upload an indexable document to make it available to AI Chat."
          icon={<BookOpenCheck size={20} />}
          action={<Button onClick={() => inputRef.current?.click()}><UploadCloud size={16} /> Upload</Button>}
        />
      ) : (
        <div className="space-y-2.5">
          {documents.map((doc) => (
            <Card key={doc.id} className="p-4" hover>
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div className="flex min-w-0 items-start gap-3">
                  <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-border bg-surface-input text-primary">
                    <FileText size={18} />
                  </span>
                  <div className="min-w-0">
                    <div className="flex min-w-0 flex-wrap items-center gap-2">
                      <p className="min-w-0 truncate text-sm font-semibold text-content">{doc.title}</p>
                      <Badge tone={statusTone(doc.status)}>{doc.status}</Badge>
                      {doc.status === "indexed" ? <Badge tone="success">usable by AI</Badge> : <Badge tone="warning">metadata only</Badge>}
                    </div>
                    <p className="mt-0.5 break-words text-[12px] text-content-subtle">
                      {doc.filename} · {formatSize(doc.size_bytes)} · {doc.chunk_count} chunks
                      {doc.last_indexed_at ? ` · indexed ${formatDateTime(doc.last_indexed_at)}` : ""}
                    </p>
                    {doc.error_message ? <p className="mt-1 text-[12px] text-warning">{doc.error_message}</p> : null}
                  </div>
                </div>
                <div className="flex w-full shrink-0 flex-wrap items-center gap-1.5 sm:w-auto sm:justify-end">
                  {doc.meta?.metadata_only ? (
                    <span className="hidden items-center gap-1 rounded-md border border-warning/25 bg-warning/10 px-2 py-1 text-[11px] text-warning sm:inline-flex">
                      <FileArchive size={12} /> Stored only
                    </span>
                  ) : null}
                  <Button variant="ghost" size="sm" onClick={() => reindex(doc)} loading={busyId === doc.id} disabled={busyId === doc.id} className="flex-1 sm:flex-none">
                    <RefreshCw size={14} /> Re-index
                  </Button>
                  <button
                    onClick={() => remove(doc)}
                    disabled={busyId === doc.id}
                    className="rounded-md p-2 text-content-subtle transition-colors hover:text-danger disabled:opacity-50"
                    aria-label="Delete document"
                  >
                    <Trash2 size={15} />
                  </button>
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}
    </AppShell>
  );
}
