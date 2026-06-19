"use client";

import { useEffect, useMemo, useState } from "react";
import { ArrowLeft, Pin, Plus, Search, Sparkles, StickyNote, Trash2 } from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Input } from "@/components/ui/Input";
import { Textarea } from "@/components/ui/Textarea";
import { Modal } from "@/components/ui/Modal";
import { EmptyState, ErrorState, Loading } from "@/components/ui/States";
import { notesApi, ApiException } from "@/lib/api";
import { cn, formatDateTime } from "@/lib/format";
import type { Note } from "@/types";

export default function NotesPage() {
  const [notes, setNotes] = useState<Note[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [mobileReader, setMobileReader] = useState(false);
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({ title: "", content: "", tags: "", is_pinned: false });

  const load = async (selectFirst = false) => {
    setError(null);
    try {
      const data = await notesApi.list();
      setNotes(data);
      if (selectFirst && data.length > 0 && !selectedId) setSelectedId(data[0].id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load notes.");
    }
  };

  useEffect(() => {
    void load(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const filtered = useMemo(() => {
    const list = notes ?? [];
    const q = query.trim().toLowerCase();
    if (!q) return list;
    return list.filter(
      (n) =>
        n.title.toLowerCase().includes(q) ||
        (n.content ?? "").toLowerCase().includes(q) ||
        n.tags.some((t) => t.toLowerCase().includes(q)),
    );
  }, [notes, query]);

  const selected = useMemo(
    () => (notes ?? []).find((n) => n.id === selectedId) ?? null,
    [notes, selectedId],
  );

  const create = async (event: React.FormEvent) => {
    event.preventDefault();
    setSaving(true);
    try {
      const note = await notesApi.create({
        title: form.title,
        content: form.content || undefined,
        tags: form.tags.split(",").map((t) => t.trim()).filter(Boolean),
        is_pinned: form.is_pinned,
      });
      setOpen(false);
      setForm({ title: "", content: "", tags: "", is_pinned: false });
      await load();
      setSelectedId(note.id);
    } catch (err) {
      setError(err instanceof ApiException ? err.message : "Failed to create note.");
    } finally {
      setSaving(false);
    }
  };

  const togglePin = async (note: Note) => {
    setNotes((prev) => prev?.map((n) => (n.id === note.id ? { ...n, is_pinned: !n.is_pinned } : n)) ?? prev);
    try {
      await notesApi.update(note.id, { is_pinned: !note.is_pinned });
      await load();
    } catch {
      void load();
    }
  };

  const remove = async (note: Note) => {
    setNotes((prev) => prev?.filter((n) => n.id !== note.id) ?? prev);
    if (selectedId === note.id) setSelectedId(null);
    try {
      await notesApi.remove(note.id);
    } catch {
      void load();
    }
  };

  const openNote = (id: string) => {
    setSelectedId(id);
    setMobileReader(true);
  };

  return (
    <AppShell>
      <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0">
          <h1 className="text-2xl font-semibold tracking-tight text-content sm:text-[28px]">Notes &amp; Knowledge</h1>
          <p className="mt-1 text-[13.5px] text-content-muted">
            {notes ? `${notes.length} entries` : "Your knowledge base"}
          </p>
        </div>
        <Button onClick={() => setOpen(true)} className="w-full sm:w-auto">
          <Plus size={16} /> New note
        </Button>
      </div>

      {error ? (
        <ErrorState message={error} onRetry={() => load()} />
      ) : !notes ? (
        <Loading />
      ) : notes.length === 0 ? (
        <EmptyState
          title="No notes yet"
          description="Capture ideas, meeting notes, and documentation."
          icon={<StickyNote size={20} />}
          action={
            <Button onClick={() => setOpen(true)}>
              <Plus size={16} /> New note
            </Button>
          }
        />
      ) : (
        <div className="grid gap-5 lg:grid-cols-[360px_1fr]">
          {/* List */}
          <div className={cn("space-y-3", mobileReader && "hidden lg:block")}>
            <Input
              leftIcon={<Search size={15} />}
              placeholder="Search notes, tags…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
            <div className="custom-scrollbar max-h-[calc(100svh-210px)] space-y-2.5 overflow-y-auto pr-1 lg:max-h-[calc(100vh-230px)]">
              {filtered.map((note) => (
                <button
                  key={note.id}
                  onClick={() => openNote(note.id)}
                  className={cn(
                    "w-full rounded-xl border p-4 text-left transition-colors",
                    note.id === selectedId
                      ? "border-primary/40 bg-primary/5"
                      : "border-border bg-surface/60 hover:border-border-strong hover:bg-surface-raised/60",
                  )}
                >
                  <div className="flex items-start justify-between gap-2">
                    <h3 className="truncate text-sm font-semibold text-content">{note.title}</h3>
                    {note.is_pinned ? <Pin size={13} className="shrink-0 text-primary" fill="currentColor" /> : null}
                  </div>
                  {note.content ? (
                    <p className="mt-1 line-clamp-2 text-[12.5px] text-content-muted">{note.content}</p>
                  ) : null}
                  {note.tags.length > 0 ? (
                    <div className="mt-2.5 hidden flex-wrap gap-1.5 sm:flex">
                      {note.tags.slice(0, 3).map((tag) => (
                        <Badge key={tag} tone="secondary">
                          {tag}
                        </Badge>
                      ))}
                    </div>
                  ) : null}
                </button>
              ))}
              {filtered.length === 0 ? (
                <p className="py-6 text-center text-[13px] text-content-muted">No notes match &quot;{query}&quot;.</p>
              ) : null}
            </div>
          </div>

          {/* Reader */}
          <Card className={cn("min-h-[400px]", !mobileReader && "hidden lg:block")} padding="lg">
            {selected ? (
              <div className="animate-fade-in">
                <button
                  onClick={() => setMobileReader(false)}
                  className="mb-4 inline-flex items-center gap-1.5 text-[13px] text-content-muted hover:text-content lg:hidden"
                >
                  <ArrowLeft size={15} /> Back to list
                </button>
                <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                  <div className="min-w-0">
                    <p className="font-mono text-[11px] uppercase tracking-widest text-content-subtle">
                      Knowledge entry
                    </p>
                    <h2 className="mt-1 break-words text-xl font-semibold tracking-tight text-content">{selected.title}</h2>
                  </div>
                  <div className="flex shrink-0 items-center gap-1.5">
                    <button
                      onClick={() => togglePin(selected)}
                      className={cn(
                        "rounded-md border border-border p-2 transition-colors hover:border-border-strong",
                        selected.is_pinned ? "text-primary" : "text-content-subtle hover:text-content",
                      )}
                      aria-label="Pin note"
                    >
                      <Pin size={15} fill={selected.is_pinned ? "currentColor" : "none"} />
                    </button>
                    <button
                      onClick={() => remove(selected)}
                      className="rounded-md border border-border p-2 text-content-subtle transition-colors hover:border-danger/40 hover:text-danger"
                      aria-label="Delete note"
                    >
                      <Trash2 size={15} />
                    </button>
                  </div>
                </div>

                {selected.tags.length > 0 ? (
                  <div className="mt-3 flex flex-wrap gap-1.5">
                    {selected.tags.map((tag) => (
                      <Badge key={tag} tone="secondary">
                        {tag}
                      </Badge>
                    ))}
                  </div>
                ) : null}

                <div className="mt-5 border-t border-border pt-5">
                  {selected.content ? (
                    <p className="whitespace-pre-wrap text-[14px] leading-relaxed text-content-muted">
                      {selected.content}
                    </p>
                  ) : (
                    <p className="text-[13px] italic text-content-subtle">This note has no content.</p>
                  )}
                </div>

                <div className="mt-6 flex flex-col gap-3 border-t border-border pt-4 sm:flex-row sm:items-center sm:justify-between">
                  <span className="text-[12px] text-content-subtle">Updated {formatDateTime(selected.updated_at)}</span>
                  <button
                    disabled
                    title="AI is not configured in this MVP"
                    className="inline-flex cursor-not-allowed items-center gap-1.5 rounded-md border border-secondary/30 bg-secondary/10 px-2.5 py-1.5 text-[12px] text-secondary-soft opacity-70"
                  >
                    <Sparkles size={13} /> Summarize (AI not configured)
                  </button>
                </div>
              </div>
            ) : (
              <EmptyState
                title="Select a note"
                description="Choose an entry from the list to read it here."
                icon={<StickyNote size={20} />}
              />
            )}
          </Card>
        </div>
      )}

      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title="New note"
        size="lg"
        footer={
          <>
            <Button variant="ghost" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button form="note-form" type="submit" loading={saving} disabled={!form.title.trim()}>
              Create note
            </Button>
          </>
        }
      >
        <form id="note-form" onSubmit={create} className="space-y-4">
          <Input
            id="title"
            label="Title"
            required
            placeholder="Note title"
            value={form.title}
            onChange={(e) => setForm({ ...form, title: e.target.value })}
          />
          <Textarea
            id="content"
            label="Content"
            placeholder="Write your note…"
            className="min-h-[160px]"
            value={form.content}
            onChange={(e) => setForm({ ...form, content: e.target.value })}
          />
          <Input
            id="tags"
            label="Tags (comma-separated)"
            placeholder="architecture, security"
            value={form.tags}
            onChange={(e) => setForm({ ...form, tags: e.target.value })}
          />
          <label className="flex items-center gap-2 text-[13px] text-content-muted">
            <input
              type="checkbox"
              checked={form.is_pinned}
              onChange={(e) => setForm({ ...form, is_pinned: e.target.checked })}
              className="h-4 w-4 rounded border-border bg-surface-input accent-primary"
            />
            Pin this note
          </label>
        </form>
      </Modal>
    </AppShell>
  );
}
