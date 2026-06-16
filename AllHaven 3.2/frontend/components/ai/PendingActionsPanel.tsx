"use client";

import { useCallback, useEffect, useRef, useState } from "react";
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

// "calendar_create_event" -> "Calendar create event"
function humanizeTool(name: string): string {
  const spaced = name.replace(/[_.-]+/g, " ").trim();
  return spaced ? spaced.charAt(0).toUpperCase() + spaced.slice(1) : name;
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
    const interval = window.setInterval(() => void loadProposals(), 7000);
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
        <div className="mx-3 mb-2 animate-slide-up rounded-xl border border-warning/45 bg-warning/10 shadow-glow">
          <button
            type="button"
            onClick={() => setOpen((o) => !o)}
            aria-expanded={open}
            className="flex w-full items-center gap-2 px-3 py-2 text-left"
          >
            {open ? <ChevronDown size={13} className="shrink-0 text-content-subtle" /> : <ChevronRight size={13} className="shrink-0 text-content-subtle" />}
            <ShieldAlert size={13} className="shrink-0 text-warning" />
            <span className="text-[12.5px] font-medium text-content">Tindakan tertunda</span>
            <Badge tone="warning">{proposals.length}</Badge>
            <span className="ml-auto hidden text-[11px] text-content-subtle sm:inline">Pending actions - approve before it runs.</span>
          </button>
          {open ? (
            <div className="custom-scrollbar max-h-56 space-y-2 overflow-y-auto border-t border-warning/20 px-3 py-2.5">
              {proposals.map((p) => {
                const action = busy[p.id];
                const risk = (p.risk_level || "").toUpperCase();
                return (
                  <div key={p.id} className="rounded-lg border border-border bg-surface-input px-3 py-2.5">
                    <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                      <span className="text-[13px] font-medium text-content">{humanizeTool(p.tool_name)}</span>
                      <Badge tone={RISK_TONE[risk] ?? "neutral"}>{risk || "UNKNOWN"} risk</Badge>
                      <span className="text-[11px] text-content-subtle">{relativeTime(p.created_at)}</span>
                    </div>
                    <p className="mt-1 truncate font-mono text-[11px] text-content-muted" title={previewJson(p.tool_payload, 2000)}>
                      {previewJson(p.tool_payload)}
                    </p>
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
