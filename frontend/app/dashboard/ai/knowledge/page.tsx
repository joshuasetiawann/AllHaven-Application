"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { BookOpenCheck, Database, FileArchive, FilePlus, FileText, RefreshCw, ScrollText, Search, ShieldCheck, Trash2, UploadCloud } from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState, ErrorState, Loading } from "@/components/ui/States";
import { SetupRequiredState } from "@/components/SetupRequiredState";
import { isBackendUnreachable } from "@/lib/connection";
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

function fileKind(filename: string): string {
  const ext = filename.includes(".") ? filename.split(".").pop() : null;
  return ext ? ext.toUpperCase() : "FILE";
}

const sourceTiles = [
  { icon: BookOpenCheck, tint: "bg-primary/[0.12] text-primary-bright" },
  { icon: ScrollText, tint: "bg-secondary/[0.14] text-secondary-soft" },
  { icon: FileText, tint: "bg-success/[0.13] text-success-soft" },
];

export default function AiKnowledgePage() {
  const toast = useToast();
  const dialog = useAppDialog();
  const [documents, setDocuments] = useState<KnowledgeDocument[] | null>(null);
  const [results, setResults] = useState<KnowledgeSearchResult[]>([]);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [setupNeeded, setSetupNeeded] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const load = async () => {
    setError(null);
    setSetupNeeded(false);
    try {
      setDocuments(await knowledgeApi.listDocuments());
    } catch (err) {
      if (isBackendUnreachable(err)) setSetupNeeded(true);
      else setError(err instanceof Error ? err.message : "Failed to load knowledge documents.");
    }
  };

  useEffect(() => { void load(); }, []);

  const stats = useMemo(() => {
    const rows = documents ?? [];
    return {
      total: rows.length,
      indexed: rows.filter((d) => d.status === "indexed").length,
      metadataOnly: rows.filter((d) => d.meta?.metadata_only || d.status === "uploaded").length,
      failed: rows.filter((d) => d.status === "failed").length,
      chunks: rows.reduce((sum, d) => sum + d.chunk_count, 0),
    };
  }, [documents]);

  const uploadFiles = async (files: File[] | FileList | undefined | null) => {
    const picks = Array.from(files ?? []).filter(Boolean);
    if (!picks.length) return;
    setUploading(true);
    setError(null);
    let indexed = 0;
    let stored = 0;
    let failed = 0;
    try {
      for (const [index, file] of picks.entries()) {
        setUploadProgress(`Uploading ${index + 1}/${picks.length}: ${file.name}`);
        try {
          const doc = await knowledgeApi.uploadDocument(file);
          if (doc.status === "indexed") indexed += 1;
          else stored += 1;
        } catch (err) {
          failed += 1;
          const message = err instanceof ApiException ? err.message : `Upload failed for ${file.name}.`;
          setError(message);
          toast.danger("Upload failed", message);
        }
      }
      await load();
      if (indexed) toast.success("Knowledge indexed", `${indexed} file${indexed === 1 ? "" : "s"} ready for AI search.`);
      if (stored) toast.warning("Files stored", `${stored} file${stored === 1 ? "" : "s"} stored as metadata only.`);
      if (!failed && !indexed && !stored) toast.info("No files uploaded", "Choose PDF, DOC, DOCX, text, or code files.");
    } finally {
      setUploading(false);
      setUploadProgress(null);
      if (inputRef.current) inputRef.current.value = "";
    }
  };

  const upload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    await uploadFiles(event.target.files);
  };

  const dropUpload = async (event: React.DragEvent<HTMLButtonElement>) => {
    event.preventDefault();
    setDragging(false);
    await uploadFiles(event.dataTransfer.files);
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

  const clearSearch = () => {
    setQuery("");
    setResults([]);
    setError(null);
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
      <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div className="min-w-0">
          <div className="flex items-center gap-2.5">
            <h1 className="text-2xl font-semibold tracking-[-0.02em] text-content sm:text-[30px]">AI Knowledge</h1>
            <Badge tone="primary" className="text-[10.5px] font-semibold">NEW</Badge>
          </div>
          <p className="mt-1.5 max-w-2xl text-[13.5px] leading-relaxed text-content-muted">
            Documents your agents can ground answers in. Retrieval only — never auto-edited.
          </p>
        </div>
        <div className="flex w-full flex-wrap items-center gap-2 sm:w-auto sm:justify-end">
          <Button onClick={() => inputRef.current?.click()} loading={uploading} disabled={uploading}>
            <FilePlus size={16} /> Add source
          </Button>
        </div>
      </div>

      <input
        ref={inputRef}
        type="file"
        multiple
        accept=".pdf,.doc,.docx,.txt,.md,.markdown,.csv,.json,.jsonl,.yaml,.yml,.xml,.html,.css,.js,.jsx,.ts,.tsx,.py,.sql,.log,text/*,application/pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        className="hidden"
        onChange={upload}
      />

      {error ? <div className="mb-4"><ErrorState message={error} /></div> : null}

      <div className="mb-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
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
        <Card padding="sm">
          <p className="label-mono">Needs attention</p>
          <p className="mt-1 text-2xl font-semibold text-warning">{stats.metadataOnly + stats.failed}</p>
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
            {query.trim() || results.length ? (
              <Button type="button" variant="ghost" onClick={clearSearch} className="w-full sm:w-auto">Clear</Button>
            ) : null}
          </form>
          {results.length ? (
            <div className="mt-4 space-y-2.5">
              {results.map((r) => (
                <div key={r.chunk_id} className="glass-tile p-3">
                  <div className="mb-1 flex flex-wrap items-center gap-2 text-[12px] text-content-subtle">
                    <Badge tone="primary">{r.document_title}</Badge>
                    <span>{r.document_filename}</span>
                    <span>chunk {r.chunk_index}</span>
                    <span>{Math.round(r.score * 100)}% match</span>
                  </div>
                  <p className="line-clamp-3 text-sm leading-relaxed text-content-muted">{r.content}</p>
                </div>
              ))}
            </div>
          ) : query.trim() && !loading ? (
            <p className="mt-3 text-[12px] text-content-subtle">Search indexed documents by keyword, title, or filename.</p>
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
            <UploadCloud size={24} className="mb-3 text-primary-bright" />
            <span className="text-sm font-medium text-content">{uploading ? uploadProgress ?? "Uploading..." : "Upload documents"}</span>
            <span className="mt-1 text-[12px] text-content-subtle">PDF, DOC, DOCX, text, and code can be uploaded together. If text extraction fails, the file is kept as metadata.</span>
          </button>
          <div className="mt-3 grid gap-2 text-[12px] text-content-muted sm:grid-cols-2">
            <div className="glass-tile px-3 py-2">
              <ShieldCheck size={14} className="mb-1 text-success-soft" />
              Secret-like text is protected from indexing.
            </div>
            <div className="glass-tile px-3 py-2">
              <Database size={14} className="mb-1 text-primary-bright" />
              {stats.metadataOnly} metadata-only files stored.
            </div>
          </div>
        </Card>
      </div>

      {setupNeeded ? (
        <SetupRequiredState feature="AI Knowledge" needs="backend" onRetry={load} />
      ) : !documents ? (
        <Loading />
      ) : documents.length === 0 ? (
        <EmptyState
          title="No knowledge documents"
          description="Upload an indexable document to make it available to AI Chat."
          icon={<BookOpenCheck size={20} />}
          action={<Button onClick={() => inputRef.current?.click()}><FilePlus size={16} /> Add source</Button>}
        />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {documents.map((doc, index) => {
            const metadataOnly = Boolean(doc.meta?.metadata_only || doc.status === "uploaded" || (doc.status === "indexed" && doc.chunk_count === 0));
            const tile = sourceTiles[index % sourceTiles.length];
            const TileIcon = tile.icon;
            return (
            <Card key={doc.id} className="flex flex-col" hover>
              <div className="mb-3 flex items-center justify-between gap-2">
                <span className={cn("flex h-[38px] w-[38px] shrink-0 items-center justify-center rounded-md", tile.tint)}>
                  <TileIcon size={18} />
                </span>
                <div className="flex min-w-0 flex-wrap items-center justify-end gap-1.5">
                  <Badge tone={statusTone(doc.status)} className="text-[10px] font-semibold capitalize">{doc.status}</Badge>
                  {doc.status === "indexed" && !metadataOnly ? (
                    <Badge tone="success" className="text-[10px] font-semibold">usable by AI</Badge>
                  ) : (
                    <Badge tone="warning" className="text-[10px] font-semibold">metadata only</Badge>
                  )}
                </div>
              </div>
              <p className="truncate text-sm font-semibold text-content">{doc.title}</p>
              <p className="mt-1 break-words text-[12px] leading-normal text-content-muted">
                {doc.filename} · {formatSize(doc.size_bytes)}
              </p>
              {doc.error_message ? <p className="mt-1 text-[12px] leading-normal text-warning">{doc.error_message}</p> : null}
              <p className="mt-3 font-mono text-[10.5px] text-content-subtle">
                {doc.chunk_count} chunks · {fileKind(doc.filename)}
                {doc.last_indexed_at ? ` · indexed ${formatDateTime(doc.last_indexed_at)}` : ""}
              </p>
              <div className="mt-4 flex items-center gap-1.5 border-t border-border/70 pt-3">
                {metadataOnly ? (
                  <span className="mr-auto inline-flex items-center gap-1 rounded-md border border-warning/25 bg-warning/10 px-2 py-1 text-[11px] text-warning">
                    <FileArchive size={12} /> Stored only
                  </span>
                ) : null}
                <Button variant="ghost" size="sm" onClick={() => reindex(doc)} loading={busyId === doc.id} disabled={busyId === doc.id} className={cn(!metadataOnly && "ml-auto")}>
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
            </Card>
            );
          })}
        </div>
      )}
    </AppShell>
  );
}
