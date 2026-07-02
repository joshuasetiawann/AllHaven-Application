"use client";

import type { ReactNode } from "react";

export function formatRupiah(amount: unknown): string {
  const n = Number(amount);
  if (!Number.isFinite(n)) return String(amount ?? "");
  return "Rp" + Math.round(n).toLocaleString("id-ID");
}

export function previewJson(value: unknown, max = 140): string {
  let text: string;
  try {
    text = JSON.stringify(value) || String(value);
  } catch {
    text = String(value);
  }
  return text.length > max ? `${text.slice(0, max)}...` : text;
}

/** A human-readable one-liner for a proposal — formatted for finance, JSON otherwise. */
export function proposalSummary(toolName: string, payload: Record<string, unknown>): string {
  if (toolName.startsWith("create_transaction")) {
    const label = String(payload.type).toUpperCase() === "INCOME" ? "Pendapatan" : "Pengeluaran";
    const parts = [`${label} ${formatRupiah(payload.amount)}`];
    if (payload.description) parts.push(`untuk ${payload.description}`);
    if (payload.transaction_date) parts.push(`(${payload.transaction_date})`);
    return parts.join(" ");
  }
  if (payload.title) return String(payload.title);
  return previewJson(payload);
}

export function fmtDateTime(value: unknown): string {
  if (!value) return "";
  const d = new Date(String(value));
  if (Number.isNaN(d.getTime())) return String(value);
  return d.toLocaleString("id-ID", { dateStyle: "medium", timeStyle: "short" });
}

export function truncate(text: string, max: number): string {
  return text.length > max ? `${text.slice(0, max)}...` : text;
}

/** One label:value line; renders nothing for empty values so cards stay tidy. */
export function Field({ label, value }: { label: string; value: ReactNode }) {
  if (value === null || value === undefined || value === "") return null;
  return (
    <div className="flex gap-2 text-[12px] leading-snug">
      {label ? <span className="shrink-0 text-content-subtle">{label}</span> : null}
      <span className="min-w-0 break-words text-content">{value}</span>
    </div>
  );
}

/**
 * Typed, human-readable details for a proposal — finance, routine schedule, single
 * event, task, note, and deletions each get structured fields instead of raw JSON.
 * Anything unrecognised falls back to the one-line summary. The exact payload stays
 * available wherever the caller exposes it (developer accordion / JSON edit modal).
 */
export function ProposalDetails({ toolName, payload }: { toolName: string; payload: Record<string, unknown> }) {
  if (toolName.startsWith("create_transaction")) {
    const income = String(payload.type).toUpperCase() === "INCOME";
    return (
      <div className="mt-1 space-y-0.5">
        <Field label="Jenis" value={income ? "Pendapatan" : "Pengeluaran"} />
        <Field label="Jumlah" value={<span className={income ? "text-success" : "text-content"}>{formatRupiah(payload.amount)}</span>} />
        <Field label="Untuk" value={payload.description as string} />
        <Field label="Tanggal" value={payload.transaction_date as string} />
      </div>
    );
  }

  if (toolName === "create_routine_schedule") {
    const blocks = Array.isArray(payload.blocks) ? (payload.blocks as Record<string, unknown>[]) : [];
    const days = Number(payload.repeat_days) || 7;
    return (
      <div className="mt-1 space-y-0.5">
        <Field label="Jadwal" value={`${blocks.length} kegiatan × ${days} hari`} />
        <Field label="Mulai" value={(payload.start_date as string) || "hari ini"} />
        {blocks.slice(0, 6).map((b, i) => (
          <Field key={i} label={String(b.start_time ?? "--:--")} value={`${b.title ?? "Kegiatan"} · ${b.duration_min ?? 60}m`} />
        ))}
        {blocks.length > 6 ? <Field label="" value={`+${blocks.length - 6} kegiatan lagi`} /> : null}
      </div>
    );
  }

  if (toolName === "create_event" || toolName === "create_routine"
      || toolName.startsWith("calendar_") || toolName.startsWith("update_event")) {
    return (
      <div className="mt-1 space-y-0.5">
        <Field label="Judul" value={payload.title as string} />
        <Field label="Mulai" value={fmtDateTime(payload.start_at)} />
        <Field label="Selesai" value={fmtDateTime(payload.end_at)} />
        <Field label="Lokasi" value={payload.location as string} />
      </div>
    );
  }

  if (toolName.startsWith("create_task") || toolName.startsWith("update_task")) {
    const checklist = Array.isArray(payload.checklist) ? payload.checklist.length : 0;
    return (
      <div className="mt-1 space-y-0.5">
        <Field label="Tugas" value={payload.title as string} />
        <Field label="Prioritas" value={payload.priority as string} />
        <Field label="Tenggat" value={(payload.due_date as string) ?? (payload.due_at as string)} />
        {checklist ? <Field label="Checklist" value={`${checklist} item`} /> : null}
      </div>
    );
  }

  if (toolName.startsWith("create_note") || toolName.startsWith("update_note")) {
    return (
      <div className="mt-1 space-y-0.5">
        <Field label="Catatan" value={payload.title as string} />
        <Field label="Isi" value={truncate(String(payload.content ?? ""), 160)} />
      </div>
    );
  }

  // Deletions (delete_task, delete_note, delete_event, delete_transaction,
  // delete_memory, delete_file, ...) — show what is being removed, plainly.
  if (toolName.startsWith("delete_")) {
    const target = payload.title ?? payload.description ?? payload.id;
    if (target !== null && target !== undefined && target !== "") {
      return (
        <div className="mt-1 space-y-0.5">
          <Field label="Hapus" value={String(target)} />
        </div>
      );
    }
    // No identifiable target — fall through to the one-line summary.
  }

  // Unrecognised tool — keep the existing one-liner.
  return <p className="mt-1 text-[12px] text-content">{proposalSummary(toolName, payload)}</p>;
}
