"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  Brain,
  CheckCircle2,
  ClipboardCheck,
  Pencil,
  RefreshCw,
  ShieldAlert,
  XCircle,
} from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { PageHeader } from "@/components/layout/PageHeader";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardHeader } from "@/components/ui/Card";
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
      <PageHeader
        title="Approvals"
        subtitle="Review pending AI changes, memory suggestions, and other actions before they run."
        actions={
          <Button variant="ghost" onClick={() => void load()}>
            <RefreshCw size={15} /> Refresh
          </Button>
        }
      />

      {error ? <div className="mb-4"><ErrorState message={error} onRetry={load} /></div> : null}

      <div className="mb-5 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Card padding="sm" className="border-primary/25">
          <p className="label-mono">Waiting</p>
          <p className="mt-1 text-2xl font-semibold text-content">{totals.all}</p>
        </Card>
        <Card padding="sm">
          <p className="label-mono">AI changes</p>
          <p className="mt-1 text-2xl font-semibold text-warning">{totals.actions}</p>
        </Card>
        <Card padding="sm">
          <p className="label-mono">Memory review</p>
          <p className="mt-1 text-2xl font-semibold text-primary">{totals.memories}</p>
        </Card>
        <Card padding="sm">
          <p className="label-mono">High risk</p>
          <p className="mt-1 text-2xl font-semibold text-danger">{totals.highRisk}</p>
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
          <Card>
            <CardHeader
              title="AI change approvals"
              subtitle={`${proposals.length} pending action${proposals.length === 1 ? "" : "s"}`}
              icon={<ShieldAlert size={18} />}
            />
            {proposals.length === 0 ? (
              <EmptyState
                title="No AI changes waiting"
                description="When AI proposes edits to finance, tasks, routine, system, or files, they will show here."
                className="py-10"
              />
            ) : (
              <div className="space-y-3">
                {proposals.map((proposal) => {
                  const risk = proposal.risk_level.toUpperCase();
                  const busy = busyId === proposal.id;
                  const isTxn = isTransactionTool(proposal.tool_name);
                  const invalid = isTxn && transactionPayloadErrors(proposal.tool_payload).length > 0;
                  const cardError = cardErrors[proposal.id];
                  return (
                    <div key={proposal.id} className="rounded-xl border border-border bg-surface-input p-3">
                      <div className="flex min-w-0 flex-wrap items-center gap-2">
                        <p className="min-w-0 break-words text-sm font-semibold text-content">{humanizeTool(proposal.tool_name)}</p>
                        <Badge tone={RISK_TONE[risk] ?? "neutral"}>{risk} risk</Badge>
                        <span className="text-[11px] text-content-subtle">{relativeTime(proposal.created_at)}</span>
                      </div>
                      {isTxn ? (
                        <TransactionSummary payload={proposal.tool_payload} />
                      ) : (
                        <pre className="mt-2 max-h-28 overflow-auto whitespace-pre-wrap break-words rounded-lg border border-border bg-bg/50 p-2 font-mono text-[11.5px] leading-relaxed text-content-muted">
                          {previewJson(proposal.tool_payload, 800)}
                        </pre>
                      )}
                      {cardError ? (
                        <p className="mt-2 flex items-start gap-1.5 rounded-lg border border-danger/30 bg-danger/10 px-2.5 py-2 text-[12px] text-danger">
                          <ShieldAlert size={13} className="mt-0.5 shrink-0" />
                          <span className="min-w-0 break-words">{cardError}</span>
                        </p>
                      ) : null}
                      <div className="mt-3 flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center">
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
                })}
              </div>
            )}
          </Card>

          <Card>
            <CardHeader
              title="Memory suggestions"
              subtitle={`${suggestions.length} pending memor${suggestions.length === 1 ? "y" : "ies"}`}
              icon={<Brain size={18} />}
            />
            {suggestions.length === 0 ? (
              <EmptyState
                title="No memory suggestions"
                description="Sensitive or uncertain memories will wait here before being saved."
                className="py-10"
              />
            ) : (
              <div className="space-y-3">
                {suggestions.map((suggestion) => {
                  const busy = busyId === suggestion.id;
                  return (
                    <div key={suggestion.id} className="rounded-xl border border-border bg-surface-input p-3">
                      <div className="flex min-w-0 flex-wrap items-center gap-2">
                        <p className="min-w-0 break-words text-sm font-semibold text-content">{suggestion.title}</p>
                        <Badge tone="primary">{suggestion.category}</Badge>
                        <Badge tone={suggestion.sensitivity === "LOW" ? "success" : "warning"}>
                          {suggestion.sensitivity}
                        </Badge>
                      </div>
                      <p className="mt-2 text-[13px] leading-relaxed text-content-muted">{suggestion.content}</p>
                      {suggestion.source_snippet ? (
                        <p className="mt-2 line-clamp-2 text-[11.5px] italic text-content-subtle">
                          From: "{suggestion.source_snippet}"
                        </p>
                      ) : null}
                      <div className="mt-3 flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center">
                        <Button size="sm" loading={busy} disabled={busy} onClick={() => void approveSuggestion(suggestion)} className="w-full sm:w-auto">
                          <CheckCircle2 size={14} /> Save memory
                        </Button>
                        <Button size="sm" variant="ghost" loading={busy} disabled={busy} onClick={() => void rejectSuggestion(suggestion)} className="w-full sm:w-auto">
                          <XCircle size={14} /> Dismiss
                        </Button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </Card>
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
