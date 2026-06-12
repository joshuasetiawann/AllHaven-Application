"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { AlertTriangle, Bot, Cpu, Loader2, PanelLeft, SendHorizonal, Sparkles, User } from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { ConversationSidebar } from "@/components/ai/ConversationSidebar";
import { MultiAgentSelector } from "@/components/ai/MultiAgentSelector";
import { aiApi, ApiException } from "@/lib/api";
import { cn } from "@/lib/format";
import type { AiProvider, ChatGroup, ChatMessage, ChatSession } from "@/types";

export default function AiChatPage() {
  const [groups, setGroups] = useState<ChatGroup[]>([]);
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [providers, setProviders] = useState<AiProvider[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
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
      const run = await aiApi.multiChat(text, selected, activeId ?? undefined);
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
            <div className="flex flex-wrap items-center gap-2">
              <MultiAgentSelector providers={providers} selected={selected} onChange={setSelected} />
              {anyLocal ? <Badge tone="success"><Cpu size={11} className="mr-1 inline" /> Local AI</Badge> : null}
              {anyExternal ? <Badge tone="warning"><AlertTriangle size={11} className="mr-1 inline" /> External AI</Badge> : null}
            </div>
          </div>

          {/* Messages */}
          <div className="custom-scrollbar flex-1 space-y-4 overflow-y-auto px-4 py-5 sm:px-6">
            {messages.length === 0 && !pendingUser ? (
              <div className="flex h-full flex-col items-center justify-center text-center">
                <span className="mb-3 flex h-12 w-12 items-center justify-center rounded-2xl bg-primary/10 text-primary">
                  <Bot size={22} />
                </span>
                <p className="text-[15px] font-semibold text-content">Start a conversation</p>
                <p className="mt-1 max-w-sm text-[13px] text-content-muted">
                  Pick 1–3 agents and ask anything. Each agent answers in the thread. AllHaven never
                  fabricates AI output or executes actions on its own.
                </p>
              </div>
            ) : (
              <>
                {messages.map((m) => {
                  const isUser = m.role === "user";
                  const provider = (m.meta?.provider_name as string) || null;
                  const status = (m.meta?.status as string) || "";
                  const isError = !isUser && status && status !== "completed";
                  return (
                    <div key={m.id} className={cn("flex gap-3", isUser ? "flex-row-reverse" : "flex-row")}>
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
                      <Loader2 size={14} className="mr-1.5 inline animate-spin" /> {selected.length > 1 ? `${selected.length} agents thinking…` : "Thinking…"}
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
