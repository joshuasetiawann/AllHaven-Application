"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { AlertTriangle, BookOpenCheck, Bot, Brain, Crown, Cpu, Eye, FileText, Handshake, ImageOff, ImagePlus, Layers, Loader2, Mic, Paperclip, PanelLeft, SendHorizonal, Sparkles, Square, Swords, User, Wrench, X } from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { Toggle } from "@/components/ui/Toggle";
import { useAppDialog } from "@/components/ui/AppDialog";
import { ConversationSidebar } from "@/components/ai/ConversationSidebar";
import { MAX_AGENTS, MultiAgentSelector } from "@/components/ai/MultiAgentSelector";
import { AgentResponseCard, isSentinel, type AgentCardData } from "@/components/ai/AgentResponseCard";
import { MarkdownMessage } from "@/components/ai/MarkdownMessage";
import { PendingActionsPanel } from "@/components/ai/PendingActionsPanel";
import { MemoryIndicator } from "@/components/ai/MemoryIndicator";
import { SectionMemoryBar } from "@/components/ai/SectionMemoryBar";
import { aiApi, ApiException, knowledgeApi } from "@/lib/api";
import { cn } from "@/lib/format";
import { aiPrefsExist, loadAiPrefs, resolveSelection, saveAiPrefs, type ChatModePref } from "@/lib/aiPrefs";
import { loadPrefs } from "@/lib/prefs";
import { DEFAULT_SECTION_KEY, resolveSection } from "@/lib/sections";
import { buildContextPreface } from "@/lib/sectionMemory";
import type { AgentResponseStatus, AiChatSettings, AiProvider, ChatGroup, ChatMessage, ChatSession, ThinkingMode } from "@/types";

type ChatMode = ChatModePref;

// Map the persisted default_mode onto this page's modes ("single" = the
// one-agent parallel flow — there is no separate single-agent mode UI).
const MODE_FROM_SETTING: Record<AiChatSettings["default_mode"], ChatMode> = {
  single: "parallel",
  parallel: "parallel",
  debate: "debate",
  reasoning: "reason",
};

const THINKING_MODES: ThinkingMode[] = ["fast", "balance", "thinking", "deep"];

// Shown when a completed assistant/final message body is empty or a bare status
// sentinel (old/synced rows) instead of a real answer — see isSentinel().
const SENTINEL_PLACEHOLDER = "_(Tidak ada jawaban — coba kirim ulang.)_";

const ROLE_LABEL: Record<string, string> = { analyst: "Analyst", critic: "Critic", synthesis: "Synthesizer", synthesizer: "Synthesizer" };

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
    role: (meta.role as string) ?? null,
  };
}

// Attached image data URLs persisted on a message's metadata.
function imagesOf(m: ChatMessage): string[] {
  const imgs = ((m.meta ?? {}) as Record<string, unknown>).images;
  return Array.isArray(imgs) ? (imgs as string[]) : [];
}

// AI tool calls recorded on an assistant message's metadata.
type ToolCallMeta = { tool: string; status: string; summary?: string };

function toolCallsOf(m: ChatMessage): ToolCallMeta[] {
  const calls = ((m.meta ?? {}) as Record<string, unknown>).tool_calls;
  return Array.isArray(calls) ? (calls as ToolCallMeta[]) : [];
}

// Honest tool-activity chip styling per outcome (mirrors Badge tones).
const TOOL_CHIP: Record<string, { cls: string; label: string }> = {
  executed: { cls: "border-success/30 bg-success/10 text-success", label: "executed" },
  pending_approval: { cls: "border-warning/30 bg-warning/10 text-warning", label: "pending approval" },
  error: { cls: "border-danger/30 bg-danger/10 text-danger", label: "error" },
};

const MAX_IMAGES = 4;
const MAX_KNOWLEDGE_ATTACHMENTS = 5;

type KnowledgeAttachment = {
  id: string;
  title: string;
  filename: string;
  status: string;
  chunk_count: number;
};

type ThreadItem =
  | { kind: "user"; key: string; message: ChatMessage }
  | { kind: "agent"; key: string; message: ChatMessage }
  | { kind: "final"; key: string; message: ChatMessage }
  | { kind: "rolecard"; key: string; message: ChatMessage }
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
    } else if ((meta.debate && meta.debate_final) || (meta.reasoning && meta.reasoning_final)) {
      items.push({ kind: "final", key: m.id, message: m });
      i += 1;
    } else if (meta.reasoning) {
      items.push({ kind: "rolecard", key: m.id, message: m });
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
  const dialog = useAppDialog();
  const [groups, setGroups] = useState<ChatGroup[]>([]);
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [providers, setProviders] = useState<AiProvider[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [mode, setMode] = useState<ChatMode>("parallel");
  const [rounds, setRounds] = useState(2);
  const [thinking, setThinking] = useState<ThinkingMode>("balance");
  const [debug, setDebug] = useState(false);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [pendingUser, setPendingUser] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [images, setImages] = useState<string[]>([]);
  const [pendingImages, setPendingImages] = useState<string[]>([]);
  const [knowledgeAttachments, setKnowledgeAttachments] = useState<KnowledgeAttachment[]>([]);
  const [uploadingKnowledge, setUploadingKnowledge] = useState(false);
  const [listening, setListening] = useState(false);
  const [chatSettings, setChatSettings] = useState<AiChatSettings | null>(null);
  const [proposalRefresh, setProposalRefresh] = useState(0);
  const [memoryRefreshKey, setMemoryRefreshKey] = useState(0);
  // Active chat "section" (each keeps its own local memory) + model-availability notice.
  const [section, setSection] = useState<string>(DEFAULT_SECTION_KEY);
  const [availabilityWarn, setAvailabilityWarn] = useState<string | null>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const knowledgeFileRef = useRef<HTMLInputElement>(null);
  const recognitionRef = useRef<{ stop?: () => void; abort?: () => void } | null>(null);
  const voiceBaseRef = useRef("");
  // Sessions+sections we've already seeded with section memory (inject once per thread).
  const prefacedRef = useRef<Set<string>>(new Set());

  // --- persisted selection (Part 4): never make the user re-pick on nav/refresh ---
  const changeSelected = (ids: string[]) => {
    setSelected(ids);
    saveAiPrefs({ selected_agent_ids: ids });
    if (ids.length) setAvailabilityWarn(null);
  };
  const changeMode = (m: ChatMode) => {
    setMode(m);
    saveAiPrefs({ chat_mode: m });
  };
  const changeThinking = (t: ThinkingMode) => {
    setThinking(t);
    saveAiPrefs({ thinking: t });
  };
  const changeRounds = (r: number) => {
    setRounds(r);
    saveAiPrefs({ rounds: r });
  };
  const changeSection = (k: string) => {
    setSection(k);
    saveAiPrefs({ section_key: k });
  };

  const providerById = useMemo(() => Object.fromEntries(providers.map((p) => [p.id, p])), [providers]);
  // Selected values are slot refs ("anthropic#2" = slot 2); the provider id is the part before "#".
  const providerOfRef = (ref: string) => providerById[ref.split("#")[0]];
  const anyExternal = selected.some((ref) => providerOfRef(ref)?.external);
  const anyLocal = selected.some((ref) => { const p = providerOfRef(ref); return p && !p.external; });
  // Image attached but one or more selected models can't read images (vision).
  const visionMissing = images.length > 0 && selected.some((ref) => { const p = providerOfRef(ref); return p && !p.capabilities?.image; });
  const visionOk = images.length > 0 && !visionMissing;
  const activeSession = sessions.find((s) => s.id === activeId) || null;
  const thread = useMemo(() => buildThread(messages), [messages]);
  const showDebateFlow = chatSettings?.show_debate_flow !== false;
  const showToolActivity = chatSettings?.show_tool_activity !== false;
  const threadHasDebate = useMemo(
    () => thread.some((t) => t.kind === "round" || (t.kind === "final" && Boolean(((t.message.meta ?? {}) as Record<string, unknown>).debate))),
    [thread],
  );

  const refreshSessions = async () => {
    try { setSessions(await aiApi.listSessions()); } catch { /* non-blocking */ }
  };
  const refreshGroups = async () => {
    try { setGroups(await aiApi.listGroups()); } catch { /* non-blocking */ }
  };

  useEffect(() => {
    void refreshSessions();
    void refreshGroups();

    // Restore the user's last-used selection/mode/section (Part 4) up front, so a
    // refresh or navigation never resets their choice.
    const prefs = loadAiPrefs();
    const hadPrefs = aiPrefsExist();
    setMode(prefs.chat_mode);
    setThinking(prefs.thinking);
    setRounds(prefs.rounds);
    setSection(prefs.section_key);

    aiApi.listProviders()
      .then((res) => {
        setProviders(res.providers);
        // Reconcile the saved agents against what's actually available now,
        // falling back (with a clear notice) if a saved model disappeared.
        const status = resolveSelection(loadAiPrefs().selected_agent_ids, res.providers);
        setSelected(status.selected);
        setAvailabilityWarn(status.kind === "ok" ? null : status.message);
        if (status.selected.length) saveAiPrefs({ selected_agent_ids: status.selected });
      })
      .catch(() => {});

    // Chat behavior settings: debate-flow/tool-activity visibility + default mode.
    aiApi.getChatSettings()
      .then((s) => {
        setChatSettings(s);
        // The workspace default mode only wins on a fresh device with no saved choice.
        if (!hadPrefs) {
          const m = MODE_FROM_SETTING[s.default_mode] ?? "parallel";
          setMode(m);
          saveAiPrefs({ chat_mode: m });
        }
      })
      .catch(() => {});
  }, []);

  // Load the active conversation's messages.
  useEffect(() => {
    if (!activeId) { setMessages([]); return; }
    let on = true;
    aiApi.listMessages(activeId)
      .then((m) => {
        if (!on) return;
        setMessages(m);
        // Replies that filed tool proposals mean the pending-actions list changed.
        if (m.some((x) => { const ids = ((x.meta ?? {}) as Record<string, unknown>).proposal_ids; return Array.isArray(ids) && ids.length > 0; })) {
          setProposalRefresh((n) => n + 1);
        }
      })
      .catch(() => on && setMessages([]));
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
    const t = await dialog.prompt({
      title: "Rename conversation",
      message: "Give this chat a clear title.",
      defaultValue: s.title || "",
      confirmLabel: "Rename",
      placeholder: "Conversation title",
    });
    if (t == null) return;
    const title = t.trim();
    if (!title) return;
    await aiApi.updateSession(s.id, { title }).catch(() => {});
    void refreshSessions();
  };
  const deleteChat = async (s: ChatSession) => {
    const ok = await dialog.confirm({
      title: "Delete conversation?",
      message: `Delete "${s.title || "New Chat"}"? This cannot be undone.`,
      confirmLabel: "Delete",
      tone: "danger",
    });
    if (!ok) return;
    await aiApi.deleteSession(s.id).catch(() => {});
    if (activeId === s.id) { setActiveId(null); setMessages([]); }
    void refreshSessions();
  };
  const moveChat = async (s: ChatSession, groupId: string | null) => {
    await aiApi.updateSession(s.id, { group_id: groupId }).catch(() => {});
    void refreshSessions();
  };
  const createGroup = async () => {
    const name = await dialog.prompt({
      title: "New group",
      message: "Create a group to organize related chats.",
      confirmLabel: "Create group",
      placeholder: "Group name",
    });
    if (!name || !name.trim()) return;
    await aiApi.createGroup(name.trim()).catch(() => {});
    void refreshGroups();
  };
  const renameGroup = async (g: ChatGroup) => {
    const name = await dialog.prompt({
      title: "Rename group",
      message: "Update this chat group name.",
      defaultValue: g.name,
      confirmLabel: "Rename",
      placeholder: "Group name",
    });
    if (name == null || !name.trim()) return;
    await aiApi.renameGroup(g.id, name.trim()).catch(() => {});
    void refreshGroups();
  };
  const deleteGroup = async (g: ChatGroup) => {
    const ok = await dialog.confirm({
      title: "Delete group?",
      message: `Delete group "${g.name}"? Its chats are kept and moved out of the group.`,
      confirmLabel: "Delete group",
      tone: "danger",
    });
    if (!ok) return;
    await aiApi.deleteGroup(g.id).catch(() => {});
    void refreshGroups();
    void refreshSessions();
  };

  // Flip debate-flow visibility optimistically; revert with the API error if the save fails.
  const toggleDebateFlow = async (next: boolean) => {
    if (!chatSettings) return;
    const prev = chatSettings;
    setChatSettings({ ...prev, show_debate_flow: next });
    try {
      setChatSettings(await aiApi.setChatSettings({ show_debate_flow: next }));
    } catch (err) {
      setChatSettings(prev);
      setError(err instanceof ApiException ? err.message : "Could not update chat settings.");
    }
  };

  // --- image attachments ---
  const readAsDataURL = (file: File) => new Promise<string>((res, rej) => {
    const r = new FileReader();
    r.onload = () => res(String(r.result));
    r.onerror = () => rej(new Error("read failed"));
    r.readAsDataURL(file);
  });
  // Downscale large images client-side so the payload stays reasonable.
  const downscale = (dataUrl: string, max = 1280) => new Promise<string>((res) => {
    const img = new window.Image();
    img.onload = () => {
      const scale = Math.min(1, max / Math.max(img.width, img.height));
      if (scale >= 1) return res(dataUrl);
      const c = document.createElement("canvas");
      c.width = Math.round(img.width * scale);
      c.height = Math.round(img.height * scale);
      const ctx = c.getContext("2d");
      if (!ctx) return res(dataUrl);
      ctx.drawImage(img, 0, 0, c.width, c.height);
      res(c.toDataURL("image/jpeg", 0.85));
    };
    img.onerror = () => res(dataUrl);
    img.src = dataUrl;
  });
  const addImages = async (files: FileList | File[] | null) => {
    if (!files) return;
    setError(null);
    const room = MAX_IMAGES - images.length;
    if (room <= 0) { setError(`You can attach up to ${MAX_IMAGES} images.`); return; }
    const picks = Array.from(files).filter((f) => f.type.startsWith("image/")).slice(0, room);
    const out: string[] = [];
    for (const f of picks) {
      try {
        const url = await downscale(await readAsDataURL(f));
        if (url.length > 6_000_000) { setError("An image is too large even after resizing."); continue; }
        out.push(url);
      } catch { /* skip unreadable file */ }
    }
    if (out.length) setImages((cur) => [...cur, ...out]);
    if (fileRef.current) fileRef.current.value = "";
  };
  const removeImage = (idx: number) => setImages((cur) => cur.filter((_, i) => i !== idx));

  const addKnowledgeFiles = async (files: FileList | File[] | null) => {
    if (!files) return;
    const room = MAX_KNOWLEDGE_ATTACHMENTS - knowledgeAttachments.length;
    if (room <= 0) {
      setError(`You can attach up to ${MAX_KNOWLEDGE_ATTACHMENTS} knowledge files per message.`);
      return;
    }
    const picks = Array.from(files).filter((f) => !f.type.startsWith("image/")).slice(0, room);
    if (!picks.length) return;
    setUploadingKnowledge(true);
    setError(null);
    const uploaded: KnowledgeAttachment[] = [];
    for (const file of picks) {
      try {
        const doc = await knowledgeApi.uploadDocument(file);
        uploaded.push({
          id: doc.id,
          title: doc.title,
          filename: doc.filename,
          status: doc.status,
          chunk_count: doc.chunk_count,
        });
      } catch (err) {
        setError(err instanceof ApiException ? err.message : `Could not upload ${file.name}.`);
      }
    }
    if (uploaded.length) setKnowledgeAttachments((cur) => [...cur, ...uploaded]);
    setUploadingKnowledge(false);
    if (knowledgeFileRef.current) knowledgeFileRef.current.value = "";
  };
  const removeKnowledgeAttachment = (idx: number) => setKnowledgeAttachments((cur) => cur.filter((_, i) => i !== idx));

  const toggleVoiceNote = () => {
    if (listening) {
      recognitionRef.current?.stop?.();
      recognitionRef.current = null;
      setListening(false);
      return;
    }
    const w = window as typeof window & {
      SpeechRecognition?: new () => any;
      webkitSpeechRecognition?: new () => any;
    };
    const SpeechRecognition = w.SpeechRecognition || w.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      setError("Voice note belum didukung di browser ini. Coba Chrome/Edge, atau ketik manual.");
      return;
    }
    const recognition = new SpeechRecognition();
    recognitionRef.current = recognition;
    voiceBaseRef.current = input.trim();
    const lang = loadPrefs().language;
    recognition.lang = lang === "en" ? "en-US" : lang === "zh-Hant" ? "zh-TW" : "id-ID";
    recognition.interimResults = true;
    recognition.continuous = false;
    recognition.onresult = (event: any) => {
      let transcript = "";
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        transcript += event.results[i][0]?.transcript ?? "";
      }
      const base = voiceBaseRef.current;
      setInput([base, transcript.trim()].filter(Boolean).join(" ").trimStart());
    };
    recognition.onerror = () => {
      setError("Voice note gagal diproses. Cek izin microphone lalu coba lagi.");
      setListening(false);
    };
    recognition.onend = () => {
      setListening(false);
      recognitionRef.current = null;
    };
    try {
      recognition.start();
      setListening(true);
      setError(null);
    } catch {
      setError("Voice note belum bisa dimulai. Coba izinkan microphone lalu ulangi.");
      setListening(false);
    }
  };

  // --- send ---
  const send = async (event: React.FormEvent) => {
    event.preventDefault();
    const text = input.trim();
    const imgs = images;
    const docs = knowledgeAttachments;
    if ((!text && imgs.length === 0 && docs.length === 0) || sending || uploadingKnowledge) return;
    if (selected.length === 0) { setError("Select at least one AI agent."); return; }
    const msg = text || (docs.length ? "Baca dan gunakan file yang saya lampirkan." : "Describe the attached image(s).");
    setError(null);
    setSending(true);
    setPendingUser(msg);
    setPendingImages(imgs);
    setInput("");
    setImages([]);
    setKnowledgeAttachments([]);
    // Section memory (Part 3): seed the active section's saved context into the
    // thread once, so answers stay relevant without repeating it every turn.
    const memoryKey = `${activeId ?? "new"}:${section}`;
    const preface = prefacedRef.current.has(memoryKey)
      ? null
      : buildContextPreface(section, resolveSection(section, groups).label);
    const knowledgeNote = docs.length
      ? [
          "[Attached AI Knowledge files this turn]",
          ...docs.map((doc) => `- ${doc.title} (${doc.filename}) status=${doc.status}, chunks=${doc.chunk_count}`),
          "Use AI Knowledge retrieval/search tools before answering questions about these files.",
        ].join("\n")
      : null;
    const sendText = [
      preface,
      knowledgeNote,
      preface || knowledgeNote ? `User message:\n${msg}` : msg,
    ].filter(Boolean).join("\n\n");
    const responseLanguage = loadPrefs().language;
    try {
      const run = mode === "debate"
        ? await aiApi.debateChat(sendText, selected, activeId ?? undefined, rounds, imgs, thinking, section, responseLanguage)
        : mode === "reason"
          ? await aiApi.reasonChat(sendText, selected, activeId ?? undefined, thinking, imgs, section, responseLanguage)
          : await aiApi.multiChat(sendText, selected, activeId ?? undefined, imgs, thinking, section, responseLanguage);
      setActiveId(run.session_id);
      prefacedRef.current.add(`${run.session_id}:${section}`);
      const msgs = await aiApi.listMessages(run.session_id);
      setMessages(msgs);
      void refreshSessions();
    } catch (err) {
      setError(err instanceof ApiException ? err.message : "Failed to send message.");
    } finally {
      setSending(false);
      setPendingUser(null);
      setPendingImages([]);
      // The reply may have filed tool proposals — refresh the pending-actions panel.
      setProposalRefresh((n) => n + 1);
      // Trigger the in-chat memory indicator to check for new/pending memories.
      setMemoryRefreshKey((n) => n + 1);
    }
  };

  // --- thread rendering ---
  const renderBubble = (m: ChatMessage) => {
    const isUser = m.role === "user";
    const provider = (m.meta?.provider_name as string) || null;
    const agentRole = !isUser ? ((m.meta?.role as string) || null) : null;
    const status = (m.meta?.status as string) || "";
    const isError = !isUser && status && status !== "completed";
    const imgs = isUser ? imagesOf(m) : [];
    const toolCalls = !isUser && showToolActivity ? toolCallsOf(m) : [];
    const usedMemory = !isUser && Boolean(m.meta?.used_memory);
    const usedKnowledge = !isUser && Boolean(m.meta?.used_knowledge);
    const activeTools = Array.isArray(m.meta?.active_tools) ? (m.meta?.active_tools as string[]) : [];
    const visibleActiveTools = activeTools.slice(0, 2);
    const hiddenActiveToolCount = Math.max(0, activeTools.length - visibleActiveTools.length);
    const visibleToolCalls = toolCalls.slice(0, 2);
    const hiddenToolCallCount = Math.max(0, toolCalls.length - visibleToolCalls.length);
    return (
      <div className={cn("flex gap-2.5", isUser ? "flex-row-reverse" : "flex-row")}>
        <span className={cn(
          "flex h-7 w-7 shrink-0 items-center justify-center rounded-lg border",
          isUser ? "border-border bg-surface-high text-content" : "border-primary/30 bg-primary/10 text-primary",
        )}>
          {isUser ? <User size={14} /> : <Bot size={14} />}
        </span>
        <div className="min-w-0 max-w-[86%] sm:max-w-[44rem]">
          {provider && !isUser ? (
            <p className="mb-0.5 flex items-center gap-1.5 text-[10.5px] font-medium uppercase tracking-wide text-content-subtle">
              {provider}
              {agentRole ? <Badge tone="neutral" className="normal-case tracking-normal">{agentRole}</Badge> : null}
            </p>
          ) : null}
          <div className={cn(
            "rounded-xl border px-3.5 py-2.5 text-sm leading-relaxed",
            isUser ? "border-primary/30 bg-primary/10 text-content"
              : isError ? "border-warning/30 bg-warning/10 text-warning"
              : "border-border bg-surface-input text-content",
          )}>
            {imgs.length ? (
              <div className={cn("flex flex-wrap gap-2", m.content ? "mb-2" : "")}>
                {imgs.map((src, i) => (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img key={i} src={src} alt="attachment" className="max-h-44 max-w-[160px] rounded-lg border border-border object-cover" />
                ))}
              </div>
            ) : null}
            {isUser || isError ? (
              <p className="whitespace-pre-wrap break-words">{m.content}</p>
            ) : (
              <MarkdownMessage content={isSentinel(m.content) ? SENTINEL_PLACEHOLDER : m.content} />
            )}
          </div>
          {usedMemory || usedKnowledge || activeTools.length ? (
            <div className="mt-1.5 flex flex-wrap gap-1.5">
              {usedMemory ? (
                <span className="inline-flex items-center gap-1 rounded-md border border-primary/30 bg-primary/10 px-2 py-0.5 text-[10.5px] font-medium text-primary">
                  <Brain size={10} /> used memory
                </span>
              ) : null}
              {usedKnowledge ? (
                <span className="inline-flex items-center gap-1 rounded-md border border-success/30 bg-success/10 px-2 py-0.5 text-[10.5px] font-medium text-success">
                  <BookOpenCheck size={10} /> used knowledge
                </span>
              ) : null}
              {visibleActiveTools.map((name) => (
                <span key={name} className="inline-flex items-center gap-1 rounded-md border border-border bg-surface-high px-2 py-0.5 text-[10.5px] font-medium text-content-subtle">
                  <Wrench size={10} /> {name.replace(/_/g, " ")}
                </span>
              ))}
              {hiddenActiveToolCount ? (
                <span className="inline-flex items-center rounded-md border border-border bg-surface-high px-2 py-0.5 text-[10.5px] font-medium text-content-subtle">
                  +{hiddenActiveToolCount} tools
                </span>
              ) : null}
            </div>
          ) : null}
          {toolCalls.length ? (
            <div className="mt-1.5 flex flex-wrap gap-1.5">
              {visibleToolCalls.map((tc, i) => {
                const chip = TOOL_CHIP[tc.status] ?? { cls: "border-border bg-surface-high text-content-muted", label: tc.status.replace(/_/g, " ") };
                return (
                  <span
                    key={i}
                    title={tc.summary || undefined}
                    className={cn("inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-[10.5px] font-medium", chip.cls)}
                  >
                    <Wrench size={10} /> {tc.tool.replace(/_/g, " ")} · {chip.label}
                  </span>
                );
              })}
              {hiddenToolCallCount ? (
                <span className="inline-flex items-center rounded-md border border-border bg-surface-high px-2 py-0.5 text-[10.5px] font-medium text-content-subtle">
                  +{hiddenToolCallCount} more
                </span>
              ) : null}
            </div>
          ) : null}
        </div>
      </div>
    );
  };

  // Compact summary shown instead of the full debate transcript, e.g. "5 agents · 2 rounds collaborated".
  const collabLine = (m: ChatMessage): string | null => {
    const meta = (m.meta ?? {}) as Record<string, unknown>;
    let agents = Number(meta.n_agents ?? 0);
    let rounds = Number(meta.rounds ?? 0);
    if (!agents || !rounds) {
      const turns = messages.filter((x) => {
        const xm = (x.meta ?? {}) as Record<string, unknown>;
        return Boolean(xm.debate) && !xm.debate_final && xm.run_id === meta.run_id;
      });
      if (!agents) agents = new Set(turns.map((x) => String(((x.meta ?? {}) as Record<string, unknown>).provider_id ?? ""))).size;
      if (!rounds) rounds = turns.reduce((max, x) => Math.max(max, Number(((x.meta ?? {}) as Record<string, unknown>).round ?? 1)), 0);
    }
    if (!agents && !rounds) return null;
    const agentPart = agents > 0 ? `${agents} agent${agents === 1 ? "" : "s"}` : "Agents";
    return rounds > 0 ? `${agentPart} · ${rounds} round${rounds === 1 ? "" : "s"} collaborated` : `${agentPart} collaborated`;
  };

  const renderFinal = (m: ChatMessage, collapsed = false) => {
    const meta = (m.meta ?? {}) as Record<string, unknown>;
    const status = (meta.status as string) || "completed";
    const ok = status === "completed";
    const name = (meta.provider_name as string) || "Synthesis";
    const isReasoning = Boolean(meta.reasoning);
    const quality = (meta.quality ?? null) as Record<string, number> | null;
    const conf = quality && quality.final_answer_confidence != null ? Number(quality.final_answer_confidence) : null;
    const issues = (Array.isArray(quality?.issues) ? (quality!.issues as unknown as string[]) : []);
    const summary = (meta.reasoning_summary as string) || "";
    const lowConf = ok && isReasoning && ((conf != null && conf < 0.55) || issues.length > 0);
    const nRounds = (meta.rounds as number) || null;
    const nAgents = (meta.n_agents as number) || null;
    return (
      <div className={cn("rounded-xl border px-4 py-3", ok ? "border-primary/40 bg-primary/5" : "border-warning/40 bg-warning/10")}>
        <div className="mb-1.5 flex flex-wrap items-center gap-x-2 gap-y-0.5">
          <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-primary/15 text-primary"><Crown size={13} /></span>
          <span className="text-[13px] font-semibold text-content">Final answer</span>
          <span className="text-[11px] text-content-subtle">· by {name}</span>
          {isReasoning && debug && conf != null ? (
            <Badge tone={conf >= 0.7 ? "success" : conf >= 0.55 ? "primary" : "warning"} className="ml-1">
              {Math.round(conf * 100)}% confidence
            </Badge>
          ) : null}
        </div>
        {ok ? (
          <MarkdownMessage content={isSentinel(m.content) ? SENTINEL_PLACEHOLDER : m.content} className="text-sm text-content" />
        ) : (
          <p className="whitespace-pre-wrap break-words text-sm leading-relaxed text-warning">{m.content}</p>
        )}
        {lowConf ? (
          <p className="mt-2 flex items-start gap-1.5 rounded-md border border-warning/30 bg-warning/10 px-2.5 py-1.5 text-[11.5px] text-warning">
            <AlertTriangle size={12} className="mt-0.5 shrink-0" />
            <span>
              This answer may be low-confidence or rely on assumptions{issues.length ? `: ${issues.slice(0, 2).join("; ")}` : ""}. Verify before relying on it.
            </span>
          </p>
        ) : null}
        {isReasoning && debug && summary ? (
          <p className="mt-2 text-[11.5px] text-content-subtle">
            <span className="font-medium text-content-muted">Reasoning:</span> {summary}
          </p>
        ) : null}
        {isReasoning && debug && quality ? (
          <div className="mt-2 flex flex-wrap gap-x-3 gap-y-0.5 text-[10.5px] text-content-subtle">
            <span>relevance {Math.round(Number(quality.input_relevance_score) * 100)}%</span>
            <span>grounding {Math.round(Number(quality.grounding_score) * 100)}%</span>
            <span>calc {Math.round(Number(quality.calculation_check_score) * 100)}%</span>
            <span>hallucination risk {Math.round(Number(quality.hallucination_risk) * 100)}%</span>
          </div>
        ) : null}
        {!isReasoning && ok && nRounds && !collapsed ? (
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
      <div className="flex h-[calc(100svh-5.75rem)] min-h-[500px] overflow-hidden rounded-xl border border-border bg-surface/30 sm:h-[calc(100vh-7.5rem)] sm:min-h-[520px] sm:rounded-2xl">
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
            <div className="flex min-w-0 flex-wrap items-center gap-2.5">
              <button onClick={() => setDrawerOpen(true)} className="rounded-md p-1.5 text-content-muted transition-colors hover:bg-surface-raised hover:text-content lg:hidden" aria-label="Open conversations">
                <PanelLeft size={17} />
              </button>
              <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
                <Sparkles size={16} />
              </span>
              <div className="min-w-0 flex-1 leading-tight">
                <p className="truncate text-sm font-semibold text-content">{activeSession?.title || "New Chat"}</p>
                <p className="label-mono">AllHaven Multi-Agent · honest status</p>
              </div>
              <div className="flex min-w-0 flex-1 flex-wrap items-center justify-end gap-2 sm:flex-none">
                <SectionMemoryBar
                  sectionKey={section}
                  groups={groups}
                  onSectionChange={changeSection}
                  onMemoryChange={() => {
                    // Memory edited — allow it to re-seed the active thread on next send.
                    prefacedRef.current.delete(`${activeId ?? "new"}:${section}`);
                  }}
                />
                <MemoryIndicator refreshKey={memoryRefreshKey} />
              </div>
            </div>
            <div className="custom-scrollbar -mx-1 flex overflow-x-auto px-1 pb-1 sm:mx-0 sm:flex-wrap sm:overflow-visible sm:px-0 sm:pb-0">
              <div className="flex min-w-max items-center gap-x-2 gap-y-1.5 sm:min-w-0 sm:flex-wrap">
              {/* Mode toggle: parallel fan-out vs multi-round debate. */}
              <div className="inline-flex shrink-0 items-center rounded-lg border border-border bg-surface-input p-0.5 text-[12.5px]">
                <button
                  type="button"
                  onClick={() => changeMode("parallel")}
                  className={cn(
                    "flex items-center gap-1.5 rounded-md px-2.5 py-1 transition-colors",
                    mode === "parallel" ? "bg-surface-high text-content" : "text-content-muted hover:text-content",
                  )}
                >
                  <Layers size={13} /> Parallel
                </button>
                <button
                  type="button"
                  onClick={() => changeMode("debate")}
                  className={cn(
                    "flex items-center gap-1.5 rounded-md px-2.5 py-1 transition-colors",
                    mode === "debate" ? "bg-surface-high text-primary" : "text-content-muted hover:text-content",
                  )}
                >
                  <Swords size={13} /> Debate
                </button>
                <button
                  type="button"
                  onClick={() => changeMode("reason")}
                  className={cn(
                    "flex items-center gap-1.5 rounded-md px-2.5 py-1 transition-colors",
                    mode === "reason" ? "bg-surface-high text-primary" : "text-content-muted hover:text-content",
                  )}
                >
                  <Brain size={13} /> Reasoning
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
                        onClick={() => changeRounds(r)}
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
              {mode === "reason" ? (
                <button
                  type="button"
                  onClick={() => setDebug((v) => !v)}
                  className={cn(
                    "shrink-0 rounded-md border px-2 py-1 text-[12px] transition-colors",
                    debug ? "border-primary/40 bg-primary/10 text-primary" : "border-border text-content-muted hover:text-content",
                  )}
                >
                  Debug
                </button>
              ) : null}
              {(mode === "debate" || threadHasDebate) && chatSettings ? (
                <label className="flex shrink-0 items-center gap-1.5 text-[12px] text-content-muted">
                  <Toggle
                    checked={chatSettings.show_debate_flow}
                    onChange={(next) => void toggleDebateFlow(next)}
                    label="Show debate flow"
                  />
                  Show debate flow
                </label>
              ) : null}
              {anyLocal ? <Badge tone="success"><Cpu size={11} className="mr-1 inline" /> Local AI</Badge> : null}
              {anyExternal ? <Badge tone="warning"><AlertTriangle size={11} className="mr-1 inline" /> External AI</Badge> : null}
              </div>
            </div>
            <MultiAgentSelector
              providers={providers}
              selected={selected}
              onChange={changeSelected}
              hint={mode === "debate" ? "they debate across rounds, then one synthesizes the final answer."
                : mode === "reason" ? "they take roles (Analyst → Critic → Synthesizer) with grounded, verified reasoning."
                : "they run at the same time."}
            />
          </div>

          {/* Messages */}
          <div
            className="custom-scrollbar flex-1 space-y-4 overflow-y-auto px-3 py-4 sm:px-6 sm:py-5"
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => {
              e.preventDefault();
              const files = Array.from(e.dataTransfer.files);
              void addImages(files);
              void addKnowledgeFiles(files);
            }}
          >
            {messages.length === 0 && !pendingUser ? (
              <div className="flex h-full animate-fade-in flex-col items-center justify-center text-center">
                <span className="mb-3 flex h-12 w-12 items-center justify-center rounded-2xl bg-primary/10 text-primary">
                  <Bot size={22} />
                </span>
                <p className="text-[15px] font-semibold text-content">Start a conversation</p>
                <p className="mt-1 max-w-md text-[13px] text-content-muted">
                  Pick 1–{MAX_AGENTS} agents and ask anything. In <span className="font-medium text-content">Parallel</span> mode each
                  agent answers independently; in <span className="font-medium text-content">Debate</span> mode they critique
                  each other across rounds and one synthesizes the best final answer. AllHaven never fabricates AI output.
                </p>
              </div>
            ) : (
              <>
                {thread.map((item) => {
                  if (item.kind === "round") {
                    // Debate flow hidden: skip the per-round transcript (display filter only — nothing is deleted).
                    if (!showDebateFlow) return null;
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
                  if (item.kind === "rolecard") {
                    // Reasoning role turns (Analyst/Critic) are detail — show only in Debug.
                    if (!debug) return null;
                    const rmeta = (item.message.meta ?? {}) as Record<string, unknown>;
                    const label = ROLE_LABEL[String(rmeta.phase || "")] || "Agent";
                    return (
                      <div key={item.key} className="space-y-1.5">
                        <div className="flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-wide text-content-subtle">
                          <Brain size={12} className="text-primary" /> {label}
                        </div>
                        <AgentResponseCard data={toCard(item.message)} />
                      </div>
                    );
                  }
                  if (item.kind === "final") {
                    const fmeta = (item.message.meta ?? {}) as Record<string, unknown>;
                    const collapsed = !showDebateFlow && Boolean(fmeta.debate);
                    const collab = collapsed ? collabLine(item.message) : null;
                    return (
                      <div key={item.key} className={collab ? "space-y-1.5" : undefined}>
                        {collab ? (
                          <p className="flex items-center gap-1.5 text-[11px] text-content-subtle">
                            <Handshake size={12} className="text-primary" /> {collab}
                          </p>
                        ) : null}
                        {renderFinal(item.message, collapsed)}
                      </div>
                    );
                  }
                  return <div key={item.key} className="animate-fade-in">{renderBubble(item.message)}</div>;
                })}

                {pendingUser ? (
                  <div className="flex animate-fade-in flex-row-reverse gap-3">
                    <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-border bg-surface-high text-content"><User size={15} /></span>
                    <div className="max-w-[86%] rounded-xl border border-primary/30 bg-primary/10 px-3.5 py-2.5 text-sm text-content sm:max-w-[82%]">
                      {pendingImages.length ? (
                        <div className="mb-2 flex flex-wrap gap-2">
                          {pendingImages.map((src, i) => (
                            // eslint-disable-next-line @next/next/no-img-element
                            <img key={i} src={src} alt="attachment" className="max-h-44 max-w-[160px] rounded-lg border border-border object-cover" />
                          ))}
                        </div>
                      ) : null}
                      <p className="whitespace-pre-wrap break-words">{pendingUser}</p>
                    </div>
                  </div>
                ) : null}
                {sending ? (
                  <div className="flex animate-fade-in gap-3">
                    <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-primary/30 bg-primary/10 text-primary"><Bot size={15} /></span>
                    <div className="rounded-xl border border-border bg-surface-input px-3.5 py-2.5 text-sm text-content-subtle">
                      <Loader2 size={14} className="mr-1.5 inline animate-spin" /> {mode === "reason" ? "Reasoning…" : mode === "debate" ? `${selected.length} agents debating across ${rounds} rounds…` : selected.length > 1 ? `${selected.length} agents thinking…` : "Thinking…"}
                    </div>
                  </div>
                ) : null}
              </>
            )}
            <div ref={endRef} />
          </div>

          {/* Pending actions: AI-proposed writes awaiting human approval. */}
          <PendingActionsPanel refreshKey={proposalRefresh} />

          {/* Input */}
          {availabilityWarn ? (
            <p className="mx-3 mb-1 flex items-start gap-1.5 rounded-md border border-warning/30 bg-warning/10 px-3 py-1.5 text-[11.5px] text-warning">
              <AlertTriangle size={12} className="mt-0.5 shrink-0" />
              <span>
                {availabilityWarn}{" "}
                <Link href="/dashboard/settings" className="font-medium underline hover:text-content">Open AI settings →</Link>
              </span>
            </p>
          ) : null}
          {anyExternal ? (
            <p className="mx-3 mb-1 flex items-start gap-1.5 rounded-md border border-warning/30 bg-warning/10 px-3 py-1.5 text-[11.5px] text-warning">
              <AlertTriangle size={12} className="mt-0.5 shrink-0" /> External AI may process your prompt. Don&apos;t send confidential data unless allowed in Settings.
            </p>
          ) : null}
          {visionMissing ? (
            <p className="mx-3 mb-1 flex items-start gap-1.5 rounded-md border border-warning/30 bg-warning/10 px-3 py-1.5 text-[11.5px] text-warning">
              <ImageOff size={12} className="mt-0.5 shrink-0" /> Some selected models can&apos;t read images — they&apos;ll return an honest &ldquo;no image support&rdquo; status. Pick models marked with the eye icon for image answers.
            </p>
          ) : null}
          {visionOk ? (
            <p className="mx-3 mb-1 flex items-start gap-1.5 rounded-md border border-primary/30 bg-primary/10 px-3 py-1.5 text-[11.5px] text-primary">
              <Eye size={12} className="mt-0.5 shrink-0" /> Vision-ready — the selected model(s) will analyze your image.
            </p>
          ) : null}
          {error ? <p className="px-5 pb-1 text-[12px] text-danger">{error}</p> : null}
          <div className="border-t border-border p-2.5 sm:p-3">
            {/* Thinking Mode (reasoning depth + sampling) — applies to every chat mode. */}
            <div className="mb-2 flex items-center gap-2">
              <span className="shrink-0 text-[10.5px] font-medium uppercase tracking-wide text-content-subtle">Thinking</span>
              <div className="flex min-w-0 flex-1 overflow-x-auto rounded-lg border border-border bg-surface-input p-0.5 text-[12px] sm:flex-none">
                {THINKING_MODES.map((tm) => (
                  <button
                    key={tm}
                    type="button"
                    onClick={() => changeThinking(tm)}
                    title={tm === "fast" ? "Quick, lighter reasoning" : tm === "balance" ? "Good quality + speed (default)" : tm === "thinking" ? "More careful, checks assumptions" : "Maximum reasoning depth"}
                    className={cn(
                      "flex-1 rounded-md px-2.5 py-1 capitalize transition-colors sm:flex-none",
                      thinking === tm ? "bg-surface-high text-content" : "text-content-muted hover:text-content",
                    )}
                  >
                    {tm}
                  </button>
                ))}
              </div>
            </div>
            {images.length ? (
              <div className="mb-2 flex flex-wrap gap-2">
                {images.map((src, i) => (
                  <div key={i} className="relative">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img src={src} alt="attachment" className="h-16 w-16 rounded-lg border border-border object-cover" />
                    <button
                      type="button"
                      onClick={() => removeImage(i)}
                      aria-label="Remove image"
                      className="absolute -right-1.5 -top-1.5 flex h-5 w-5 items-center justify-center rounded-full border border-border bg-surface text-content-subtle hover:text-danger"
                    >
                      <X size={12} />
                    </button>
                  </div>
                ))}
              </div>
            ) : null}
            {knowledgeAttachments.length ? (
              <div className="mb-2 flex flex-wrap gap-2">
                {knowledgeAttachments.map((doc, i) => (
                  <span
                    key={doc.id}
                    className="inline-flex max-w-full items-center gap-2 rounded-lg border border-border bg-surface-input px-2.5 py-1.5 text-[12px] text-content-muted"
                  >
                    <FileText size={13} className={doc.status === "indexed" ? "text-success" : "text-warning"} />
                    <span className="min-w-0 truncate">{doc.filename}</span>
                    <span className="shrink-0 text-content-subtle">{doc.status}</span>
                    <button
                      type="button"
                      onClick={() => removeKnowledgeAttachment(i)}
                      aria-label="Remove knowledge file"
                      className="shrink-0 rounded p-0.5 text-content-subtle hover:text-danger"
                    >
                      <X size={12} />
                    </button>
                  </span>
                ))}
              </div>
            ) : null}
            <form onSubmit={send} className="flex items-center gap-1.5 sm:gap-2">
              <input
                ref={fileRef}
                type="file"
                accept="image/*"
                multiple
                className="hidden"
                onChange={(e) => addImages(e.target.files)}
              />
              <input
                ref={knowledgeFileRef}
                type="file"
                accept=".pdf,.doc,.docx,.txt,.md,.markdown,.csv,.json,.jsonl,.yaml,.yml,.xml,.html,.css,.js,.jsx,.ts,.tsx,.py,.sql,.log,text/*,application/pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                multiple
                className="hidden"
                onChange={(e) => addKnowledgeFiles(e.target.files)}
              />
              <button
                type="button"
                onClick={() => fileRef.current?.click()}
                aria-label="Attach image"
                title="Attach image"
                className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg border border-border bg-surface-input text-content-muted transition-colors hover:border-primary/50 hover:text-content"
              >
                <ImagePlus size={17} />
              </button>
              <button
                type="button"
                onClick={() => knowledgeFileRef.current?.click()}
                aria-label="Attach knowledge file"
                title="Attach PDF, DOC, DOCX, or text file"
                disabled={uploadingKnowledge}
                className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg border border-border bg-surface-input text-content-muted transition-colors hover:border-primary/50 hover:text-content disabled:opacity-60"
              >
                {uploadingKnowledge ? <Loader2 size={17} className="animate-spin" /> : <Paperclip size={17} />}
              </button>
              <button
                type="button"
                onClick={toggleVoiceNote}
                aria-label={listening ? "Stop voice note" : "Start voice note"}
                title={listening ? "Stop voice note" : "Voice note"}
                className={cn(
                  "flex h-11 w-11 shrink-0 items-center justify-center rounded-lg border transition-colors",
                  listening
                    ? "border-danger/40 bg-danger/10 text-danger"
                    : "border-border bg-surface-input text-content-muted hover:border-primary/50 hover:text-content",
                )}
              >
                {listening ? <Square size={15} /> : <Mic size={17} />}
              </button>
              <input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder={listening ? "Listening..." : "Type, speak, or attach a file..."}
                className="h-11 min-w-0 flex-1 rounded-lg border border-border bg-surface-input px-3.5 text-sm text-content placeholder:text-content-subtle focus:border-primary/70 focus:outline-none focus:ring-1 focus:ring-primary/30"
              />
              <Button
                type="submit"
                size="lg"
                loading={sending}
                disabled={(!input.trim() && images.length === 0 && knowledgeAttachments.length === 0) || selected.length === 0 || uploadingKnowledge}
                className="shrink-0 px-3 sm:px-4"
              >
                {!sending ? <SendHorizonal size={16} /> : null}
              </Button>
            </form>
          </div>
        </div>
      </div>

      <p className="mt-2 px-1 text-center text-[11px] text-content-subtle lg:text-left">
        Conversations are saved to your workspace. <Link href="/dashboard/settings" className="text-primary hover:underline">Configure AI providers →</Link>
      </p>
    </AppShell>
  );
}
