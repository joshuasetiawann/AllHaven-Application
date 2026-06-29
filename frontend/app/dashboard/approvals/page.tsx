"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import Link from "next/link";
import {
  Bot,
  Brain,
  CheckCircle2,
  ClipboardCheck,
  Clock,
  Pencil,
  RefreshCw,
  Send,
  ShieldAlert,
  Trash2,
  Wallet,
  Wrench,
  XCircle,
} from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState, ErrorState, Loading } from "@/components/ui/States";
import { Modal } from "@/components/ui/Modal";
import { Textarea } from "@/components/ui/Textarea";
import { useToast } from "@/components/ui/Toast";
import { aiApi, ApiException, memoryApi } from "@/lib/api";
import { cn, relativeTime } from "@/lib/format";
import type { AiMemory, MemorySuggestion, ToolProposal } from "@/types";
import {
  isTransactionTool,
  todayIso,
  TransactionEditForm,
  TransactionSummary,
  transactionPayloadErrors,
} from "@/components/approvals/TransactionProposal";

const RISK_TONE: Record<string, "neutral" | "warning" | "danger"> = {
  LOW: "neutral",
  MEDIUM: "warning",
  HIGH: "danger",
};

/* Risk-tinted approval card — High = red border/wash, Medium = amber, Low = plain glass. */
const RISK_CARD: Record<string, string> = {
  HIGH: "border-danger/30 bg-[linear-gradient(135deg,rgb(var(--color-danger)/0.07),rgb(var(--color-danger)/0.015)_60%)]",
  MEDIUM:
    "border-warning/25 bg-[linear-gradient(135deg,rgb(var(--color-warning)/0.06),rgb(var(--color-warning)/0.012)_60%)]",
};

const RISK_TILE: Record<string, string> = {
  HIGH: "border-danger/30 bg-danger/10 text-danger",
  MEDIUM: "border-warning/30 bg-warning/10 text-warning",
};

/** Presentational glyph for the risk tile, picked from the tool name. */
function toolIcon(name: string) {
  const n = name.toLowerCase();
  if (isTransactionTool(name)) return Wallet;
  if (n.includes("delete") || n.includes("remove")) return Trash2;
  if (n.includes("send") || n.includes("email") || n.includes("invoice")) return Send;
  if (n.includes("memory")) return Brain;
  return Wrench;
}

function humanizeTool(name: string): string {
  const spaced = name.replace(/[_.-]+/g, " ").trim();
  return spaced ? spaced.charAt(0).toUpperCase() + spaced.slice(1) : name;
}

function previewJson(value: unknown, max = 220): string {
  let text: string;
  try {
    text = JSON.stringify(value) || String(value);
  } catch {
    text = String(value);
  }
  return text.length > max ? `${text.slice(0, max)}...` : text;
}

/** Mono provenance chip (agent / tool / relative time). */
function ProvenanceChip({ icon, children }: { icon: ReactNode; children: ReactNode }) {
  return (
    <span className="inline-flex min-w-0 items-center gap-1.5 rounded-sm border border-border bg-surface-input/60 px-2 py-1 font-mono text-[10.5px] text-content-muted">
      <span className="shrink-0">{icon}</span>
      <span className="min-w-0 truncate">{children}</span>
    </span>
  );
}

/** Small section eyebrow above each approval column. */
function SectionHeading({
  icon,
  title,
  meta,
}: {
  icon: ReactNode;
  title: string;
  meta: string;
}) {
  return (
    <div className="flex min-w-0 items-center gap-2.5">
      <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-primary/20 bg-primary/10 text-primary-bright">
        {icon}
      </span>
      <h2 className="truncate text-[15px] font-semibold text-content">{title}</h2>
      <span className="ml-auto shrink-0 font-mono text-[10.5px] uppercase tracking-[0.12em] text-content-faint">
        {meta}
      </span>
    </div>
  );
}

export default function ApprovalsPage() {
  const toast = useToast();
  const [proposals, setProposals] = useState<ToolProposal[]>([]);
  const [suggestions, setSuggestions] = useState<MemorySuggestion[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [editing, setEditing] = useState<ToolProposal | null>(null);
  const [editText, setEditText] = useState("");
  const [editPayload, setEditPayload] = useState<Record<string, unknown> | null>(null);
  const [editError, setEditError] = useState<string | null>(null);
  // Per-proposal inline approval errors — one message each, instead of stacking toasts.
  const [cardErrors, setCardErrors] = useState<Record<string, string>>({});

  const load = useCallback(async () => {
    setError(null);
    try {
      const [proposalRows, suggestionRows] = await Promise.all([
        aiApi.listProposals(),
        memoryApi.listSuggestions(),
      ]);
      setProposals(proposalRows);
      setSuggestions(suggestionRows);
    } catch (err) {
      setError(err instanceof ApiException ? err.message : "Failed to load approvals.");
    } finally {
      setLoading(false);
    }
  }, []);

  // Poll every 12s + refetch when the tab regains focus, so an approval made on
  // another device (or by the AI mid-session) appears/clears here without a manual
  // refresh — and a proposal approved elsewhere converges within ~12s (3.9 cross-device).
  useEffect(() => {
    void load();
    const interval = window.setInterval(() => void load(), 12000);
    const onVisible = () => {
      if (document.visibilityState === "visible") void load();
    };
    document.addEventListener("visibilitychange", onVisible);
    window.addEventListener("focus", onVisible);
    return () => {
      window.clearInterval(interval);
      document.removeEventListener("visibilitychange", onVisible);
      window.removeEventListener("focus", onVisible);
    };
  }, [load]);

  const totals = useMemo(() => ({
    all: proposals.length + suggestions.length,
    actions: proposals.length,
    memories: suggestions.length,
    highRisk: proposals.filter((p) => p.risk_level === "HIGH").length,
  }), [proposals, suggestions]);

  const clearCardError = (id: string) =>
    setCardErrors((cur) => {
      if (!(id in cur)) return cur;
      const next = { ...cur };
      delete next[id];
      return next;
    });

  const approveProposal = async (proposal: ToolProposal) => {
    // Block client-side when required fields are invalid: one clear message,
    // nothing sent for execution, proposal stays editable.
    if (isTransactionTool(proposal.tool_name)) {
      const issues = transactionPayloadErrors(proposal.tool_payload);
      if (issues.length > 0) {
        setCardErrors((cur) => ({ ...cur, [proposal.id]: issues.join(" ") }));
        return;
      }
    }
    setBusyId(proposal.id);
    clearCardError(proposal.id);
    try {
      await aiApi.approveProposal(proposal.id);
      setProposals((cur) => cur.filter((p) => p.id !== proposal.id));
      toast.success("Change approved", `${humanizeTool(proposal.tool_name)} executed.`);
    } catch (err) {
      const message = err instanceof ApiException ? err.message : "Approval failed.";
      // Inline, per-card — keeps the proposal visible/editable and never stacks
      // the same toast when the user retries.
      setCardErrors((cur) => ({ ...cur, [proposal.id]: message }));
    } finally {
      setBusyId(null);
    }
  };

  const rejectProposal = async (proposal: ToolProposal) => {
    setBusyId(proposal.id);
    setError(null);
    try {
      await aiApi.rejectProposal(proposal.id);
      setProposals((cur) => cur.filter((p) => p.id !== proposal.id));
      toast.info("Change rejected", humanizeTool(proposal.tool_name));
    } catch (err) {
      const message = err instanceof ApiException ? err.message : "Reject failed.";
      setError(message);
      toast.danger("Reject failed", message);
    } finally {
      setBusyId(null);
    }
  };

  const openEdit = (proposal: ToolProposal) => {
    setEditing(proposal);
    setEditError(null);
    if (isTransactionTool(proposal.tool_name)) {
      const payload = { ...(proposal.tool_payload ?? {}) };
      if (!String(payload.transaction_date ?? "").trim()) payload.transaction_date = todayIso();
      setEditPayload(payload);
    } else {
      setEditPayload(null);
      setEditText(JSON.stringify(proposal.tool_payload ?? {}, null, 2));
    }
  };

  const closeEdit = () => {
    setEditing(null);
    setEditPayload(null);
    setEditError(null);
  };

  const saveEdit = async () => {
    if (!editing) return;
    let payload: Record<string, unknown>;
    if (isTransactionTool(editing.tool_name)) {
      payload = editPayload ?? {};
      const issues = transactionPayloadErrors(payload);
      if (issues.length > 0) {
        setEditError(issues.join(" "));
        return;
      }
    } else {
      let parsed: unknown;
      try {
        parsed = JSON.parse(editText);
      } catch (err) {
        setEditError(`Invalid JSON: ${err instanceof Error ? err.message : "could not parse"}`);
        return;
      }
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
        setEditError("Payload must be a JSON object.");
        return;
      }
      payload = parsed as Record<string, unknown>;
    }
    setBusyId(editing.id);
    try {
      const updated = await aiApi.editProposal(editing.id, payload);
      setProposals((cur) => cur.map((p) => (p.id === updated.id ? updated : p)));
      clearCardError(updated.id);
      closeEdit();
      toast.success("Payload updated", "Review it, then approve when ready.");
    } catch (err) {
      const message = err instanceof ApiException ? err.message : "Could not save payload.";
      setEditError(message);
    } finally {
      setBusyId(null);
    }
  };

  const approveSuggestion = async (suggestion: MemorySuggestion) => {
    setBusyId(suggestion.id);
    setError(null);
    try {
      const memory: AiMemory = await memoryApi.approveSuggestion(suggestion.id);
      setSuggestions((cur) => cur.filter((s) => s.id !== suggestion.id));
      toast.success("Memory approved", memory.title);
    } catch (err) {
      const message = err instanceof ApiException ? err.message : "Memory approval failed.";
      setError(message);
      toast.danger("Approval failed", message);
    } finally {
      setBusyId(null);
    }
  };

  const rejectSuggestion = async (suggestion: MemorySuggestion) => {
    setBusyId(suggestion.id);
    setError(null);
    try {
      await memoryApi.rejectSuggestion(suggestion.id);
      setSuggestions((cur) => cur.filter((s) => s.id !== suggestion.id));
      toast.info("Memory suggestion dismissed", suggestion.title);
    } catch (err) {
      const message = err instanceof ApiException ? err.message : "Dismiss failed.";
      setError(message);
      toast.danger("Dismiss failed", message);
    } finally {
      setBusyId(null);
    }
  };

  return (
    <AppShell>
      {/* Header — title + pending warning chip + subtitle, filter segments right. */}
      <div className="mb-[18px] flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div className="min-w-0">
          <div className="mb-2 flex flex-wrap items-center gap-2.5">
            <h1 className="text-2xl font-semibold tracking-[-0.02em] text-content sm:text-[30px]">
              Approvals
            </h1>
            <Badge tone="warning" className="px-3 py-[3px] text-xs font-semibold">
              {totals.all} pending
            </Badge>
          </div>
          <p className="max-w-2xl text-[13.5px] leading-relaxed text-content-muted">
            Risky AI actions and memory suggestions wait here for your decision. Nothing runs
            until you approve.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="inline-flex items-center gap-0.5 rounded-md border border-border bg-surface-input/60 p-[3px]">
            <span className="rounded-sm border border-primary/30 bg-[linear-gradient(90deg,rgb(var(--color-primary)/0.2),rgb(var(--color-secondary)/0.12))] px-3 py-1.5 text-[12.5px] font-semibold text-content">
              Pending
            </span>
            <span
              aria-disabled="true"
              title="Decision history is not stored yet"
              className="cursor-not-allowed px-3 py-1.5 text-[12.5px] text-content-faint"
            >
              Approved
            </span>
            <span
              aria-disabled="true"
              title="Decision history is not stored yet"
              className="cursor-not-allowed px-3 py-1.5 text-[12.5px] text-content-faint"
            >
              Rejected
            </span>
          </div>
          <Button variant="ghost" onClick={() => void load()}>
            <RefreshCw size={15} /> Refresh
          </Button>
        </div>
      </div>

      {error ? <div className="mb-4"><ErrorState message={error} onRetry={load} /></div> : null}

      <div className="mb-5 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Card padding="sm" gradient>
          <p className="label-mono">Waiting</p>
          <p className="mt-1.5 text-2xl font-semibold tracking-[-0.02em] text-content">{totals.all}</p>
        </Card>
        <Card padding="sm">
          <p className="label-mono">AI changes</p>
          <p className="mt-1.5 text-2xl font-semibold tracking-[-0.02em] text-warning">{totals.actions}</p>
        </Card>
        <Card padding="sm">
          <p className="label-mono">Memory review</p>
          <p className="mt-1.5 text-2xl font-semibold tracking-[-0.02em] text-primary-bright">{totals.memories}</p>
        </Card>
        <Card padding="sm">
          <p className="label-mono">High risk</p>
          <p className="mt-1.5 text-2xl font-semibold tracking-[-0.02em] text-danger">{totals.highRisk}</p>
        </Card>
      </div>

      {loading ? (
        <Loading label="Loading approvals..." />
      ) : totals.all === 0 ? (
        <EmptyState
          title="No pending approvals"
          description="AI changes and memory suggestions that need review will appear here."
          icon={<ClipboardCheck size={20} />}
          action={<Link href="/dashboard/ai"><Button variant="ghost">Open AI Chat</Button></Link>}
        />
      ) : (
        <div className="grid gap-5 xl:grid-cols-[1.15fr_0.85fr]">
          {/* AI change approvals — standalone risk-tinted glass cards. */}
          <div className="min-w-0 space-y-3.5">
            <SectionHeading
              icon={<ShieldAlert size={16} />}
              title="AI change approvals"
              meta={`${proposals.length} pending action${proposals.length === 1 ? "" : "s"}`}
            />
            {proposals.length === 0 ? (
              <EmptyState
                title="No AI changes waiting"
                description="When AI proposes edits to finance, tasks, routine, system, or files, they will show here."
                className="py-10"
              />
            ) : (
              proposals.map((proposal) => {
                const risk = proposal.risk_level.toUpperCase();
                const busy = busyId === proposal.id;
                const isTxn = isTransactionTool(proposal.tool_name);
                const invalid = isTxn && transactionPayloadErrors(proposal.tool_payload).length > 0;
                const cardError = cardErrors[proposal.id];
                const Glyph = toolIcon(proposal.tool_name);
                return (
                  <div
                    key={proposal.id}
                    className={cn(
                      "panel relative rounded-[18px] p-4 sm:p-5",
                      RISK_CARD[risk],
                    )}
                  >
                    <div className="flex items-start gap-3.5">
                      <span
                        className={cn(
                          "flex h-11 w-11 shrink-0 items-center justify-center rounded-[13px] border",
                          RISK_TILE[risk] ?? "border-border bg-surface-high/60 text-content-muted",
                        )}
                      >
                        <Glyph size={20} />
                      </span>
                      <div className="min-w-0 flex-1">
                        <div className="mb-1.5 flex min-w-0 flex-wrap items-center gap-2">
                          <p className="min-w-0 break-words text-[15px] font-semibold text-content">
                            {humanizeTool(proposal.tool_name)}
                          </p>
                          <Badge
                            tone={RISK_TONE[risk] ?? "neutral"}
                            className="text-[10px] font-semibold uppercase tracking-[0.05em]"
                          >
                            {risk} risk
                          </Badge>
                        </div>
                        {isTxn ? (
                          <TransactionSummary payload={proposal.tool_payload} />
                        ) : (
                          <pre className="mt-1 max-h-28 overflow-auto whitespace-pre-wrap break-words rounded-md border border-border bg-bg/50 p-2.5 font-mono text-[11.5px] leading-relaxed text-content-muted">
                            {previewJson(proposal.tool_payload, 800)}
                          </pre>
                        )}
                        <div className="mt-2.5 flex flex-wrap gap-1.5">
                          <ProvenanceChip icon={<Bot size={11} />}>{proposal.tool_name}</ProvenanceChip>
                          <ProvenanceChip icon={<Clock size={11} />}>
                            {relativeTime(proposal.created_at)}
                          </ProvenanceChip>
                        </div>
                      </div>
                    </div>
                    {cardError ? (
                      <p className="mt-3 flex items-start gap-1.5 rounded-md border border-danger/30 bg-danger/10 px-2.5 py-2 text-[12px] text-danger">
                        <ShieldAlert size={13} className="mt-0.5 shrink-0" />
                        <span className="min-w-0 break-words">{cardError}</span>
                      </p>
                    ) : null}
                    <div className="mt-4 flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center">
                      <Button
                        size="sm"
                        loading={busy}
                        disabled={busy || invalid}
                        onClick={() => void approveProposal(proposal)}
                        title={invalid ? "Fix the highlighted fields before approving" : undefined}
                        className="w-full sm:w-auto"
                      >
                        <CheckCircle2 size={14} /> Approve
                      </Button>
                      <Button size="sm" variant="ghost" disabled={busy} onClick={() => openEdit(proposal)} className="w-full sm:w-auto">
                        <Pencil size={14} /> Edit
                      </Button>
                      <Button size="sm" variant="danger" loading={busy} disabled={busy} onClick={() => void rejectProposal(proposal)} className="w-full sm:w-auto">
                        <XCircle size={14} /> Reject
                      </Button>
                    </div>
                  </div>
                );
              })
            )}
          </div>

          {/* Memory suggestions — violet-tinted review cards. */}
          <div className="min-w-0 space-y-3.5">
            <SectionHeading
              icon={<Brain size={16} />}
              title="Memory suggestions"
              meta={`${suggestions.length} pending memor${suggestions.length === 1 ? "y" : "ies"}`}
            />
            {suggestions.length === 0 ? (
              <EmptyState
                title="No memory suggestions"
                description="Sensitive or uncertain memories will wait here before being saved."
                className="py-10"
              />
            ) : (
              suggestions.map((suggestion) => {
                const busy = busyId === suggestion.id;
                return (
                  <div key={suggestion.id} className="panel relative rounded-[18px] p-4 sm:p-5">
                    <div className="flex items-start gap-3.5">
                      <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-[13px] border border-secondary/30 bg-secondary/10 text-secondary-soft">
                        <Brain size={20} />
                      </span>
                      <div className="min-w-0 flex-1">
                        <div className="mb-1.5 flex min-w-0 flex-wrap items-center gap-2">
                          <p className="min-w-0 break-words text-[15px] font-semibold text-content">
                            {suggestion.title}
                          </p>
                          <Badge tone="secondary" className="text-[10px] font-semibold uppercase tracking-[0.05em]">
                            {suggestion.category}
                          </Badge>
                          <Badge
                            tone={suggestion.sensitivity === "LOW" ? "success" : "warning"}
                            className="text-[10px] font-semibold uppercase tracking-[0.05em]"
                          >
                            {suggestion.sensitivity}
                          </Badge>
                        </div>
                        <p className="text-[13px] leading-[1.55] text-content-muted">{suggestion.content}</p>
                        {suggestion.source_snippet ? (
                          <p className="mt-2 line-clamp-2 text-[11.5px] italic text-content-subtle">
                            From: "{suggestion.source_snippet}"
                          </p>
                        ) : null}
                        <div className="mt-2.5 flex flex-wrap gap-1.5">
                          <ProvenanceChip icon={<Clock size={11} />}>
                            {relativeTime(suggestion.created_at)}
                          </ProvenanceChip>
                        </div>
                      </div>
                    </div>
                    <div className="mt-4 flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center">
                      <Button size="sm" loading={busy} disabled={busy} onClick={() => void approveSuggestion(suggestion)} className="w-full sm:w-auto">
                        <CheckCircle2 size={14} /> Save memory
                      </Button>
                      <Button size="sm" variant="danger" loading={busy} disabled={busy} onClick={() => void rejectSuggestion(suggestion)} className="w-full sm:w-auto">
                        <XCircle size={14} /> Dismiss
                      </Button>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>
      )}

      <Modal
        open={editing !== null}
        onClose={() => { if (!busyId) closeEdit(); }}
        title="Edit proposed change"
        description={
          editing
            ? isTransactionTool(editing.tool_name)
              ? `${humanizeTool(editing.tool_name)} — review the fields, then save.`
              : `${humanizeTool(editing.tool_name)} - adjust the JSON payload before approval.`
            : undefined
        }
        footer={
          <>
            <Button variant="ghost" onClick={closeEdit} disabled={Boolean(busyId)}>
              Cancel
            </Button>
            <Button onClick={() => void saveEdit()} loading={Boolean(editing && busyId === editing.id)}>
              Save payload
            </Button>
          </>
        }
      >
        {editing && isTransactionTool(editing.tool_name) ? (
          <TransactionEditForm
            value={editPayload ?? {}}
            onChange={setEditPayload}
            disabled={Boolean(busyId)}
          />
        ) : (
          <Textarea
            label="Payload JSON"
            value={editText}
            onChange={(e) => setEditText(e.target.value)}
            rows={11}
            spellCheck={false}
            className={cn("font-mono text-[12.5px]", editError && "border-danger/50")}
          />
        )}
        {editError ? <p className="mt-2 text-[12px] text-danger">{editError}</p> : null}
      </Modal>
    </AppShell>
  );
}
