"use client";

import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { CheckCircle2, ChevronDown, ChevronRight, ShieldAlert } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { Textarea } from "@/components/ui/Textarea";
import { useToast } from "@/components/ui/Toast";
import { aiApi, ApiException } from "@/lib/api";
import { cn, relativeTime } from "@/lib/format";
import type { ToolProposal } from "@/types";

const RISK_TONE: Record<string, "neutral" | "warning" | "danger"> = {
  LOW: "neutral",
  MEDIUM: "warning",
  HIGH: "danger",
};

type ActionNotice = {
  id: string;
  text: string;
  tone: "success" | "danger";
};

// "calendar_create_event" -> "Routine create event"
function humanizeTool(name: string): string {
  const spaced = name.replace(/^calendar[_-]/, "routine_").replace(/[_.-]+/g, " ").trim();
  return spaced ? spaced.charAt(0).toUpperCase() + spaced.slice(1) : name;
}

function formatRupiah(amount: unknown): string {
  const n = Number(amount);
  if (!Number.isFinite(n)) return String(amount ?? "");
  return "Rp" + Math.round(n).toLocaleString("id-ID");
}

/** A human-readable one-liner for a proposal — formatted for finance, JSON otherwise. */
function proposalSummary(toolName: string, payload: Record<string, unknown>): string {
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

function previewJson(value: unknown, max = 140): string {
  let text: string;
  try {
    text = JSON.stringify(value) || String(value);
  } catch {
    text = String(value);
  }
  return text.length > max ? `${text.slice(0, max)}...` : text;
}

function fmtDateTime(value: unknown): string {
  if (!value) return "";
  const d = new Date(String(value));
  if (Number.isNaN(d.getTime())) return String(value);
  return d.toLocaleString("id-ID", { dateStyle: "medium", timeStyle: "short" });
}

function truncate(text: string, max: number): string {
  return text.length > max ? `${text.slice(0, max)}...` : text;
}

/** One label:value line; renders nothing for empty values so cards stay tidy. */
function Field({ label, value }: { label: string; value: ReactNode }) {
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
 * event, task, and note each get structured fields instead of raw JSON. Anything
 * unrecognised falls back to the one-line summary. The exact payload is always still
 * available under the "Developer details" accordion (and editable via the JSON modal).
 */
function ProposalDetails({ toolName, payload }: { toolName: string; payload: Record<string, unknown> }) {
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

  // Unrecognised tool — keep the existing one-liner.
  return <p className="mt-1 text-[12px] text-content">{proposalSummary(toolName, payload)}</p>;
}

function omitKey<T>(map: Record<string, T>, key: string): Record<string, T> {
  const next = { ...map };
  delete next[key];
  return next;
}

/**
 * Collapsible list of PENDING tool proposals (AI-requested write actions).
 * Humans approve (executes via the Tool Registry), edit the JSON payload, or
 * reject. Nothing runs without explicit approval. Shows brief notices after a decision.
 */
export function PendingActionsPanel({ refreshKey }: { refreshKey: number }) {
  const toast = useToast();
  const [proposals, setProposals] = useState<ToolProposal[]>([]);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState<Record<string, "approve" | "reject">>({});
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [notices, setNotices] = useState<ActionNotice[]>([]);
  const [editing, setEditing] = useState<ToolProposal | null>(null);
  const [editText, setEditText] = useState("");
  const [editError, setEditError] = useState<string | null>(null);
  const [savingEdit, setSavingEdit] = useState(false);
  const timersRef = useRef<number[]>([]);
  const seenIdsRef = useRef<Set<string>>(new Set());

  const loadProposals = useCallback(async () => {
    try {
      const rows = await aiApi.listProposals();
      setProposals(rows);
      const nextIds = new Set(rows.map((p) => p.id));
      const hasNew = rows.some((p) => !seenIdsRef.current.has(p.id));
      if (rows.length > 0 && hasNew) setOpen(true);
      seenIdsRef.current = nextIds;
    } catch {
      /* non-blocking */
    }
  }, []);

  useEffect(() => {
    void loadProposals();
    const retry = window.setTimeout(() => void loadProposals(), 1200);
    const interval = window.setInterval(() => void loadProposals(), 12000); // 3.9 cross-device cadence
    return () => {
      window.clearTimeout(retry);
      window.clearInterval(interval);
    };
  }, [loadProposals, refreshKey]);

  useEffect(() => () => { timersRef.current.forEach((t) => window.clearTimeout(t)); }, []);

  const fail = (id: string, err: unknown, fallback: string) =>
    setErrors((cur) => ({ ...cur, [id]: err instanceof ApiException ? err.message : fallback }));

  const addNotice = (notice: ActionNotice) => {
    setNotices((cur) => [notice, ...cur].slice(0, 3));
    timersRef.current.push(window.setTimeout(() => {
      setNotices((cur) => cur.filter((x) => x.id !== notice.id));
    }, 3200));
  };

  const approve = async (p: ToolProposal) => {
    setBusy((cur) => ({ ...cur, [p.id]: "approve" }));
    setErrors((cur) => omitKey(cur, p.id));
    try {
      await aiApi.approveProposal(p.id);
      setProposals((cur) => cur.filter((x) => x.id !== p.id));
      addNotice({ id: `${p.id}-approved`, tone: "success", text: `${humanizeTool(p.tool_name)} approved and executed.` });
      toast.success("Action approved", `${humanizeTool(p.tool_name)} executed successfully.`);
    } catch (err) {
      const message = err instanceof ApiException ? err.message : "Approval failed.";
      fail(p.id, err, "Approval failed.");
      toast.danger("Approval failed", message);
    } finally {
      setBusy((cur) => omitKey(cur, p.id));
    }
  };

  const reject = async (p: ToolProposal) => {
    setBusy((cur) => ({ ...cur, [p.id]: "reject" }));
    setErrors((cur) => omitKey(cur, p.id));
    try {
      await aiApi.rejectProposal(p.id);
      setProposals((cur) => cur.filter((x) => x.id !== p.id));
      addNotice({ id: `${p.id}-rejected`, tone: "danger", text: `${humanizeTool(p.tool_name)} rejected.` });
      toast.info("Action rejected", humanizeTool(p.tool_name));
    } catch (err) {
      const message = err instanceof ApiException ? err.message : "Reject failed.";
      fail(p.id, err, "Reject failed.");
      toast.danger("Reject failed", message);
    } finally {
      setBusy((cur) => omitKey(cur, p.id));
    }
  };

  const openEdit = (p: ToolProposal) => {
    setEditing(p);
    setEditText(JSON.stringify(p.tool_payload ?? {}, null, 2));
    setEditError(null);
  };
  const closeEdit = () => {
    if (savingEdit) return;
    setEditing(null);
    setEditError(null);
  };
  const saveEdit = async () => {
    if (!editing) return;
    let payload: unknown;
    try {
      payload = JSON.parse(editText);
    } catch (err) {
      setEditError(`Invalid JSON: ${err instanceof Error ? err.message : "could not parse"}`);
      return;
    }
    if (typeof payload !== "object" || payload === null || Array.isArray(payload)) {
      setEditError("The payload must be a JSON object.");
      return;
    }
    setEditError(null);
    setSavingEdit(true);
    try {
      const updated = await aiApi.editProposal(editing.id, payload as Record<string, unknown>);
      setProposals((cur) => cur.map((x) => (x.id === updated.id ? updated : x)));
      setEditing(null);
      toast.success("Payload updated", "Review it once more, then approve when ready.");
    } catch (err) {
      const message = err instanceof ApiException ? err.message : "Could not save the payload.";
      setEditError(message);
      toast.danger("Edit failed", message);
    } finally {
      setSavingEdit(false);
    }
  };

  if (proposals.length === 0 && notices.length === 0) return null;

  return (
    <>
      {notices.length ? (
        <div className="mx-3 mb-1.5 space-y-1.5">
          {notices.map((notice) => (
            <div
              key={notice.id}
              className={cn(
                "flex items-center gap-2 rounded-lg border px-3 py-2 text-[12px]",
                notice.tone === "success"
                  ? "border-success/30 bg-success/10 text-success"
                  : "border-danger/30 bg-danger/10 text-danger",
              )}
            >
              <CheckCircle2 size={13} className="shrink-0" />
              <span className="min-w-0 truncate">{notice.text}</span>
            </div>
          ))}
        </div>
      ) : null}

      {proposals.length ? (
        <div className="mx-3 mb-2 animate-slide-up rounded-xl border border-warning/30 bg-warning/[0.07] shadow-panel">
          <button
            type="button"
            onClick={() => setOpen((o) => !o)}
            aria-expanded={open}
            className="flex w-full items-center gap-2 px-3 py-2 text-left"
          >
            {open ? <ChevronDown size={13} className="shrink-0 text-content-subtle" /> : <ChevronRight size={13} className="shrink-0 text-content-subtle" />}
            <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-sm bg-warning/[0.14] text-warning">
              <ShieldAlert size={14} />
            </span>
            <span className="text-[13px] font-semibold text-content">Tindakan tertunda</span>
            <Badge tone="warning">{proposals.length}</Badge>
            <span className="ml-auto hidden text-[11px] text-content-subtle sm:inline">Pending actions - approve before it runs.</span>
          </button>
          {open ? (
            <div className="custom-scrollbar max-h-56 space-y-2 overflow-y-auto border-t border-warning/20 px-3 py-2.5">
              {proposals.map((p) => {
                const action = busy[p.id];
                const risk = (p.risk_level || "").toUpperCase();
                return (
                  <div key={p.id} className="rounded-md border border-border bg-white/[0.03] px-3 py-2.5">
                    <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                      <span className="text-[13px] font-semibold text-content">{humanizeTool(p.tool_name)}</span>
                      <Badge tone={RISK_TONE[risk] ?? "neutral"}>{risk || "UNKNOWN"} risk</Badge>
                      {p.status && p.status !== "PENDING" ? (
                        <Badge tone="danger">{p.status === "NEEDS_EDIT" ? "Perlu diedit" : p.status}</Badge>
                      ) : null}
                      <span className="text-[11px] text-content-subtle">{relativeTime(p.created_at)}</span>
                    </div>
                    <ProposalDetails toolName={p.tool_name} payload={(p.tool_payload ?? {}) as Record<string, unknown>} />
                    <details className="mt-1.5">
                      <summary className="cursor-pointer list-none text-[11px] text-content-subtle hover:text-content">
                        Developer details (JSON)
                      </summary>
                      <pre className="custom-scrollbar mt-1 max-h-40 overflow-auto rounded-md bg-surface px-2 py-1.5 font-mono text-[11px] leading-snug text-content-muted">
                        {JSON.stringify(p.tool_payload ?? {}, null, 2)}
                      </pre>
                    </details>
                    {p.error_message ? (
                      <p className="mt-1 text-[11.5px] text-warning">Gagal: {p.error_message}</p>
                    ) : null}
                    {errors[p.id] ? <p className="mt-1.5 text-[11.5px] text-danger">{errors[p.id]}</p> : null}
                    <div className="mt-2 flex flex-wrap items-center gap-2">
                      <Button size="sm" loading={action === "approve"} disabled={Boolean(action)} onClick={() => void approve(p)}>
                        Approve
                      </Button>
                      <Button size="sm" variant="ghost" disabled={Boolean(action)} onClick={() => openEdit(p)}>
                        Edit
                      </Button>
                      <Button size="sm" variant="danger" loading={action === "reject"} disabled={Boolean(action)} onClick={() => void reject(p)}>
                        Reject
                      </Button>
                    </div>
                  </div>
                );
              })}
            </div>
          ) : null}
        </div>
      ) : null}

      <Modal
        open={editing !== null}
        onClose={closeEdit}
        title="Edit proposed action"
        description={editing ? `${humanizeTool(editing.tool_name)} - adjust the payload, then approve it to run.` : undefined}
        footer={
          <>
            <Button variant="ghost" onClick={closeEdit} disabled={savingEdit}>
              Cancel
            </Button>
            <Button onClick={() => void saveEdit()} loading={savingEdit}>
              Save payload
            </Button>
          </>
        }
      >
        <Textarea
          label="Tool payload (JSON)"
          value={editText}
          onChange={(e) => setEditText(e.target.value)}
          rows={10}
          spellCheck={false}
          className="font-mono text-[12.5px]"
        />
        {editError ? <p className="mt-2 text-[12px] text-danger">{editError}</p> : null}
      </Modal>
    </>
  );
}
