"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { AlertTriangle, Bot, Lock, SendHorizonal, ShieldCheck, Sparkles, User, XCircle } from "lucide-react";
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
    <AppShell title="AI Chat" subtitle="AI proposes — humans approve every write action">
      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <Card padding="none" className="flex h-[calc(100vh-230px)] min-h-[460px] flex-col">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-5 py-3.5">
              <div className="flex items-center gap-2.5">
                <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10 text-primary">
                  <Bot size={17} />
                </span>
                <div className="leading-tight">
                  <p className="text-sm font-semibold text-content">CoreOS Assistant</p>
                  <p className="label-mono">
                    {activeProvider ? activeProvider.detail : configured ? "Configured" : "Not configured"}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                {activeProvider ? <PrivacyModeBadge external={activeProvider.external} /> : null}
                <ProviderSelector providers={providers} value={providerId} onChange={setProviderId} />
              </div>
            </div>

            <div className="custom-scrollbar flex-1 space-y-4 overflow-y-auto px-5 py-4">
              {messages.length === 0 ? (
                <div className="flex h-full items-center justify-center">
                  <EmptyState
                    title="Start a conversation"
                    description="Ask anything. The assistant will respond honestly and never fake AI output or execute actions on its own."
                    icon={<Bot size={20} />}
                  />
                </div>
              ) : (
                messages.map((message) => {
                  const isUser = message.role === "user";
                  return (
                    <div
                      key={message.id}
                      className={cn("flex gap-3", isUser ? "flex-row-reverse" : "flex-row")}
                    >
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
                          "max-w-[78%] rounded-xl border px-3.5 py-2.5 text-sm",
                          isUser
                            ? "border-border bg-surface-high text-content"
                            : "border-border bg-surface-input text-content-muted",
                        )}
                      >
                        <p className="whitespace-pre-wrap leading-relaxed">{message.content}</p>
                      </div>
                    </div>
                  );
                })
              )}
              <div ref={endRef} />
            </div>

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
                placeholder="Message CoreOS Assistant…"
                className="h-10 flex-1 rounded-md border border-border bg-surface-input px-3 text-sm text-content placeholder:text-content-subtle focus:border-primary focus:outline-none"
              />
              <Button type="submit" disabled={sending || !input.trim()}>
                <Send size={15} />
                <span className="hidden sm:inline">Send</span>
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
                <dt className="text-content-muted">Provider</dt>
                <dd className="text-content">{activeProvider?.name ?? "—"}</dd>
              </div>
              <div className="flex items-center justify-between">
                <dt className="text-content-muted">Status</dt>
                <dd>
                  <Badge tone={activeProvider?.configured ? "primary" : "neutral"}>
                    {activeProvider?.detail ?? "Not configured"}
                  </Badge>
                </dd>
              </div>
              <div className="flex items-center justify-between">
                <dt className="text-content-muted">Mode</dt>
                <dd className="text-content">Human-in-the-loop</dd>
              </div>
            </dl>
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
            <CardHeader title="Pending proposals" icon={<Bot size={18} />} />
            {proposals.length === 0 ? (
              <p className="py-2 text-[13px] text-content-muted">
                No pending proposals. When the assistant proposes an action, it will appear here for
                your review.
              </p>
            ) : (
              <ul className="space-y-2.5">
                {proposals.map((proposal) => (
                  <li key={proposal.id} className="rounded-lg border border-border bg-surface-input p-3">
                    <div className="mb-1.5 flex items-center justify-between">
                      <span className="font-mono text-[13px] text-content">{proposal.tool_name}</span>
                      <Badge tone={proposal.risk_level === "HIGH" ? "danger" : "warning"}>
                        {proposal.risk_level}
                      </Badge>
                    </div>
                    <pre className="custom-scrollbar overflow-x-auto rounded bg-bg/60 p-2 text-[11px] text-content-muted">
                      {JSON.stringify(proposal.tool_payload, null, 2)}
                    </pre>
                    <div className="mt-2 flex justify-end">
                      <Button variant="danger" size="sm" onClick={() => reject(proposal)}>
                        <XCircle size={14} /> Reject
                      </Button>
                    </div>
                  </li>
                ))}
              </ul>
            )}
            <p className="mt-3 text-[11px] text-content-subtle">
              Approval/execution of proposals is intentionally not implemented in this MVP.
            </p>
          </Card>
        </div>
      </div>
    </AppShell>
  );
}
