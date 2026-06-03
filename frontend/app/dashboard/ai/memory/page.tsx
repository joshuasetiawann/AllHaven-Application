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
  RefreshCw,
  Search,
  Shield,
  X,
  Zap,
} from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
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
  Profile: "border-info/25 bg-info/10 text-info",
  Preferences: "border-secondary/30 bg-secondary/12 text-secondary-soft",
  Projects: "border-success/25 bg-success/10 text-success-soft",
  Decisions: "border-primary/30 bg-primary/10 text-primary-bright",
  "Writing style": "border-warning/30 bg-warning/10 text-warning",
  "Work context": "border-info/25 bg-info/10 text-info",
  "UI/UX preferences": "border-magenta/30 bg-magenta/10 text-magenta",
  Technical: "border-primary/30 bg-primary/10 text-primary-bright",
  "Technical preferences": "border-secondary/30 bg-secondary/12 text-secondary-soft",
  "Tasks context": "border-success/25 bg-success/10 text-success-soft",
  "Finance context": "border-primary/30 bg-primary/10 text-primary-bright",
  Goals: "border-danger/30 bg-danger/10 text-danger",
  Other: "border-border bg-surface-high/70 text-content-muted",
};

const SOURCE_LABELS: Record<string, string> = {
  chat_extracted: "Auto-learned",
  manual: "Manual",
  llm_extracted: "AI-extracted",
  tool_result: "Tool result",
  approved_action: "Approved action",
};

type Tab = "all" | "auto" | "manual" | "pending";

const fieldClass =
  "rounded-md border border-border bg-surface-input px-3 py-2 text-[12.5px] text-content focus:border-primary/50 focus:outline-none focus:ring-1 focus:ring-primary/30";

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
  const [searching, setSearching] = useState(false);
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
    setSearching(true);
    try {
      const results = await memoryApi.search(searchQ);
      setMemories(results);
      if (results.length === 0) toast.info("No memories found", "Try a different keyword.");
    } catch (e) {
      const message = e instanceof ApiException ? e.message : "Search failed.";
      setError(message);
      toast.danger("Search failed", message);
    } finally {
      setSearching(false);
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
    const title = editDraft.title.trim();
    const content = editDraft.content.trim();
    if (!title || !content) {
      setError("Title and content are required.");
      toast.warning("Missing memory details", "Title and content are required.");
      return;
    }
    setError(null);
    try {
      const updated = await memoryApi.update(id, {
        title,
        category: editDraft.category,
        content,
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
    const title = newMemory.title.trim();
    const content = newMemory.content.trim();
    if (!title || !content) {
      setError("Title and content are required.");
      toast.warning("Missing memory details", "Title and content are required.");
      return;
    }
    setError(null);
    try {
      const m = await memoryApi.create({ ...newMemory, title, content });
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

  const groupedByCategory = (() => {
    const map = new Map<string, AiMemory[]>();
    for (const m of filtered) {
      const arr = map.get(m.category) ?? [];
      arr.push(m);
      map.set(m.category, arr);
    }
    const known = (CATEGORIES as string[]).filter((c) => map.has(c));
    const unknown = [...map.keys()].filter((k) => !(CATEGORIES as string[]).includes(k));
    return [...known, ...unknown].map((category) => ({
      category,
      items: map.get(category)!,
    }));
  })();

  const startEdit = (m: AiMemory) => {
    setEditingId(m.id);
    setEditDraft({ title: m.title, category: m.category, content: m.content });
  };

  const resetSearch = () => {
    setSearchQ("");
    setTab("all");
    void load();
  };

  const renderSuggestion = (s: MemorySuggestion) => (
    <div
      key={s.id}
      className="flex flex-col gap-3 rounded-xl border border-warning/25 bg-warning/5 p-3.5 sm:flex-row sm:items-start"
    >
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-1.5">
          <span
            className={cn(
              "rounded-full border px-2 py-0.5 text-[10px] font-medium",
              CATEGORY_COLORS[s.category as MemoryCategory] ?? "border-border bg-surface-high/70 text-content-muted",
            )}
          >
            {s.category}
          </span>
          <span className="text-[12.5px] font-medium text-content">
            {s.title}
          </span>
          <Badge
            tone={s.sensitivity === "LOW" ? "success" : "warning"}
            className="text-[10px]"
          >
            {s.sensitivity}
          </Badge>
        </div>
        <p className="mt-1 text-[12.5px] leading-relaxed text-content-muted">
          {s.content}
        </p>
        {s.source_snippet && (
          <p className="mt-1 text-[10.5px] italic text-content-subtle">
            From: &ldquo;{s.source_snippet}&rdquo;
          </p>
        )}
      </div>
      <div className="flex shrink-0 flex-wrap gap-1.5 sm:justify-end">
        <button
          onClick={() => void handleApproveSuggestion(s.id)}
          className="inline-flex items-center gap-1 rounded-md border border-success/30 bg-success/10 px-2.5 py-1 text-[11px] font-medium text-success-soft transition-colors hover:bg-success/20"
        >
          <Check size={11} /> Save
        </button>
        <button
          onClick={() => void handleRejectSuggestion(s.id)}
          className="inline-flex items-center gap-1 rounded-md border border-border bg-surface-input/60 px-2.5 py-1 text-[11px] font-medium text-content-muted transition-colors hover:bg-surface-raised hover:text-content"
        >
          <X size={11} /> Dismiss
        </button>
      </div>
    </div>
  );

  return (
    <AppShell>
      {/* Header */}
      <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div className="min-w-0">
          <div className="flex items-center gap-2.5">
            <Link
              href="/dashboard/ai"
              aria-label="Back to AI chat"
              className="rounded-md p-1.5 text-content-muted transition-colors hover:bg-surface-raised hover:text-content"
            >
              <ArrowLeft size={17} />
            </Link>
            <h1 className="text-2xl font-semibold tracking-[-0.02em] text-content sm:text-[30px]">AI Memory</h1>
            <Badge tone="primary" className="text-[10.5px] font-semibold">NEW</Badge>
          </div>
          <p className="mt-1.5 max-w-2xl text-[13.5px] leading-relaxed text-content-muted">
            Facts your agents remember about you. Edit or forget any of them ·{" "}
            {memories.length} memories · {suggestions.length} pending
          </p>
        </div>
        <div className="flex w-full flex-wrap items-center gap-2 sm:w-auto sm:justify-end">
          <Button onClick={() => setShowAddForm((v) => !v)} className="w-full sm:w-auto">
            <Plus size={16} /> Add fact
          </Button>
        </div>
      </div>

      {/* Stats */}
      <div className="mb-5 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Card padding="sm">
          <p className="label-mono">Active</p>
          <p className="mt-1 text-2xl font-semibold text-content">{memories.length}</p>
        </Card>
        <Card padding="sm">
          <p className="label-mono">Enabled</p>
          <p className="mt-1 text-2xl font-semibold text-success-soft">{stats.enabled}</p>
        </Card>
        <Card padding="sm">
          <p className="label-mono">Used</p>
          <p className="mt-1 text-2xl font-semibold text-primary-bright">{stats.recentlyUsed}</p>
        </Card>
        <Card padding="sm">
          <p className="label-mono">Review</p>
          <p className="mt-1 text-2xl font-semibold text-warning">{suggestions.length}</p>
        </Card>
      </div>

      {/* Settings Bar */}
      {settings && (
        <Card padding="sm" className="mb-5 flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center sm:gap-5">
          <span className="label-mono">Settings</span>
          <div className="flex items-center gap-2.5 text-[12.5px] text-content-muted">
            <Toggle
              checked={settings.auto_learning_enabled}
              onChange={(v) =>
                void handleUpdateSettings({ auto_learning_enabled: v })
              }
              label="Auto-learning"
            />
            <span>Auto-learn new facts</span>
          </div>
          <div className="flex items-center gap-2.5 text-[12.5px] text-content-muted">
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
            className="text-left text-[11.5px] font-medium text-danger transition-colors hover:underline sm:ml-auto"
          >
            Clear all memories
          </button>
        </Card>
      )}

      {/* Add Form */}
      {showAddForm && (
        <Card gradient className="mb-5 space-y-3">
          <p className="text-[15px] font-semibold text-content">Add fact</p>
          <div className="grid gap-2 sm:grid-cols-[160px_120px_1fr]">
            <select
              value={newMemory.category}
              onChange={(e) =>
                setNewMemory((p) => ({
                  ...p,
                  category: e.target.value as MemoryCategory,
                }))
              }
              className={fieldClass}
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
              className={fieldClass}
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
              className="flex-1 text-[12.5px]"
            />
          </div>
          <textarea
            value={newMemory.content}
            onChange={(e) =>
              setNewMemory((p) => ({ ...p, content: e.target.value }))
            }
            placeholder="Short memory content, e.g. User prefers concise Indonesian answers."
            rows={3}
            className={cn("w-full placeholder:text-content-faint", fieldClass)}
          />
          <div className="flex flex-col gap-2 sm:flex-row">
            <Button size="sm" onClick={() => void handleAddMemory()} className="w-full sm:w-auto">
              Save
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => setShowAddForm(false)}
              className="w-full sm:w-auto"
            >
              Cancel
            </Button>
          </div>
        </Card>
      )}

      {/* Pending Suggestions */}
      {suggestions.length > 0 && tab !== "pending" && (
        <div className="mb-5 space-y-2">
          <p className="flex items-center gap-1.5 text-[12.5px] font-medium text-content-muted">
            <Zap size={13} className="text-warning" />
            {suggestions.length} pending suggestion
            {suggestions.length > 1 ? "s" : ""}
          </p>
          {suggestions.map(renderSuggestion)}
        </div>
      )}

      {/* Tab + Filter bar */}
      <div className="mb-5 flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center">
        <div className="custom-scrollbar flex overflow-x-auto rounded-md border border-border bg-surface-input/70 p-[3px] text-[12px] sm:inline-flex">
          {(["all", "auto", "manual", "pending"] as Tab[]).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={cn(
                "shrink-0 rounded-sm border px-3 py-1 font-medium capitalize transition-colors",
                tab === t
                  ? "border-primary/40 bg-[linear-gradient(90deg,rgb(var(--color-primary)/0.16),rgb(var(--color-secondary)/0.10))] text-content"
                  : "border-transparent text-content-muted hover:text-content",
              )}
            >
              {t === "all"
                ? `All (${memories.length})`
                : t === "pending"
                  ? `Review (${suggestions.length})`
                  : t === "auto"
                    ? "Auto-learned"
                    : "Manual"}
            </button>
          ))}
        </div>
        <select
          value={categoryFilter}
          onChange={(e) => setCategoryFilter(e.target.value)}
          className={cn("h-9 w-full py-0 text-content-muted sm:w-auto", fieldClass)}
        >
          <option value="all">All categories</option>
          {CATEGORIES.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
        <div className="flex h-9 min-w-0 flex-1 items-center gap-1.5 rounded-md border border-border bg-surface-input px-2.5 focus-within:border-primary/50">
          <Search size={13} className="shrink-0 text-content-subtle" />
          <input
            value={searchQ}
            onChange={(e) => setSearchQ(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && !e.nativeEvent.isComposing && void handleSearch()}
            placeholder="Search memories…"
            className="min-w-0 flex-1 bg-transparent py-1 text-[12.5px] text-content placeholder:text-content-faint focus:outline-none"
          />
        </div>
        <Button size="sm" variant="ghost" onClick={() => void handleSearch()} loading={searching} className="w-full sm:w-auto">
          <Search size={13} /> Search
        </Button>
        {searchQ.trim() ? (
          <Button size="sm" variant="secondary" onClick={resetSearch} className="w-full sm:w-auto">
            <RefreshCw size={13} /> Reset
          </Button>
        ) : null}
      </div>

      {/* Error state */}
      {error && (
        <p className="mb-5 rounded-lg border border-danger/30 bg-danger/10 px-3.5 py-2.5 text-[12.5px] text-danger">
          {error}
        </p>
      )}

      {/* Memory List */}
      {loading ? (
        <p className="text-[12.5px] text-content-muted">Loading memories…</p>
      ) : tab === "pending" ? (
        suggestions.length === 0 ? (
          <Card className="flex flex-col items-center py-12 text-center">
            <Brain size={32} className="mb-3 text-content-subtle" />
            <p className="text-[13px] text-content-muted">
              No pending suggestions.
            </p>
          </Card>
        ) : (
          <div className="space-y-2">{suggestions.map(renderSuggestion)}</div>
        )
      ) : filtered.length === 0 ? (
        <Card className="flex flex-col items-center py-12 text-center">
          <span className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl border border-primary/25 bg-primary/10 text-primary-bright shadow-glow-primary">
            <Brain size={22} />
          </span>
          <p className="text-[13.5px] font-medium text-content">No memories yet.</p>
          <p className="mt-1 max-w-sm text-[12.5px] leading-relaxed text-content-subtle">
            {settings?.auto_learning_enabled
              ? "Chat with AI and it will auto-learn important facts about you."
              : "Auto-learning is off. Enable it in settings, or add memories manually."}
          </p>
        </Card>
      ) : (
        <div className="grid items-start gap-4 lg:grid-cols-2">
          {groupedByCategory.map(({ category, items }) => (
            <Card key={category} padding="sm" className="min-w-0">
              <div className="mb-2 flex items-center gap-2.5">
                <span
                  className={cn(
                    "flex h-8 w-8 shrink-0 items-center justify-center rounded-[9px] border",
                    CATEGORY_COLORS[category as MemoryCategory] ??
                      "border-border bg-surface-high/70 text-content-muted",
                  )}
                >
                  <Brain size={15} />
                </span>
                <p className="text-[13px] font-semibold text-content">{category}</p>
                <span className="label-mono ml-auto">{items.length}</span>
              </div>
              <ul className="divide-y divide-border/60">
                {items.map((m) => (
                  <li
                    key={m.id}
                    className={cn(
                      "py-3 transition-opacity first:pt-1 last:pb-0",
                      !m.enabled && "opacity-50",
                    )}
                  >
                    <div className="flex flex-col gap-2 sm:flex-row sm:items-start">
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-1.5">
                          <span className="min-w-0 break-words text-[13px] font-medium text-content">
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
                                className={fieldClass}
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
                                className="text-[12.5px]"
                              />
                            </div>
                            <textarea
                              value={editDraft.content}
                              onChange={(e) => setEditDraft((p) => ({ ...p, content: e.target.value }))}
                              rows={3}
                              className={cn("w-full", fieldClass)}
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
                                variant="ghost"
                                onClick={() => setEditingId(null)}
                                className="w-full sm:w-auto"
                              >
                                Cancel
                              </Button>
                            </div>
                          </div>
                        ) : (
                          <>
                            <p className="mt-0.5 text-[13px] leading-relaxed text-content-muted">
                              {m.content}
                            </p>
                            <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 font-mono text-[10.5px] text-content-faint">
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
                          className="rounded-sm p-1 text-content-subtle transition-colors hover:bg-surface-raised hover:text-primary-bright"
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
                          className="rounded-sm p-1 text-content-subtle transition-colors hover:text-danger"
                        >
                          <X size={14} />
                        </button>
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
            </Card>
          ))}
        </div>
      )}
    </AppShell>
  );
}
