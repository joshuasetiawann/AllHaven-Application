"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { AlertTriangle, Bot, Cpu, Lock, SendHorizonal, ShieldCheck, Sparkles, User, XCircle } from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { Button } from "@/components/ui/Button";
import { Card, CardHeader } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { EmptyState } from "@/components/ui/States";
import { MultiAgentSelector } from "@/components/ai/MultiAgentSelector";
import { AgentResponseCard, type AgentCardData } from "@/components/ai/AgentResponseCard";
import { aiApi, ApiException } from "@/lib/api";
import { cn } from "@/lib/format";
import type { AiProvider, MultiChatResponse, ToolProposal } from "@/types";

const ALLOWED_TOOLS = ["create_task", "create_note", "create_transaction", "summarize_notes"];

interface Turn {
  id: string;
  user: string;
  providerIds: string[];
  run?: MultiChatResponse;
  error?: string;
}

export default function AiChatPage() {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [sessionId, setSessionId] = useState<string | undefined>(undefined);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [proposals, setProposals] = useState<ToolProposal[]>([]);
  const [providers, setProviders] = useState<AiProvider[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const endRef = useRef<HTMLDivElement>(null);

  const providerById = useMemo(
    () => Object.fromEntries(providers.map((p) => [p.id, p])),
    [providers],
  );
  const anyExternal = selected.some((id) => providerById[id]?.external);
  const anyLocal = selected.some((id) => providerById[id] && !providerById[id]!.external);

  const loadProposals = async () => {
    try {
      setProposals(await aiApi.listProposals());
    } catch {
      /* non-blocking */
    }
  };

  const loadProviders = async () => {
    try {
      const res = await aiApi.listProviders();
      setProviders(res.providers);
      const preferred = res.providers.find((p) => p.id === "ollama") ?? res.providers[0];
      if (preferred) setSelected((cur) => (cur.length ? cur : [preferred.id]));
    } catch {
      /* non-blocking */
    }
  };

  useEffect(() => {
    void loadProposals();
    void loadProviders();
  }, []);
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns]);

  const send = async (event: React.FormEvent) => {
    event.preventDefault();
    const text = input.trim();
    if (!text || sending) return;
    if (selected.length === 0) {
      setError("Select at least one AI agent.");
      return;
    }
    setError(null);
    setSending(true);

    const turnId = `t-${Date.now()}`;
    const ids = [...selected];
    setTurns((prev) => [...prev, { id: turnId, user: text, providerIds: ids }]);
    setInput("");

    try {
      const run = await aiApi.multiChat(text, ids, sessionId);
      setSessionId(run.session_id);
      setTurns((prev) => prev.map((t) => (t.id === turnId ? { ...t, run } : t)));
    } catch (err) {
      const msg = err instanceof ApiException ? err.message : "Failed to send message.";
      setTurns((prev) => prev.map((t) => (t.id === turnId ? { ...t, error: msg } : t)));
    } finally {
      setSending(false);
    }
  };

  const reject = async (proposal: ToolProposal) => {
    setProposals((prev) => prev.filter((p) => p.id !== proposal.id));
    try {
      await aiApi.rejectProposal(proposal.id);
    } catch {
      void loadProposals();
    }
  };

  // Build the per-agent cards for a turn (queued placeholders while pending).
  const cardsForTurn = (turn: Turn): AgentCardData[] => {
    if (turn.run) {
      return turn.run.agent_responses.map((r) => ({
        provider_id: r.provider_id,
        provider_name: r.provider_name,
        status: r.status,
        content: r.content,
        error_message: r.error_message,
        latency_ms: r.latency_ms,
        external: providerById[r.provider_id]?.external,
      }));
    }
    return turn.providerIds.map((id) => ({
      provider_id: id,
      provider_name: providerById[id]?.name ?? id,
      status: "running",
      external: providerById[id]?.external,
    }));
  };

  return (
    <AppShell>
      <div className="mb-5 flex items-center gap-3">
        <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/12 text-primary">
          <Bot size={20} />
        </span>
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-content sm:text-[28px]">AI Chat</h1>
          <p className="text-[13.5px] text-content-muted">
            Run up to 3 agents at once. AI proposes — humans approve every write action.
          </p>
        </div>
      </div>

      <div className="grid gap-5 lg:grid-cols-3">
        {/* Chat */}
        <div className="min-w-0 lg:col-span-2">
          <Card padding="none" className="flex h-[calc(100vh-230px)] min-h-[460px] flex-col">
            <div className="flex flex-col gap-2.5 border-b border-border px-5 py-3.5">
              <div className="flex items-center gap-2.5">
                <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10 text-primary">
                  <Sparkles size={16} />
                </span>
                <div className="leading-tight">
                  <p className="text-sm font-semibold text-content">CoreOS Multi-Agent</p>
                  <p className="label-mono">Concurrent agents · honest status</p>
                </div>
              </div>
              <MultiAgentSelector providers={providers} selected={selected} onChange={setSelected} />
              <div className="flex flex-wrap items-center gap-2">
                {anyLocal ? (
                  <Badge tone="success">
                    <Cpu size={11} className="mr-1 inline" /> Local AI included
                  </Badge>
                ) : null}
                {anyExternal ? (
                  <Badge tone="warning">
                    <AlertTriangle size={11} className="mr-1 inline" /> External AI selected
                  </Badge>
                ) : null}
              </div>
            </div>

            <div className="custom-scrollbar flex-1 space-y-5 overflow-y-auto px-4 py-4 sm:px-5">
              {turns.length === 0 ? (
                <div className="flex h-full items-center justify-center">
                  <EmptyState
                    title="Start a conversation"
                    description="Pick 1–3 agents and ask anything. Each agent answers in its own card. CoreOS never fabricates AI output or executes actions on its own."
                    icon={<Bot size={20} />}
                  />
                </div>
              ) : (
                turns.map((turn) => (
                  <div key={turn.id} className="space-y-3">
                    {/* User message */}
                    <div className="flex flex-row-reverse gap-3">
                      <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-border bg-surface-high text-content">
                        <User size={15} />
                      </span>
                      <div className="max-w-[80%] rounded-xl border border-primary/30 bg-primary/10 px-3.5 py-2.5 text-sm leading-relaxed text-content">
                        <p className="whitespace-pre-wrap break-words">{turn.user}</p>
                      </div>
                    </div>

                    {/* Agent responses */}
                    {turn.error ? (
                      <p className="rounded-lg border border-danger/30 bg-danger/10 px-3 py-2 text-[12.5px] text-danger">
                        {turn.error}
                      </p>
                    ) : (
                      <div
                        className={cn(
                          "grid gap-3",
                          turn.providerIds.length > 1 ? "sm:grid-cols-2" : "grid-cols-1",
                        )}
                      >
                        {cardsForTurn(turn).map((card) => (
                          <AgentResponseCard key={`${turn.id}-${card.provider_id}`} data={card} />
                        ))}
                      </div>
                    )}
                  </div>
                ))
              )}
              <div ref={endRef} />
            </div>

            {anyExternal ? (
              <p className="mx-3 mb-1 flex items-start gap-1.5 rounded-md border border-warning/30 bg-warning/10 px-3 py-2 text-[12px] text-warning">
                <AlertTriangle size={13} className="mt-0.5 shrink-0" />
                External AI may process your prompt. Do not send confidential data unless allowed in Settings.
              </p>
            ) : null}

            {error ? <p className="px-5 pb-1 text-[12px] text-danger">{error}</p> : null}

            <form onSubmit={send} className="flex items-center gap-2 border-t border-border p-3">
              <input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Type a command or ask a question…"
                className="h-11 min-w-0 flex-1 rounded-lg border border-border bg-surface-input px-3.5 text-sm text-content placeholder:text-content-subtle focus:border-primary/70 focus:outline-none focus:ring-1 focus:ring-primary/30"
              />
              <Button type="submit" size="lg" loading={sending} disabled={!input.trim() || selected.length === 0} className="px-4">
                {!sending ? <SendHorizonal size={16} /> : null}
              </Button>
            </form>
          </Card>
        </div>

        {/* Right rail */}
        <div className="space-y-5">
          <Card>
            <CardHeader title="Selected agents" icon={<Bot size={18} />} />
            {selected.length === 0 ? (
              <p className="py-1 text-[13px] text-content-muted">No agents selected.</p>
            ) : (
              <ul className="space-y-2 text-[13px]">
                {selected.map((id) => {
                  const p = providerById[id];
                  return (
                    <li key={id} className="flex items-center justify-between">
                      <span className="truncate text-content">{p?.name ?? id}</span>
                      <Badge tone={p?.configured ? "primary" : "neutral"}>{p?.detail ?? "Unknown"}</Badge>
                    </li>
                  );
                })}
              </ul>
            )}
            <Link
              href="/dashboard/settings"
              className="mt-3 inline-flex items-center gap-1 text-[13px] text-primary hover:underline"
            >
              Configure AI providers →
            </Link>
          </Card>

          <Card>
            <CardHeader title="Proposed tools" subtitle="Available when a model is configured" icon={<Sparkles size={18} />} />
            <div className="flex flex-wrap gap-1.5">
              {ALLOWED_TOOLS.map((tool) => (
                <Badge key={tool} tone="secondary" className="font-mono">
                  {tool}
                </Badge>
              ))}
            </div>
          </Card>

          <Card>
            <CardHeader title="Pending proposals" icon={<ShieldCheck size={18} />} />
            {proposals.length === 0 ? (
              <p className="py-1 text-[13px] text-content-muted">
                No pending proposals. When the assistant proposes an action, it appears here for your review.
              </p>
            ) : (
              <ul className="space-y-2.5">
                {proposals.map((proposal) => (
                  <li key={proposal.id} className="rounded-lg border border-border bg-surface-input p-3">
                    <div className="mb-1.5 flex items-center justify-between">
                      <span className="font-mono text-[13px] text-content">{proposal.tool_name}</span>
                      <Badge tone={proposal.risk_level === "HIGH" ? "danger" : "warning"}>{proposal.risk_level}</Badge>
                    </div>
                    <pre className="custom-scrollbar overflow-x-auto rounded bg-bg/60 p-2 text-[11px] text-content-muted">
                      {JSON.stringify(proposal.tool_payload, null, 2)}
                    </pre>
                    <div className="mt-2 flex items-center justify-end gap-2">
                      <button
                        disabled
                        title="Execution is not enabled in this MVP"
                        className="inline-flex cursor-not-allowed items-center gap-1 rounded-md border border-border px-2.5 py-1 text-[12px] text-content-subtle opacity-60"
                      >
                        Approve
                      </button>
                      <Button variant="danger" size="sm" onClick={() => reject(proposal)}>
                        <XCircle size={14} /> Reject
                      </Button>
                    </div>
                  </li>
                ))}
              </ul>
            )}
            <p className="mt-3 text-[11px] text-content-subtle">
              Human approval required for write actions. Approval/execution is intentionally not implemented in this MVP.
            </p>
          </Card>

          <Card className="border-primary/15">
            <div className="flex items-start gap-2.5">
              <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
                <Lock size={16} />
              </span>
              <div>
                <p className="text-[13px] font-semibold text-content">Local-first by design</p>
                <p className="mt-0.5 text-[12px] leading-relaxed text-content-muted">
                  When a local model (Ollama) is configured, AI processing runs on your machine. CoreOS
                  never fakes AI responses.
                </p>
              </div>
            </div>
          </Card>
        </div>
      </div>
    </AppShell>
  );
}
