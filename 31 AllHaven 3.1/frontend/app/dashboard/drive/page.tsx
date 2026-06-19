"use client";

import { useEffect, useRef, useState } from "react";
import { Download, FileText, FolderOpen, Trash2, UploadCloud } from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { PageHeader } from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState, ErrorState, Loading } from "@/components/ui/States";
import { driveApi, ApiException } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import type { DriveConfig, DriveFile } from "@/types";

function formatSize(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  const i = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  const value = bytes / Math.pow(1024, i);
  return `${value.toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
}

export default function DrivePage() {
  const [files, setFiles] = useState<DriveFile[] | null>(null);
  const [config, setConfig] = useState<DriveConfig | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const load = async () => {
    setError(null);
    try {
      const [cfg, rows] = await Promise.all([driveApi.config(), driveApi.list()]);
      setConfig(cfg);
      setFiles(rows);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load files.");
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const handleUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    if (config && file.size > config.max_upload_bytes) {
      setActionError(`File exceeds the configured ${config.max_upload_mb} MB limit.`);
      if (inputRef.current) inputRef.current.value = "";
      return;
    }
    setUploading(true);
    setActionError(null);
    try {
      await driveApi.upload(file);
      await load();
    } catch (err) {
      setActionError(err instanceof ApiException ? err.message : "Upload failed.");
    } finally {
      setUploading(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  };

  const handleDownload = async (file: DriveFile) => {
    setActionError(null);
    setBusyId(file.id);
    try {
      const res = await fetch(driveApi.downloadUrl(file.id), { credentials: "include" });
      if (!res.ok) throw new ApiException(`Download failed (${res.status})`, "HTTP_ERROR", res.status);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = file.filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      setActionError(
        err instanceof ApiException ? err.message : "Could not download this file.",
      );
    } finally {
      setBusyId(null);
    }
  };

  const handleDelete = async (file: DriveFile) => {
    setActionError(null);
    setBusyId(file.id);
    setFiles((prev) => prev?.filter((f) => f.id !== file.id) ?? prev);
    try {
      await driveApi.remove(file.id);
    } catch (err) {
      setActionError(err instanceof ApiException ? err.message : "Could not delete this file.");
      void load();
    } finally {
      setBusyId(null);
    }
  };

  return (
    <AppShell>
      <PageHeader
        title="Drive"
        subtitle="Workspace file storage — upload, download, and manage your files."
        actions={
          <Button onClick={() => inputRef.current?.click()} loading={uploading} disabled={uploading}>
            <UploadCloud size={16} /> Upload file
          </Button>
        }
      />

      <input ref={inputRef} type="file" className="hidden" onChange={handleUpload} />

      <Card className="mb-5">
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          disabled={uploading}
          className="flex w-full flex-col items-center justify-center rounded-xl border border-dashed border-border px-6 py-10 text-center transition-colors hover:border-primary/50 hover:bg-surface-raised/40 disabled:cursor-not-allowed disabled:opacity-60"
        >
          <span className="mb-3 flex h-12 w-12 items-center justify-center rounded-xl border border-border bg-surface-input text-primary">
            <UploadCloud size={22} />
          </span>
          <p className="text-sm font-medium text-content">
            {uploading ? "Uploading…" : "Click to upload a file"}
          </p>
          <p className="mt-1 max-w-sm text-[13px] text-content-muted">
            Current upload limit: {config ? `${config.max_upload_mb} MB` : "loading..."}.
          </p>
        </button>
      </Card>

      {actionError ? (
        <div className="mb-4">
          <ErrorState message={actionError} />
        </div>
      ) : null}

      {error ? (
        <ErrorState message={error} onRetry={load} />
      ) : !files ? (
        <Loading />
      ) : files.length === 0 ? (
        <EmptyState
          title="No files yet"
          description="Upload your first file to get started."
          icon={<FolderOpen size={20} />}
          action={
            <Button onClick={() => inputRef.current?.click()}>
              <UploadCloud size={16} /> Upload file
            </Button>
          }
        />
      ) : (
        <div className="space-y-2.5">
          {files.map((file) => (
            <Card key={file.id} className="p-4" hover>
              <div className="flex items-center justify-between gap-3">
                <div className="flex min-w-0 items-center gap-3">
                  <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-border bg-surface-input text-primary">
                    <FileText size={18} />
                  </span>
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-content">{file.filename}</p>
                    <p className="mt-0.5 text-[12px] text-content-subtle">
                      {formatSize(file.size_bytes)} · {formatDateTime(file.created_at)}
                    </p>
                  </div>
                </div>
                <div className="flex shrink-0 items-center gap-1.5">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleDownload(file)}
                    loading={busyId === file.id}
                    disabled={busyId === file.id}
                  >
                    <Download size={14} /> Download
                  </Button>
                  <button
                    onClick={() => handleDelete(file)}
                    disabled={busyId === file.id}
                    className="rounded-md p-2 text-content-subtle transition-colors hover:text-danger disabled:opacity-50"
                    aria-label="Delete file"
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
