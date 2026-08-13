"use client";

import { useEffect, useRef, useState } from "react";
import {
  Download,
  FileArchive,
  FileText,
  FolderOpen,
  HardDrive,
  Image as ImageIcon,
  Trash2,
  Upload,
  UploadCloud,
} from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState, ErrorState, Loading } from "@/components/ui/States";
import { SetupRequiredState } from "@/components/SetupRequiredState";
import { isBackendUnreachable } from "@/lib/connection";
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

const IMAGE_EXTS = ["png", "jpg", "jpeg", "gif", "webp", "svg", "bmp", "avif"];
const ARCHIVE_EXTS = ["zip", "rar", "7z", "tar", "gz", "bz2", "xz"];

function fileVisual(filename: string): { icon: typeof FileText; tile: string } {
  const ext = filename.split(".").pop()?.toLowerCase() ?? "";
  if (IMAGE_EXTS.includes(ext)) {
    return { icon: ImageIcon, tile: "bg-danger/10 text-danger" };
  }
  if (ARCHIVE_EXTS.includes(ext)) {
    return { icon: FileArchive, tile: "bg-secondary/15 text-secondary-soft" };
  }
  if (ext === "pdf" || ext === "doc" || ext === "docx" || ext === "md" || ext === "txt") {
    return { icon: FileText, tile: "bg-success/10 text-success-soft" };
  }
  return { icon: FileText, tile: "bg-primary-dim/10 text-primary" };
}

export default function DrivePage() {
  const [files, setFiles] = useState<DriveFile[] | null>(null);
  const [config, setConfig] = useState<DriveConfig | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const [setupNeeded, setSetupNeeded] = useState(false);
  const load = async () => {
    setError(null);
    setSetupNeeded(false);
    try {
      const [cfg, rows] = await Promise.all([driveApi.config(), driveApi.list()]);
      setConfig(cfg);
      setFiles(rows);
    } catch (err) {
      if (isBackendUnreachable(err)) setSetupNeeded(true);
      else setError(err instanceof Error ? err.message : "Failed to load files.");
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
      const blob = await driveApi.download(file.id);
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

  const usedBytes = files?.reduce((sum, f) => sum + (f.size_bytes || 0), 0) ?? 0;

  return (
    <AppShell>
      {/* Header */}
      <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div className="min-w-0">
          <div className="flex items-center gap-2.5">
            <h1 className="text-2xl font-semibold tracking-[-0.02em] text-content sm:text-[30px]">
              Drive
            </h1>
            <Badge tone="warning" className="text-[10.5px] font-semibold">
              MVP
            </Badge>
          </div>
          <p className="mt-2 max-w-2xl text-[13.5px] leading-relaxed text-content-muted">
            Secure file vault, synced across your devices.
          </p>
        </div>
        <div className="flex w-full flex-wrap items-center gap-2 sm:w-auto sm:justify-end">
          <Button onClick={() => inputRef.current?.click()} loading={uploading} disabled={uploading}>
            <Upload size={16} /> Upload
          </Button>
        </div>
      </div>

      <input ref={inputRef} type="file" className="hidden" onChange={handleUpload} />

      {/* Storage strip */}
      <div className="panel mb-5 flex flex-wrap items-center gap-4 px-5 py-[18px]">
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-primary-dim/10 text-primary">
          <HardDrive size={19} />
        </span>
        <div className="min-w-[200px] flex-1">
          <div className="mb-2 flex items-baseline justify-between gap-3">
            <span className="text-[13px] text-content">
              {files ? `${formatSize(usedBytes)} used` : "Calculating storage…"}
            </span>
            <span className="text-[13px] text-content-subtle">
              {config ? `up to ${config.max_upload_mb} MB per upload` : "loading limit…"}
            </span>
          </div>
          <div className="h-2 rounded-full bg-white/[0.08]">
            <div
              className="h-2 rounded-full grad-primary shadow-glow-primary transition-all duration-500"
              style={{
                width: files && files.length > 0 ? "100%" : "0%",
                opacity: files && files.length > 0 ? 0.9 : 0,
              }}
            />
          </div>
        </div>
        <div className="flex gap-4">
          <span className="text-[12.5px] text-content-muted">
            <span className="font-semibold text-primary">{files ? files.length : "—"}</span> files
          </span>
        </div>
      </div>

      {/* Upload dropzone */}
      <Card className="mb-5">
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          disabled={uploading}
          className="flex w-full flex-col items-center justify-center rounded-xl border border-dashed border-border-strong bg-white/[0.015] px-6 py-10 text-center transition-colors hover:border-primary-dim/50 hover:bg-primary-dim/[0.05] disabled:cursor-not-allowed disabled:opacity-60"
        >
          <span className="mb-3.5 flex h-12 w-12 items-center justify-center rounded-md grad-primary text-primary-fg shadow-btn-primary">
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

      {setupNeeded ? (
        <SetupRequiredState feature="Drive" needs="backend" onRetry={load} />
      ) : error ? (
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
        <div className="grid grid-cols-1 gap-3.5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {files.map((file) => {
            const { icon: Icon, tile } = fileVisual(file.filename);
            return (
              <div
                key={file.id}
                className="glass-tile group flex flex-col p-[18px] transition-colors hover:border-primary-dim/30 hover:bg-white/[0.05]"
              >
                <div className="mb-3.5 flex items-start justify-between gap-2">
                  <span
                    className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-md ${tile}`}
                  >
                    <Icon size={22} />
                  </span>
                  <button
                    onClick={() => handleDelete(file)}
                    disabled={busyId === file.id}
                    className="rounded-md p-2 text-content-faint transition-colors hover:bg-danger/10 hover:text-danger disabled:opacity-50"
                    aria-label="Delete file"
                  >
                    <Trash2 size={15} />
                  </button>
                </div>
                <p className="truncate text-[13.5px] font-medium text-content" title={file.filename}>
                  {file.filename}
                </p>
                <p className="mt-1 text-[11.5px] text-content-subtle">
                  {formatSize(file.size_bytes)} · {formatDateTime(file.created_at)}
                </p>
                <div className="mt-3.5 border-t border-white/[0.07] pt-3">
                  <Button
                    variant="ghost"
                    size="sm"
                    className="w-full"
                    onClick={() => handleDownload(file)}
                    loading={busyId === file.id}
                    disabled={busyId === file.id}
                  >
                    <Download size={14} /> Download
                  </Button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </AppShell>
  );
}
