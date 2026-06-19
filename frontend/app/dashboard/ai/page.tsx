"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { AlertTriangle, Bot, Crown, Cpu, Layers, Loader2, PanelLeft, SendHorizonal, Sparkles, Swords, User } from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { ConversationSidebar } from "@/components/ai/ConversationSidebar";
import { MultiAgentSelector } from "@/components/ai/MultiAgentSelector";
import { AgentResponseCard, type AgentCardData } from "@/components/ai/AgentResponseCard";
import { aiApi, ApiException } from "@/lib/api";
import { cn } from "@/lib/format";
import type { AgentResponseStatus, AiProvider, ChatGroup, ChatMessage, ChatSession } from "@/types";

type ChatMode = "parallel" | "debate";

// Turn one persisted debate ChatMessage into the card model AgentResponseCard wants.
function toCard(m: ChatMessage): AgentCardData {
  const meta = (m.meta ?? {}) as Record<string, unknown>;
  const status = (meta.status as AgentResponseStatus) || "completed";
  const completed = status === "completed";
  return {
    provider_id: String(meta.provider_id ?? ""),
    provider_name: String(meta.provider_name ?? "Agent"),
    status,
    content: completed ? m.content : null,
    error_message: completed ? null : m.content,
    latency_ms: (meta.latency_ms as number) ?? null,
    external: Boolean(meta.external),
  };
}

type ThreadItem =
  | { kind: "user"; key: string; message: ChatMessage }
  | { kind: "agent"; key: string; message: ChatMessage }
  | { kind: "final"; key: string; message: ChatMessage }
  | { kind: "round"; key: string; round: number; phase: string; items: ChatMessage[] };

// Fold the flat message list into render blocks: plain bubbles for user/single/
// parallel turns, grouped "Round N" sections for debate turns, and a highlighted
// final-answer block for the synthesis.
function buildThread(messages: ChatMessage[]): ThreadItem[] {
  const items: ThreadItem[] = [];
  let i = 0;
  while (i < messages.length) {
    const m = messages[i];
    const meta = (m.meta ?? {}) as Record<string, unknown>;
    if (m.role === "user") {
      items.push({ kind: "user", key: m.id, message: m });
      i += 1;
    } else if (meta.debate && meta.debate_final) {
      items.push({ kind: "final", key: m.id, message: m });
      i += 1;
    } else if (meta.debate) {
      const runId = meta.run_id;
      const round = Number(meta.round ?? 1);
      const group: ChatMessage[] = [];
      while (i < messages.length) {
        const mm = (messages[i].meta ?? {}) as Record<string, unknown>;
        if (!mm.debate || mm.debate_final || mm.run_id !== runId || Number(mm.round ?? 1) !== round) break;
        group.push(messages[i]);
        i += 1;
      }
      const phase = String(((group[0]?.meta ?? {}) as Record<string, unknown>).phase ?? "opening");
      items.push({ kind: "round", key: `${String(runId)}-${round}`, round, phase, items: group });
    } else {
      items.push({ kind: "agent", key: m.id, message: m });
      i += 1;
    }
  }
  return items;
}

export default function AiChatPage() {
  const [groups, setGroups] = useState<ChatGroup[]>([]);
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [providers, setProviders] = useState<AiProvider[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [mode, setMode] = useState<ChatMode>("parallel");
  const [rounds, setRounds] = useState(2);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [pendingUser, setPendingUser] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  const providerById = useMemo(() => Object.fromEntries(providers.map((p) => [p.id, p])), [providers]);
  const anyExternal = selected.some((id) => providerById[id]?.external);
  const anyLocal = selected.some((id) => providerById[id] && !providerById[id]!.external);
  const activeSession = sessions.find((s) => s.id === activeId) || null;
  const thread = useMemo(() => buildThread(messages), [messages]);

  const refreshSessions = async () => {
    try { setSessions(await aiApi.listSessions()); } catch { /* non-blocking */ }
  };
  const refreshGroups = async () => {
    try { setGroups(await aiApi.listGroups()); } catch { /* non-blocking */ }
  };

  useEffect(() => {
    void refreshSessions();
    void refreshGroups();
    aiApi.listProviders()
      .then((res) => {
        setProviders(res.providers);
        const pref = res.providers.find((p) => p.id === "ollama") ?? res.providers[0];
        if (pref) setSelected((cur) => (cur.length ? cur : [pref.id]));
      })
      .catch(() => {});
  }, []);

  // Load the active conversation's messages.
  useEffect(() => {
    if (!activeId) { setMessages([]); return; }
    let on = true;
    aiApi.listMessages(activeId).then((m) => on && setMessages(m)).catch(() => on && setMessages([]));
    return () => { on = false; };
  }, [activeId]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, pendingUser, sending]);

  // --- conversation actions ---
  const selectSession = (id: string) => { setActiveId(id); setError(null); setDrawerOpen(false); };

  const newChat = async (groupId?: string | null) => {
    try {
      const s = await aiApi.createSession(groupId ?? null);
      setSessions((prev) => [s, ...prev]);
      setActiveId(s.id);
      setMessages([]);
      setError(null);
      setDrawerOpen(false);
    } catch (e) {
      setError(e instanceof ApiException ? e.message : "Could not create chat.");
    }
  };

  const renameChat = async (s: ChatSession) => {
    const t = window.prompt("Rename conversation", s.title || "");
    if (t == null) return;
    const title = t.trim();
    if (!title) return;
    await aiApi.updateSession(s.id, { title }).catch(() => {});
    void refreshSessions();
  };
  const deleteChat = async (s: ChatSession) => {
    if (!window.confirm(`Delete "${s.title || "New Chat"}"? This cannot be undone.`)) return;
    await aiApi.deleteSession(s.id).catch(() => {});
    if (activeId === s.id) { setActiveId(null); setMessages([]); }
    void refreshSessions();
  };
  const moveChat = async (s: ChatSession, groupId: string | null) => {
    await aiApi.updateSession(s.id, { group_id: groupId }).catch(() => {});
    void refreshSessions();
  };
  const createGroup = async () => {
    const name = window.prompt("New group name");
    if (!name || !name.trim()) return;
    await aiApi.createGroup(name.trim()).catch(() => {});
    void refreshGroups();
  };
  const renameGroup = async (g: ChatGroup) => {
    const name = window.prompt("Rename group", g.name);
    if (name == null || !name.trim()) return;
    await aiApi.renameGroup(g.id, name.trim()).catch(() => {});
    void refreshGroups();
  };
  const deleteGroup = async (g: ChatGroup) => {
    if (!window.confirm(`Delete group "${g.name}"? Its chats are kept (moved out of the group).`)) return;
    await aiApi.deleteGroup(g.id).catch(() => {});
    void refreshGroups();
    void refreshSessions();
  };

  // --- send ---
  const send = async (event: React.FormEvent) => {
    event.preventDefault();
    const text = input.trim();
    if (!text || sending) return;
    if (selected.length === 0) { setError("Select at least one AI agent."); return; }
    setError(null);
    setSending(true);
    setPendingUser(text);
    setInput("");
    try {
      const run = mode === "debate"
        ? await aiApi.debateChat(text, selected, activeId ?? undefined, rounds)
        : await aiApi.multiChat(text, selected, activeId ?? undefined);
      setActiveId(run.session_id);
      const msgs = await aiApi.listMessages(run.session_id);
      setMessages(msgs);
      void refreshSessions();
    } catch (err) {
      setError(err instanceof ApiException ? err.message : "Failed to send message.");
    } finally {
      setSending(false);
      setPendingUser(null);
    }
  };

  // --- thread rendering ---
  const renderBubble = (m: ChatMessage) => {
    const isUser = m.role === "user";
    const provider = (m.meta?.provider_name as string) || null;
    const status = (m.meta?.status as string) || "";
    const isError = !isUser && status && status !== "completed";
    return (
      <div className={cn("flex gap-3", isUser ? "flex-row-reverse" : "flex-row")}>
        <span className={cn(
          "flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border",
          isUser ? "border-border bg-surface-high text-content" : "border-primary/30 bg-primary/10 text-primary",
        )}>
          {isUser ? <User size={15} /> : <Bot size={15} />}
        </span>
        <div className="min-w-0 max-w-[82%]">
          {provider && !isUser ? (
            <p className="mb-0.5 text-[10.5px] font-medium uppercase tracking-wide text-content-subtle">{provider}</p>
          ) : null}
          <div className={cn(
            "rounded-xl border px-3.5 py-2.5 text-sm leading-relaxed",
            isUser ? "border-primary/30 bg-primary/10 text-content"
              : isError ? "border-warning/30 bg-warning/10 text-warning"
              : "border-border bg-surface-input text-content-muted",
          )}>
            <p className="whitespace-pre-wrap break-words">{m.content}</p>
          </div>
        </div>
      </div>
    );
  };

  const renderFinal = (m: ChatMessage) => {
    const status = (m.meta?.status as string) || "completed";
    const ok = status === "completed";
    const name = (m.meta?.provider_name as string) || "Synthesis";
    const nRounds = (m.meta?.rounds as number) || null;
    const nAgents = (m.meta?.n_agents as number) || null;
    return (
      <div className={cn("rounded-xl border px-4 py-3", ok ? "border-primary/40 bg-primary/5" : "border-warning/40 bg-warning/10")}>
        <div className="mb-1.5 flex flex-wrap items-center gap-x-2 gap-y-0.5">
          <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-primary/15 text-primary"><Crown size={13} /></span>
          <span className="text-[13px] font-semibold text-content">Final answer</span>
          <span className="text-[11px] text-content-subtle">· synthesized by {name}</span>
        </div>
        <p className={cn("whitespace-pre-wrap break-words text-sm leading-relaxed", ok ? "text-content" : "text-warning")}>{m.content}</p>
        {ok && nRounds ? (
          <p className="mt-2 text-[10.5px] text-content-subtle">
            From {nAgents ?? "the"} agents across {nRounds} round{nRounds > 1 ? "s" : ""} of debate.
          </p>
        ) : null}
      </div>
    );
  };

  const sidebarProps = {
    groups, sessions, activeId,
    onSelect: selectSession, onNewChat: newChat, onCreateGroup: createGroup,
    onRenameChat: renameChat, onDeleteChat: deleteChat, onMoveChat: moveChat,
    onRenameGroup: renameGroup, onDeleteGroup: deleteGroup,
  };

  return (
    <AppShell>
      <div className="flex h-[calc(100vh-7.5rem)] min-h-[520px] overflow-hidden rounded-2xl border border-border bg-surface/30">
        {/* Conversation sidebar (desktop) */}
        <div className="hidden w-72 shrink-0 border-r border-border lg:block">
          <ConversationSidebar {...sidebarProps} />
        </div>

        {/* Conversation drawer (mobile) */}
        {drawerOpen ? (
          <div className="fixed inset-0 z-50 lg:hidden">
            <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={() => setDrawerOpen(false)} />
            <div className="absolute inset-y-0 left-0 w-[82%] max-w-xs border-r border-border bg-surface">
              <ConversationSidebar {...sidebarProps} onCloseMobile={() => setDrawerOpen(false)} />
            </div>
          </div>
        ) : null}

        {/* Main thread */}
        <div className="flex min-w-0 flex-1 flex-col">
          {/* Header */}
          <div className="flex flex-col gap-2 border-b border-border px-4 py-3 sm:px-5">
            <div className="flex items-center gap-2.5">
              <button onClick={() => setDrawerOpen(true)} className="rounded-md p-1.5 text-content-muted hover:bg-surface-raised hover:text-content lg:hidden" aria-label="Open conversations">
                <PanelLeft size={17} />
              </button>
              <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
                <Sparkles size={16} />
              </span>
              <div className="min-w-0 leading-tight">
                <p className="truncate text-sm font-semibold text-content">{activeSession?.title || "New Chat"}</p>
                <p className="label-mono">AllHaven Multi-Agent · honest status</p>
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-x-2 gap-y-1.5">
              {/* Mode toggle: parallel fan-out vs multi-round debate. */}
              <div className="inline-flex shrink-0 items-center rounded-lg border border-border bg-surface-input p-0.5 text-[12.5px]">
                <button
                  type="button"
                  onClick={() => setMode("parallel")}
                  className={cn(
                    "flex items-center gap-1.5 rounded-md px-2.5 py-1 transition-colors",
                    mode === "parallel" ? "bg-surface-high text-content" : "text-content-muted hover:text-content",
                  )}
                >
                  <Layers size={13} /> Parallel
                </button>
                <button
                  type="button"
                  onClick={() => setMode("debate")}
                  className={cn(
                    "flex items-center gap-1.5 rounded-md px-2.5 py-1 transition-colors",
                    mode === "debate" ? "bg-surface-high text-primary" : "text-content-muted hover:text-content",
                  )}
                >
                  <Swords size={13} /> Debate
                </button>
              </div>
              {mode === "debate" ? (
                <div className="inline-flex shrink-0 items-center gap-1.5 text-[12px] text-content-muted">
                  <span>Rounds</span>
                  <div className="inline-flex rounded-lg border border-border bg-surface-input p-0.5">
                    {[2, 3].map((r) => (
                      <button
                        key={r}
                        type="button"
                        onClick={() => setRounds(r)}
                        className={cn(
                          "min-w-[28px] rounded-md px-2 py-1 transition-colors",
                          rounds === r ? "bg-surface-high text-content" : "text-content-muted hover:text-content",
                        )}
                      >
                        {r}
                      </button>
                    ))}
                  </div>
                </div>
              ) : null}
              {anyLocal ? <Badge tone="success"><Cpu size={11} className="mr-1 inline" /> Local AI</Badge> : null}
              {anyExternal ? <Badge tone="warning"><AlertTriangle size={11} className="mr-1 inline" /> External AI</Badge> : null}
            </div>
            <MultiAgentSelector
              providers={providers}
              selected={selected}
              onChange={setSelected}
              hint={mode === "debate" ? "they debate across rounds, then one synthesizes the final answer." : "they run at the same time."}
            />
          </div>

          {/* Messages */}
          <div className="custom-scrollbar flex-1 space-y-4 overflow-y-auto px-4 py-5 sm:px-6">
            {messages.length === 0 && !pendingUser ? (
              <div className="flex h-full flex-col items-center justify-center text-center">
                <span className="mb-3 flex h-12 w-12 items-center justify-center rounded-2xl bg-primary/10 text-primary">
                  <Bot size={22} />
                </span>
                <p className="text-[15px] font-semibold text-content">Start a conversation</p>
                <p className="mt-1 max-w-md text-[13px] text-content-muted">
                  Pick 1–3 agents and ask anything. In <span className="font-medium text-content">Parallel</span> mode each
                  agent answers independently; in <span className="font-medium text-content">Debate</span> mode they critique
                  each other across rounds and one synthesizes the best final answer. AllHaven never fabricates AI output.
                </p>
              </div>
            ) : (
              <>
                {thread.map((item) => {
                  if (item.kind === "round") {
                    return (
                      <div key={item.key} className="space-y-2">
                        <div className="flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-wide text-content-subtle">
                          <Swords size={12} className="text-primary" />
                          Round {item.round} · {item.phase === "opening" ? "Opening" : "Rebuttal"}
                        </div>
                        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
                          {item.items.map((m) => <AgentResponseCard key={m.id} data={toCard(m)} />)}
                        </div>
                      </div>
                    );
                  }
                  if (item.kind === "final") return <div key={item.key}>{renderFinal(item.message)}</div>;
                  return <div key={item.key}>{renderBubble(item.message)}</div>;
                })}

                {pendingUser ? (
                  <div className="flex flex-row-reverse gap-3">
                    <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-border bg-surface-high text-content"><User size={15} /></span>
                    <div className="max-w-[82%] rounded-xl border border-primary/30 bg-primary/10 px-3.5 py-2.5 text-sm text-content">
                      <p className="whitespace-pre-wrap break-words">{pendingUser}</p>
                    </div>
                  </div>
                ) : null}
                {sending ? (
                  <div className="flex gap-3">
                    <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-primary/30 bg-primary/10 text-primary"><Bot size={15} /></span>
                    <div className="rounded-xl border border-border bg-surface-input px-3.5 py-2.5 text-sm text-content-subtle">
                      <Loader2 size={14} className="mr-1.5 inline animate-spin" /> {mode === "debate" ? `${selected.length} agents debating across ${rounds} rounds…` : selected.length > 1 ? `${selected.length} agents thinking…` : "Thinking…"}
                    </div>
                  </div>
                ) : null}
              </>
            )}
            <div ref={endRef} />
          </div>

          {/* Input */}
          {anyExternal ? (
            <p className="mx-3 mb-1 flex items-start gap-1.5 rounded-md border border-warning/30 bg-warning/10 px-3 py-1.5 text-[11.5px] text-warning">
              <AlertTriangle size={12} className="mt-0.5 shrink-0" /> External AI may process your prompt. Don&apos;t send confidential data unless allowed in Settings.
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
        </div>
      </div>

      <p className="mt-2 px-1 text-center text-[11px] text-content-subtle lg:text-left">
        Conversations are saved to your workspace. <Link href="/dashboard/settings" className="text-primary hover:underline">Configure AI providers →</Link>
      </p>
    </AppShell>
  );
}
