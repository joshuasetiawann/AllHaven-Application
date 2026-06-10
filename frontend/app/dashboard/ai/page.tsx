"use client";

import { useEffect, useRef, useState } from "react";
import { Bot, Lock, SendHorizonal, ShieldCheck, Sparkles, User, XCircle } from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { Button } from "@/components/ui/Button";
import { Card, CardHeader } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { EmptyState } from "@/components/ui/States";
import { ProviderSelector } from "@/components/ai/ProviderSelector";
import { PrivacyModeBadge } from "@/components/ai/PrivacyModeBadge";
import { aiApi, ApiException } from "@/lib/api";
import { cn } from "@/lib/format";
import type { AiProvider, ChatMessage, ToolProposal } from "@/types";

const ALLOWED_TOOLS = ["create_task", "create_note", "create_transaction", "summarize_notes"];

export default function AiChatPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [sessionId, setSessionId] = useState<string | undefined>(undefined);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [configured, setConfigured] = useState<boolean | null>(null);
  const [proposals, setProposals] = useState<ToolProposal[]>([]);
  const [providers, setProviders] = useState<AiProvider[]>([]);
  const [providerId, setProviderId] = useState<string>("ollama");
  const [error, setError] = useState<string | null>(null);
  const endRef = useRef<HTMLDivElement>(null);

  const activeProvider = useMemo(
    () => providers.find((p) => p.id === providerId),
    [providers, providerId],
  );

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
      // Prefer the local Ollama agent by default; otherwise the first provider.
      const preferred = res.providers.find((p) => p.id === "ollama") ?? res.providers[0];
      if (preferred) setProviderId(preferred.id);
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
  }, [messages]);

  const send = async (event: React.FormEvent) => {
    event.preventDefault();
    const text = input.trim();
    if (!text || sending) return;
    setError(null);
    setSending(true);

    const optimistic: ChatMessage = {
      id: `local-${Date.now()}`,
      session_id: sessionId ?? null,
      role: "user",
      content: text,
      meta: null,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, optimistic]);
    setInput("");

    try {
      const result = await aiApi.chat(text, sessionId, providerId);
      setSessionId(result.session_id);
      setConfigured(result.ai_configured);
      setMessages((prev) => [...prev, result.reply]);
    } catch (err) {
      setError(err instanceof ApiException ? err.message : "Failed to send message.");
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

  return (
    <AppShell>
      <div className="mb-5 flex items-center gap-3">
        <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/12 text-primary">
          <Bot size={20} />
        </span>
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-content sm:text-[28px]">AI Chat</h1>
          <p className="text-[13.5px] text-content-muted">AI proposes — humans approve every write action.</p>
        </div>
      </div>

      <div className="grid gap-5 lg:grid-cols-3">
        {/* Chat */}
        <div className="lg:col-span-2">
          <Card padding="none" className="flex h-[calc(100vh-230px)] min-h-[460px] flex-col">
            <div className="flex items-center justify-between border-b border-border px-5 py-3.5">
              <div className="flex items-center gap-2.5">
                <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10 text-primary">
                  <Sparkles size={16} />
                </span>
                <div className="leading-tight">
                  <p className="text-sm font-semibold text-content">CoreOS Assistant</p>
                  <p className="label-mono">{configured === null ? "Idle" : configured ? "Configured" : "Not configured"}</p>
                </div>
              </div>
              <Badge tone={configured ? "primary" : "neutral"}>{configured ? "Live off" : "Not configured"}</Badge>
            </div>

            <div className="custom-scrollbar flex-1 space-y-4 overflow-y-auto px-4 py-4 sm:px-5">
              {messages.length === 0 ? (
                <div className="flex h-full items-center justify-center">
                  <EmptyState
                    title="Start a conversation"
                    description="Ask anything. The assistant answers honestly and never fabricates AI output or executes actions on its own."
                    icon={<Bot size={20} />}
                  />
                </div>
              ) : (
                messages.map((message) => {
                  const isUser = message.role === "user";
                  return (
                    <div key={message.id} className={cn("flex gap-3", isUser ? "flex-row-reverse" : "flex-row")}>
                      <span
                        className={cn(
                          "flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border",
                          isUser
                            ? "border-border bg-surface-high text-content"
                            : "border-primary/30 bg-primary/10 text-primary",
                        )}
                      >
                        {isUser ? <User size={15} /> : <Bot size={15} />}
                      </span>
                      <div
                        className={cn(
                          "max-w-[80%] rounded-xl border px-3.5 py-2.5 text-sm leading-relaxed",
                          isUser ? "border-primary/30 bg-primary/10 text-content" : "border-border bg-surface-input text-content-muted",
                        )}
                      >
                        <p className="whitespace-pre-wrap">{message.content}</p>
                      </div>
                    </div>
                  );
                })
              )}
              <div ref={endRef} />
            </div>

            {activeProvider && !activeProvider.configured ? (
              <p className="mx-3 mb-1 flex flex-wrap items-center gap-1.5 rounded-md border border-border bg-surface-input px-3 py-2 text-[12px] text-content-muted">
                {activeProvider.name} is not configured.
                <Link href="/dashboard/settings" className="text-primary hover:underline">
                  Set it up in Settings →
                </Link>
              </p>
            ) : null}
            {activeProvider?.external ? (
              <p className="mx-3 mb-1 flex items-start gap-1.5 rounded-md border border-warning/30 bg-warning/10 px-3 py-2 text-[12px] text-warning">
                <AlertTriangle size={13} className="mt-0.5 shrink-0" />
                External AI may process your prompt. Do not send confidential data unless allowed.
              </p>
            ) : null}

            {error ? <p className="px-5 pb-1 text-[12px] text-danger">{error}</p> : null}

            <form onSubmit={send} className="flex items-center gap-2 border-t border-border p-3">
              <input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Type a command or ask a question…"
                className="h-11 flex-1 rounded-lg border border-border bg-surface-input px-3.5 text-sm text-content placeholder:text-content-subtle focus:border-primary/70 focus:outline-none focus:ring-1 focus:ring-primary/30"
              />
              <Button type="submit" size="lg" loading={sending} disabled={!input.trim()} className="px-4">
                {!sending ? <SendHorizonal size={16} /> : null}
              </Button>
            </form>
          </Card>
        </div>

        {/* Right rail */}
        <div className="space-y-5">
          <Card>
            <CardHeader title="Assistant status" icon={<Bot size={18} />} />
            <dl className="space-y-2.5 text-[13px]">
              <div className="flex items-center justify-between">
                <dt className="text-content-muted">State</dt>
                <dd>
                  <Badge tone={configured ? "primary" : "neutral"}>
                    {configured === null ? "Idle" : configured ? "Configured" : "Not configured"}
                  </Badge>
                </dd>
              </div>
              <div className="flex items-center justify-between">
                <dt className="text-content-muted">Mode</dt>
                <dd className="text-content">Human-in-the-loop</dd>
              </div>
              <div className="flex items-center justify-between">
                <dt className="text-content-muted">Execution</dt>
                <dd className="text-content">Disabled in MVP</dd>
              </div>
            </dl>
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
