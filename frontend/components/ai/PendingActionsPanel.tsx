"use client";

import { useEffect, useRef, useState } from "react";
import { CheckCircle2, ChevronDown, ChevronRight, ShieldAlert } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { Textarea } from "@/components/ui/Textarea";
import { aiApi, ApiException } from "@/lib/api";
import { cn, relativeTime } from "@/lib/format";
import type { ToolProposal } from "@/types";

const RISK_TONE: Record<string, "neutral" | "warning" | "danger"> = {
  LOW: "neutral",
  MEDIUM: "warning",
  HIGH: "danger",
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
  return text.length > max ? `${text.slice(0, max)}…` : text;
}

function omitKey<T>(map: Record<string, T>, key: string): Record<string, T> {
  const next = { ...map };
  delete next[key];
  return next;
}

/**
 * Collapsible list of PENDING tool proposals (AI-requested write actions).
 * Humans approve (executes via the Tool Registry), edit the JSON payload, or
 * reject — nothing runs without explicit approval. Hidden entirely when empty.
 */
export function PendingActionsPanel({ refreshKey }: { refreshKey: number }) {
  const [proposals, setProposals] = useState<ToolProposal[]>([]);
  const [open, setOpen] = useState(true);
  const [busy, setBusy] = useState<Record<string, "approve" | "reject">>({});
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [executed, setExecuted] = useState<Record<string, Record<string, unknown>>>({});
  const [editing, setEditing] = useState<ToolProposal | null>(null);
  const [editText, setEditText] = useState("");
  const [editError, setEditError] = useState<string | null>(null);
  const [savingEdit, setSavingEdit] = useState(false);
  const timersRef = useRef<number[]>([]);

  useEffect(() => {
    let on = true;
    aiApi.listProposals().then((p) => on && setProposals(p)).catch(() => { /* non-blocking */ });
    return () => { on = false; };
  }, [refreshKey]);

  useEffect(() => () => { timersRef.current.forEach((t) => window.clearTimeout(t)); }, []);

  const fail = (id: string, err: unknown, fallback: string) =>
    setErrors((cur) => ({ ...cur, [id]: err instanceof ApiException ? err.message : fallback }));

  const approve = async (p: ToolProposal) => {
    setBusy((cur) => ({ ...cur, [p.id]: "approve" }));
    setErrors((cur) => omitKey(cur, p.id));
    try {
      const res = await aiApi.approveProposal(p.id);
      // Show the execution result briefly, then drop the item from the list.
      setExecuted((cur) => ({ ...cur, [p.id]: res.result }));
      timersRef.current.push(window.setTimeout(() => {
        setProposals((cur) => cur.filter((x) => x.id !== p.id));
        setExecuted((cur) => omitKey(cur, p.id));
      }, 5000));
    } catch (err) {
      fail(p.id, err, "Approval failed.");
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
    } catch (err) {
      fail(p.id, err, "Reject failed.");
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
    } catch (err) {
      setEditError(err instanceof ApiException ? err.message : "Could not save the payload.");
    } finally {
      setSavingEdit(false);
    }
  };

  if (proposals.length === 0) return null;

  return (
    <>
      <div className="mx-3 mb-1.5 animate-slide-up rounded-xl border border-warning/30 bg-warning/5">
        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          aria-expanded={open}
          className="flex w-full items-center gap-2 px-3 py-2 text-left"
        >
          {open ? <ChevronDown size={13} className="shrink-0 text-content-subtle" /> : <ChevronRight size={13} className="shrink-0 text-content-subtle" />}
          <ShieldAlert size={13} className="shrink-0 text-warning" />
          <span className="text-[12.5px] font-medium text-content">Pending actions</span>
          <Badge tone="warning">{proposals.length}</Badge>
          <span className="ml-auto hidden text-[11px] text-content-subtle sm:inline">AI-proposed writes — nothing runs until you approve.</span>
        </button>
        {open ? (
          <div className="space-y-2 border-t border-warning/20 px-3 py-2.5">
            {proposals.map((p) => {
              const result = executed[p.id];
              const action = busy[p.id];
              const risk = (p.risk_level || "").toUpperCase();
              return (
                <div
                  key={p.id}
                  className={cn("rounded-lg border px-3 py-2.5", result ? "border-success/30 bg-success/5" : "border-border bg-surface-input")}
                >
                  <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                    <span className="text-[13px] font-medium text-content">{humanizeTool(p.tool_name)}</span>
                    <Badge tone={RISK_TONE[risk] ?? "neutral"}>{risk || "UNKNOWN"} risk</Badge>
                    <span className="text-[11px] text-content-subtle">{relativeTime(p.created_at)}</span>
                  </div>
                  <p className="mt-1 truncate font-mono text-[11px] text-content-muted" title={previewJson(p.tool_payload, 2000)}>
                    {previewJson(p.tool_payload)}
                  </p>
                  {result ? (
                    <p className="mt-1.5 flex items-start gap-1.5 break-all text-[11.5px] text-success">
                      <CheckCircle2 size={12} className="mt-0.5 shrink-0" /> Executed — {previewJson(result, 200)}
                    </p>
                  ) : (
                    <>
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
                    </>
                  )}
                </div>
              );
            })}
          </div>
        ) : null}
      </div>

      <Modal
        open={editing !== null}
        onClose={closeEdit}
        title="Edit proposed action"
        description={editing ? `${humanizeTool(editing.tool_name)} — adjust the payload, then approve it to run.` : undefined}
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
