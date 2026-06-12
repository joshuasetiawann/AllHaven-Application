"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  Brain,
  Check,
  Clock3,
  Pencil,
  Plus,
  Search,
  Shield,
  Trash2,
  X,
  Zap,
} from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Toggle } from "@/components/ui/Toggle";
import { useToast } from "@/components/ui/Toast";
import { useAppDialog } from "@/components/ui/AppDialog";
import { memoryApi, ApiException } from "@/lib/api";
import { cn, relativeTime } from "@/lib/format";
import type { AiMemory, MemorySuggestion, MemorySettings, MemoryCategory, MemorySensitivity } from "@/types";

const CATEGORIES: MemoryCategory[] = [
  "Profile",
  "Preferences",
  "Projects",
  "Decisions",
  "Writing style",
  "Work context",
  "UI/UX preferences",
  "Technical",
  "Technical preferences",
  "Tasks context",
  "Finance context",
  "Goals",
  "Other",
];

const CATEGORY_COLORS: Record<MemoryCategory, string> = {
  Profile: "bg-blue-500/10 text-blue-400 border-blue-500/20",
  Preferences: "bg-purple-500/10 text-purple-400 border-purple-500/20",
  Projects: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
  Decisions: "bg-teal-500/10 text-teal-400 border-teal-500/20",
  "Writing style": "bg-amber-500/10 text-amber-400 border-amber-500/20",
  "Work context": "bg-sky-500/10 text-sky-400 border-sky-500/20",
  "UI/UX preferences": "bg-fuchsia-500/10 text-fuchsia-400 border-fuchsia-500/20",
  Technical: "bg-cyan-500/10 text-cyan-400 border-cyan-500/20",
  "Technical preferences": "bg-indigo-500/10 text-indigo-400 border-indigo-500/20",
  "Tasks context": "bg-lime-500/10 text-lime-400 border-lime-500/20",
  "Finance context": "bg-green-500/10 text-green-400 border-green-500/20",
  Goals: "bg-rose-500/10 text-rose-400 border-rose-500/20",
  Other: "bg-slate-500/10 text-slate-400 border-slate-500/20",
};

const SOURCE_LABELS: Record<string, string> = {
  chat_extracted: "Auto-learned",
  manual: "Manual",
  llm_extracted: "AI-extracted",
  tool_result: "Tool result",
  approved_action: "Approved action",
};

type Tab = "all" | "auto" | "manual" | "pending";

export default function MemoryPage() {
  const toast = useToast();
  const dialog = useAppDialog();
  const [memories, setMemories] = useState<AiMemory[]>([]);
  const [suggestions, setSuggestions] = useState<MemorySuggestion[]>([]);
  const [settings, setSettings] = useState<MemorySettings | null>(null);
  const [tab, setTab] = useState<Tab>("all");
  const [categoryFilter, setCategoryFilter] = useState<string>("all");
  const [searchQ, setSearchQ] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editDraft, setEditDraft] = useState<{
    title: string;
    category: MemoryCategory;
    content: string;
  }>({ title: "", category: "Profile", content: "" });
  const [showAddForm, setShowAddForm] = useState(false);
  const [newMemory, setNewMemory] = useState<{
    category: MemoryCategory;
    sensitivity: MemorySensitivity;
    title: string;
    content: string;
  }>({ category: "Profile", sensitivity: "LOW", title: "", content: "" });

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const [mems, suggs, s] = await Promise.all([
        memoryApi.list(),
        memoryApi.listSuggestions(),
        memoryApi.getSettings(),
      ]);
      setMemories(mems);
      setSuggestions(suggs);
      setSettings(s);
    } catch (e) {
      setError(e instanceof ApiException ? e.message : "Failed to load memories.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleSearch = async () => {
    setError(null);
    if (!searchQ.trim()) {
      void load();
      return;
    }
    try {
      const results = await memoryApi.search(searchQ);
      setMemories(results);
      if (results.length === 0) toast.info("No memories found", "Try a different keyword.");
    } catch (e) {
      const message = e instanceof ApiException ? e.message : "Search failed.";
      setError(message);
      toast.danger("Search failed", message);
    }
  };

  const handleToggleEnabled = async (m: AiMemory) => {
    setError(null);
    try {
      const updated = m.enabled
        ? await memoryApi.disable(m.id)
        : await memoryApi.enable(m.id);
      setMemories((prev) => prev.map((x) => (x.id === m.id ? updated : x)));
      toast.success(m.enabled ? "Memory disabled" : "Memory enabled", m.title);
    } catch (e) {
      const message = e instanceof ApiException ? e.message : "Failed to update memory.";
      setError(message);
      toast.danger("Update failed", message);
    }
  };

  const handleDelete = async (id: string) => {
    const ok = await dialog.confirm({
      title: "Delete memory?",
      message: "This memory will stop being available to AI context. This cannot be undone.",
      confirmLabel: "Delete",
      tone: "danger",
    });
    if (!ok) return;
    setError(null);
    try {
      await memoryApi.remove(id);
      setMemories((prev) => prev.filter((m) => m.id !== id));
      toast.success("Memory deleted");
    } catch (e) {
      const message = e instanceof ApiException ? e.message : "Failed to delete memory.";
      setError(message);
      toast.danger("Delete failed", message);
    }
  };

  const handleSaveEdit = async (id: string) => {
    setError(null);
    try {
      const updated = await memoryApi.update(id, {
        title: editDraft.title,
        category: editDraft.category,
        content: editDraft.content,
      });
      setMemories((prev) => prev.map((m) => (m.id === id ? updated : m)));
      setEditingId(null);
      toast.success("Memory updated", updated.title);
    } catch (e) {
      const message = e instanceof ApiException ? e.message : "Failed to save edit.";
      setError(message);
      toast.danger("Save failed", message);
    }
  };

  const handleApproveSuggestion = async (id: string) => {
    setError(null);
    try {
      const m = await memoryApi.approveSuggestion(id);
      setSuggestions((prev) => prev.filter((s) => s.id !== id));
      setMemories((prev) => [m, ...prev]);
      toast.success("Memory saved", m.title);
    } catch (e) {
      const message = e instanceof ApiException ? e.message : "Failed to approve suggestion.";
      setError(message);
      toast.danger("Approval failed", message);
    }
  };

  const handleRejectSuggestion = async (id: string) => {
    setError(null);
    try {
      await memoryApi.rejectSuggestion(id);
      setSuggestions((prev) => prev.filter((s) => s.id !== id));
      toast.info("Suggestion dismissed");
    } catch (e) {
      const message = e instanceof ApiException ? e.message : "Failed to reject suggestion.";
      setError(message);
      toast.danger("Dismiss failed", message);
    }
  };

  const handleAddMemory = async () => {
    if (!newMemory.title.trim() || !newMemory.content.trim()) {
      setError("Title and content are required.");
      toast.warning("Missing memory details", "Title and content are required.");
      return;
    }
    setError(null);
    try {
      const m = await memoryApi.create(newMemory);
      setMemories((prev) => [m, ...prev]);
      setNewMemory({ category: "Profile", sensitivity: "LOW", title: "", content: "" });
      setShowAddForm(false);
      toast.success("Memory added", m.title);
    } catch (e) {
      const message = e instanceof ApiException ? e.message : "Failed to add memory.";
      setError(message);
      toast.danger("Add failed", message);
    }
  };

  const handleUpdateSettings = async (patch: Partial<MemorySettings>) => {
    if (!settings) return;
    setError(null);
    const prev = settings;
    const next = { ...settings, ...patch };
    setSettings(next); // optimistic
    try {
      const saved = await memoryApi.updateSettings(patch);
      setSettings(saved);
      toast.success("Memory settings saved");
    } catch (e) {
      setSettings(prev); // rollback
      const message = e instanceof ApiException ? e.message : "Failed to update settings.";
      setError(message);
      toast.danger("Settings failed", message);
    }
  };

  const handleClearAll = async () => {
    const ok = await dialog.confirm({
      title: "Delete all AI memories?",
      message: "This clears every saved AI memory in this workspace. This cannot be undone.",
      confirmLabel: "Delete all",
      tone: "danger",
    });
    if (!ok) return;
    setError(null);
    try {
      await memoryApi.clearAll();
      setMemories([]);
      toast.success("All memories cleared");
    } catch (e) {
      const message = e instanceof ApiException ? e.message : "Failed to clear memories.";
      setError(message);
      toast.danger("Clear failed", message);
    }
  };

  const stats = useMemo(() => {
    const enabled = memories.filter((m) => m.enabled).length;
    const recentlyUsed = memories.filter((m) => Boolean(m.last_used_at)).length;
    return { enabled, recentlyUsed };
  }, [memories]);

  const filtered = memories.filter((m) => {
    if (tab === "auto" && m.source === "manual") return false;
    if (tab === "manual" && m.source !== "manual") return false;
    if (categoryFilter !== "all" && m.category !== categoryFilter) return false;
    const q = searchQ.trim().toLowerCase();
    if (q && !`${m.title} ${m.content} ${m.category}`.toLowerCase().includes(q)) return false;
    return true;
  });

  const startEdit = (m: AiMemory) => {
    setEditingId(m.id);
    setEditDraft({ title: m.title, category: m.category, content: m.content });
  };

  return (
    <AppShell>
      <div className="mx-auto w-full max-w-4xl space-y-6">
        {/* Header */}
        <div className="flex flex-wrap items-center gap-3">
          <Link
            href="/dashboard/ai"
            aria-label="Back to AI chat"
            className="rounded-md p-1.5 text-content-muted hover:bg-surface-raised hover:text-content"
          >
            <ArrowLeft size={17} />
          </Link>
          <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary/10 text-primary">
            <Brain size={18} />
          </span>
          <div className="min-w-0 flex-1">
            <h1 className="text-lg font-semibold text-content">AI Memory</h1>
            <p className="text-[12px] text-content-muted">
              {memories.length} memories · {suggestions.length} pending
            </p>
          </div>
          <div className="flex w-full gap-2 sm:ml-auto sm:w-auto">
            <Button
              size="sm"
              variant="secondary"
              onClick={() => setShowAddForm((v) => !v)}
              className="w-full sm:w-auto"
            >
              <Plus size={14} className="mr-1" /> Add Memory
            </Button>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <div className="rounded-lg border border-border bg-surface/45 px-3 py-2.5">
            <p className="label-mono">Active</p>
            <p className="mt-1 text-xl font-semibold text-content">{memories.length}</p>
          </div>
          <div className="rounded-lg border border-border bg-surface/45 px-3 py-2.5">
            <p className="label-mono">Enabled</p>
            <p className="mt-1 text-xl font-semibold text-success">{stats.enabled}</p>
          </div>
          <div className="rounded-lg border border-border bg-surface/45 px-3 py-2.5">
            <p className="label-mono">Used</p>
            <p className="mt-1 text-xl font-semibold text-primary">{stats.recentlyUsed}</p>
          </div>
          <div className="rounded-lg border border-border bg-surface/45 px-3 py-2.5">
            <p className="label-mono">Review</p>
            <p className="mt-1 text-xl font-semibold text-warning">{suggestions.length}</p>
          </div>
        </div>

        {/* Settings Bar */}
        {settings && (
          <div className="flex flex-col gap-3 rounded-xl border border-border bg-surface/50 px-4 py-3 sm:flex-row sm:flex-wrap sm:items-center sm:gap-4">
            <span className="text-[12px] font-medium text-content-muted">
              Settings
            </span>
            <div className="flex items-center gap-2 text-[12px] text-content-muted">
              <Toggle
                checked={settings.auto_learning_enabled}
                onChange={(v) =>
                  void handleUpdateSettings({ auto_learning_enabled: v })
                }
                label="Auto-learning"
              />
              <span>Auto-learning</span>
            </div>
            <div className="flex items-center gap-2 text-[12px] text-content-muted">
              <Toggle
                checked={settings.require_approval_sensitive}
                onChange={(v) =>
                  void handleUpdateSettings({ require_approval_sensitive: v })
                }
                label="Require approval for sensitive"
              />
              <span>Require approval for sensitive</span>
            </div>
            <button
              onClick={() => void handleClearAll()}
              className="text-left text-[11.5px] text-danger hover:underline sm:ml-auto"
            >
              Clear all memories
            </button>
          </div>
        )}

        {/* Add Form */}
        {showAddForm && (
          <div className="rounded-xl border border-border bg-surface/50 p-4 space-y-3">
            <p className="text-[13px] font-medium text-content">Add Memory</p>
            <div className="grid gap-2 sm:grid-cols-[160px_120px_1fr]">
              <select
                value={newMemory.category}
                onChange={(e) =>
                  setNewMemory((p) => ({
                    ...p,
                    category: e.target.value as MemoryCategory,
                  }))
                }
                className="rounded-md border border-border bg-surface-input px-2 py-1.5 text-[12px] text-content"
              >
                {CATEGORIES.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
              <select
                value={newMemory.sensitivity}
                onChange={(e) =>
                  setNewMemory((p) => ({
                    ...p,
                    sensitivity: e.target.value as MemorySensitivity,
                  }))
                }
                className="rounded-md border border-border bg-surface-input px-2 py-1.5 text-[12px] text-content"
              >
                <option value="LOW">Low</option>
                <option value="MEDIUM">Medium</option>
                <option value="HIGH">High</option>
              </select>
              <Input
                value={newMemory.title}
                onChange={(e) =>
                  setNewMemory((p) => ({ ...p, title: e.target.value }))
                }
                placeholder="Title"
                className="flex-1 text-[12px]"
              />
            </div>
            <textarea
              value={newMemory.content}
              onChange={(e) =>
                setNewMemory((p) => ({ ...p, content: e.target.value }))
              }
              placeholder="Short memory content, e.g. User prefers concise Indonesian answers."
              rows={3}
              className="w-full rounded-md border border-border bg-surface-input px-3 py-2 text-[12px] text-content placeholder:text-content-subtle focus:border-primary/70 focus:outline-none"
            />
            <div className="flex flex-col gap-2 sm:flex-row">
              <Button size="sm" onClick={() => void handleAddMemory()} className="w-full sm:w-auto">
                Save
              </Button>
              <Button
                size="sm"
                variant="secondary"
                onClick={() => setShowAddForm(false)}
                className="w-full sm:w-auto"
              >
                Cancel
              </Button>
            </div>
          </div>
        )}

        {/* Pending Suggestions */}
        {suggestions.length > 0 && (
          <div className="space-y-2">
            <p className="flex items-center gap-1.5 text-[12px] font-medium text-content-muted">
              <Zap size={13} className="text-warning" />
              {suggestions.length} pending suggestion
              {suggestions.length > 1 ? "s" : ""}
            </p>
            {suggestions.map((s) => (
              <div
                key={s.id}
                className="flex flex-col gap-3 rounded-xl border border-warning/20 bg-warning/5 p-3 sm:flex-row sm:items-start"
              >
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-1.5">
                    <span
                      className={cn(
                        "rounded-md border px-1.5 py-0.5 text-[10px] font-medium",
                        CATEGORY_COLORS[s.category as MemoryCategory] ?? "",
                      )}
                    >
                      {s.category}
                    </span>
                    <span className="text-[12px] font-medium text-content">
                      {s.title}
                    </span>
                    <Badge
                      tone={s.sensitivity === "LOW" ? "success" : "warning"}
                      className="text-[10px]"
                    >
                      {s.sensitivity}
                    </Badge>
                  </div>
                  <p className="mt-0.5 text-[12px] text-content-muted">
                    {s.content}
                  </p>
                  {s.source_snippet && (
                    <p className="mt-0.5 text-[10.5px] text-content-subtle italic">
                      From: &ldquo;{s.source_snippet}&rdquo;
                    </p>
                  )}
                </div>
                <div className="flex shrink-0 flex-wrap gap-1.5 sm:justify-end">
                  <button
                    onClick={() => void handleApproveSuggestion(s.id)}
                    className="flex items-center gap-1 rounded-md border border-success/30 bg-success/10 px-2 py-1 text-[11px] text-success hover:bg-success/20"
                  >
                    <Check size={11} /> Save
                  </button>
                  <button
                    onClick={() => void handleRejectSuggestion(s.id)}
                    className="flex items-center gap-1 rounded-md border border-border px-2 py-1 text-[11px] text-content-muted hover:bg-surface-raised"
                  >
                    <X size={11} /> Dismiss
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Tab + Filter bar */}
        <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center">
          <div className="custom-scrollbar flex overflow-x-auto rounded-lg border border-border bg-surface-input p-0.5 text-[12px] sm:inline-flex">
            {(["all", "auto", "manual", "pending"] as Tab[]).map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={cn(
                  "shrink-0 rounded-md px-3 py-1 capitalize transition-colors",
                  tab === t
                    ? "bg-surface-high text-content"
                    : "text-content-muted hover:text-content",
                )}
              >
                {t === "all"
                  ? `All (${memories.length})`
                  : t === "pending"
                    ? `Pending (${suggestions.length})`
                    : t === "auto"
                      ? "Auto-learned"
                      : "Manual"}
              </button>
            ))}
          </div>
          <select
            value={categoryFilter}
            onChange={(e) => setCategoryFilter(e.target.value)}
            className="h-8 w-full rounded-md border border-border bg-surface-input px-2 py-1 text-[12px] text-content-muted sm:w-auto"
          >
            <option value="all">All categories</option>
            {CATEGORIES.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
          <div className="flex min-w-0 flex-1 items-center gap-1.5 rounded-md border border-border bg-surface-input px-2">
            <Search size={13} className="shrink-0 text-content-subtle" />
            <input
              value={searchQ}
              onChange={(e) => setSearchQ(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && !e.nativeEvent.isComposing && void handleSearch()}
              placeholder="Search memories…"
              className="min-w-0 flex-1 bg-transparent py-1 text-[12px] text-content placeholder:text-content-subtle focus:outline-none"
            />
          </div>
        </div>

        {/* Error state */}
        {error && (
          <p className="rounded-md border border-danger/30 bg-danger/5 px-3 py-2 text-[12px] text-danger">
            {error}
          </p>
        )}

        {/* Memory List */}
        {loading ? (
          <p className="text-[12px] text-content-muted">Loading memories…</p>
        ) : tab === "pending" ? (
          suggestions.length === 0 ? (
            <div className="flex flex-col items-center py-12 text-center">
              <Brain size={32} className="mb-3 text-content-subtle" />
              <p className="text-[13px] text-content-muted">
                No pending suggestions.
              </p>
            </div>
          ) : null
        ) : filtered.length === 0 ? (
          <div className="flex flex-col items-center py-12 text-center">
            <Brain size={32} className="mb-3 text-content-subtle" />
            <p className="text-[13px] text-content-muted">No memories yet.</p>
            <p className="mt-1 text-[12px] text-content-subtle">
              {settings?.auto_learning_enabled
                ? "Chat with AI and it will auto-learn important facts about you."
                : "Auto-learning is off. Enable it in settings, or add memories manually."}
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            {filtered.map((m) => (
              <div
                key={m.id}
                className={cn(
                  "rounded-xl border p-3 transition-colors",
                  m.enabled
                    ? "border-border bg-surface/50"
                    : "border-border/50 bg-surface/20 opacity-60",
                )}
              >
                <div className="flex flex-col gap-2 sm:flex-row sm:items-start">
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-1.5">
                      <span
                        className={cn(
                          "rounded-md border px-1.5 py-0.5 text-[10px] font-medium",
                          CATEGORY_COLORS[m.category as MemoryCategory] ?? "",
                        )}
                      >
                        {m.category}
                      </span>
                      <span className="min-w-0 break-words text-[12.5px] font-medium text-content">
                        {m.title}
                      </span>
                      <Badge tone="neutral" className="text-[10px]">
                        {SOURCE_LABELS[m.source] ?? m.source}
                      </Badge>
                      {m.sensitivity !== "LOW" && (
                        <Badge tone="warning" className="text-[10px]">
                          {m.sensitivity}
                        </Badge>
                      )}
                    </div>
                    {editingId === m.id ? (
                      <div className="mt-2 space-y-2">
                        <div className="grid gap-2 sm:grid-cols-[160px_1fr]">
                          <select
                            value={editDraft.category}
                            onChange={(e) => setEditDraft((p) => ({ ...p, category: e.target.value as MemoryCategory }))}
                            className="rounded-md border border-border bg-surface-input px-2 py-1.5 text-[12px] text-content"
                          >
                            {CATEGORIES.map((c) => (
                              <option key={c} value={c}>
                                {c}
                              </option>
                            ))}
                          </select>
                          <Input
                            value={editDraft.title}
                            onChange={(e) => setEditDraft((p) => ({ ...p, title: e.target.value }))}
                            className="text-[12px]"
                          />
                        </div>
                        <textarea
                          value={editDraft.content}
                          onChange={(e) => setEditDraft((p) => ({ ...p, content: e.target.value }))}
                          rows={3}
                          className="w-full rounded-md border border-border bg-surface-input px-2.5 py-1.5 text-[12px] text-content focus:border-primary/70 focus:outline-none"
                        />
                        <div className="flex flex-col gap-1.5 sm:flex-row">
                          <Button
                            size="sm"
                            onClick={() => void handleSaveEdit(m.id)}
                            className="w-full sm:w-auto"
                          >
                            Save
                          </Button>
                          <Button
                            size="sm"
                            variant="secondary"
                            onClick={() => setEditingId(null)}
                            className="w-full sm:w-auto"
                          >
                            Cancel
                          </Button>
                        </div>
                      </div>
                    ) : (
                      <>
                        <p className="mt-0.5 text-[12px] leading-relaxed text-content-muted">
                          {m.content}
                        </p>
                        <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[10.5px] text-content-subtle">
                          <span className="inline-flex items-center gap-1">
                            <Shield size={11} /> confidence {Math.round(m.confidence * 100)}%
                          </span>
                          <span>relevance {Math.round(m.relevance_score * 100)}%</span>
                          <span className="inline-flex items-center gap-1">
                            <Clock3 size={11} /> {m.last_used_at ? `used ${relativeTime(m.last_used_at)}` : "not used yet"}
                          </span>
                        </div>
                      </>
                    )}
                  </div>
                  <div className="flex shrink-0 items-center justify-end gap-2">
                    <button
                      onClick={() => startEdit(m)}
                      aria-label="Edit memory"
                      className="rounded-md p-1 text-content-subtle hover:bg-surface-raised hover:text-content"
                    >
                      <Pencil size={13} />
                    </button>
                    <Toggle
                      checked={m.enabled}
                      onChange={() => void handleToggleEnabled(m)}
                      label={m.enabled ? "Enabled" : "Disabled"}
                    />
                    <button
                      onClick={() => void handleDelete(m.id)}
                      aria-label="Delete memory"
                      className="rounded-md p-1 text-content-subtle hover:text-danger"
                    >
                      <Trash2 size={13} />
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </AppShell>
  );
}
