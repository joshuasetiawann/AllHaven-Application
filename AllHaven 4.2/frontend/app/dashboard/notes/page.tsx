"use client";

import { useEffect, useMemo, useState } from "react";
import { ArrowLeft, Pencil, Pin, Plus, Search, Sparkles, StickyNote, Trash2 } from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { Textarea } from "@/components/ui/Textarea";
import { Modal } from "@/components/ui/Modal";
import { EmptyState, ErrorState, Loading } from "@/components/ui/States";
import { notesApi, ApiException } from "@/lib/api";
import { cn, formatDateTime, relativeTime } from "@/lib/format";
import type { Note } from "@/types";

/* Aurora category tints — cyan (work-ish), violet (ideas-ish), green (personal-ish). */
const TAG_TINTS = [
  {
    pill: "border-primary/30 bg-primary/10 text-primary-bright",
    tile: "bg-primary/10 text-primary-bright",
  },
  {
    pill: "border-secondary/30 bg-secondary/10 text-secondary-soft",
    tile: "bg-secondary/15 text-secondary-soft",
  },
  {
    pill: "border-success/30 bg-success/10 text-success-soft",
    tile: "bg-success/10 text-success-soft",
  },
] as const;

function tagTint(tag?: string) {
  if (!tag) return TAG_TINTS[0];
  const t = tag.toLowerCase();
  if (/work|project|meeting|client|finance|report/.test(t)) return TAG_TINTS[0];
  if (/idea|inspir|brainstorm|design|draft/.test(t)) return TAG_TINTS[1];
  if (/personal|health|home|life|family/.test(t)) return TAG_TINTS[2];
  let sum = 0;
  for (let i = 0; i < t.length; i += 1) sum += t.charCodeAt(i);
  return TAG_TINTS[sum % TAG_TINTS.length];
}

export default function NotesPage() {
  const [notes, setNotes] = useState<Note[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [mobileReader, setMobileReader] = useState(false);
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
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

  const startCreate = () => {
    setEditingId(null);
    setForm({ title: "", content: "", tags: "", is_pinned: false });
    setOpen(true);
  };

  const startEdit = (note: Note) => {
    setEditingId(note.id);
    setForm({
      title: note.title,
      content: note.content ?? "",
      tags: note.tags.join(", "),
      is_pinned: note.is_pinned,
    });
    setOpen(true);
  };

  const save = async (event: React.FormEvent) => {
    event.preventDefault();
    setSaving(true);
    try {
      const payload: Partial<Note> = {
        title: form.title.trim(),
        content: form.content.trim() ? form.content : null,
        tags: form.tags.split(",").map((t) => t.trim()).filter(Boolean),
        is_pinned: form.is_pinned,
      };
      const note = editingId
        ? await notesApi.update(editingId, payload)
        : await notesApi.create(payload);
      setOpen(false);
      setEditingId(null);
      setForm({ title: "", content: "", tags: "", is_pinned: false });
      await load();
      setSelectedId(note.id);
    } catch (err) {
      setError(err instanceof ApiException ? err.message : "Failed to save note.");
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

  const tagChips = Array.from(new Set((notes ?? []).flatMap((n) => n.tags))).slice(0, 4);
  const activeQuery = query.trim().toLowerCase();

  return (
    <AppShell>
      <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div className="min-w-0">
          <h1 className="text-2xl font-semibold tracking-[-0.02em] text-content sm:text-[30px]">Notes</h1>
          <p className="mt-2 text-[13.5px] text-content-muted">
            {notes
              ? `${notes.length} entries — searchable and local-first.`
              : "Your thoughts, meeting notes, and captured ideas — searchable and local-first."}
          </p>
        </div>
        <Button onClick={startCreate} className="w-full sm:w-auto">
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
            <Button onClick={startCreate}>
              <Plus size={16} /> New note
            </Button>
          }
        />
      ) : (
        <div>
          {/* Board: search + tag chips + masonry */}
          <div className={cn(mobileReader && "hidden")}>
            <div className="mb-[18px] flex flex-wrap items-center gap-2.5">
              <div className="w-full min-w-[240px] flex-1 sm:max-w-[420px]">
                <Input
                  leftIcon={<Search size={15} />}
                  placeholder="Search notes…"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                />
              </div>
              {tagChips.length > 0 ? (
                <div className="inline-flex max-w-full items-center gap-0.5 overflow-x-auto rounded-md border border-border bg-white/[0.03] p-[3px]">
                  <button
                    onClick={() => setQuery("")}
                    className={cn(
                      "rounded-sm border px-3 py-1.5 text-[12.5px] transition-colors",
                      !activeQuery
                        ? "border-primary/30 bg-gradient-to-r from-primary/20 to-secondary/10 font-semibold text-content"
                        : "border-transparent text-content-muted hover:text-content",
                    )}
                  >
                    All
                  </button>
                  {tagChips.map((tag) => (
                    <button
                      key={tag}
                      onClick={() => setQuery(tag)}
                      className={cn(
                        "whitespace-nowrap rounded-sm border px-3 py-1.5 text-[12.5px] transition-colors",
                        activeQuery === tag.toLowerCase()
                          ? "border-primary/30 bg-gradient-to-r from-primary/20 to-secondary/10 font-semibold text-content"
                          : "border-transparent text-content-muted hover:text-content",
                      )}
                    >
                      {tag}
                    </button>
                  ))}
                </div>
              ) : null}
            </div>

            <div className="columns-1 gap-4 md:columns-2 xl:columns-3">
              {filtered.map((note) => (
                <button
                  key={note.id}
                  onClick={() => openNote(note.id)}
                  className={cn(
                    "panel-hover mb-4 block w-full break-inside-avoid p-[18px] text-left",
                    note.is_pinned ? "panel-gradient" : "panel",
                    note.id === selectedId && "border-primary/40",
                  )}
                >
                  <div className="mb-2.5 flex items-center justify-between gap-2">
                    {note.is_pinned ? (
                      <span className="inline-flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-[0.08em] text-primary-bright">
                        <Pin size={12} fill="currentColor" /> Pinned
                      </span>
                    ) : (
                      <span
                        className={cn(
                          "flex h-7 w-7 items-center justify-center rounded-[9px]",
                          tagTint(note.tags[0]).tile,
                        )}
                      >
                        <StickyNote size={14} />
                      </span>
                    )}
                  </div>
                  <h3 className="break-words text-[15px] font-semibold text-content">{note.title}</h3>
                  {note.content ? (
                    <p className="mt-2 line-clamp-3 text-[12.5px] leading-[1.6] text-content-muted">
                      {note.content}
                    </p>
                  ) : null}
                  <div className="mt-3 flex items-center gap-2">
                    {note.tags.length > 0 ? (
                      <div className="hidden min-w-0 flex-wrap gap-1.5 sm:flex">
                        {note.tags.slice(0, 3).map((tag) => (
                          <span
                            key={tag}
                            className={cn(
                              "rounded-full border px-2.5 py-0.5 text-[10.5px]",
                              tagTint(tag).pill,
                            )}
                          >
                            {tag}
                          </span>
                        ))}
                      </div>
                    ) : null}
                    <span className="ml-auto shrink-0 text-[11px] text-content-faint">
                      {relativeTime(note.updated_at)}
                    </span>
                  </div>
                </button>
              ))}
            </div>
            {filtered.length === 0 ? (
              <p className="py-6 text-center text-[13px] text-content-muted">No notes match &quot;{query}&quot;.</p>
            ) : null}
          </div>

          {/* Reader */}
          <Card
            className={cn("mx-auto min-h-[400px] w-full max-w-3xl", !mobileReader && "hidden")}
            padding="lg"
          >
            {selected ? (
              <div className="animate-fade-in">
                <button
                  onClick={() => setMobileReader(false)}
                  className="mb-5 inline-flex items-center gap-1.5 text-[13px] text-content-muted transition-colors hover:text-primary-bright"
                >
                  <ArrowLeft size={15} /> All notes
                </button>
                <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                  <div className="min-w-0">
                    <p
                      className={cn(
                        "label-mono inline-flex items-center gap-1.5",
                        selected.is_pinned && "text-primary-bright",
                      )}
                    >
                      {selected.is_pinned ? (
                        <>
                          <Pin size={11} fill="currentColor" /> Pinned note
                        </>
                      ) : (
                        "Note entry"
                      )}
                    </p>
                    <h2 className="mt-1.5 break-words text-xl font-semibold tracking-tight text-content">
                      {selected.title}
                    </h2>
                  </div>
                  <div className="flex shrink-0 items-center gap-1.5">
                    <button
                      onClick={() => startEdit(selected)}
                      className="rounded-[10px] border border-border bg-white/[0.03] p-2 text-content-subtle transition-colors hover:border-primary/40 hover:text-primary-bright"
                      aria-label="Edit note"
                    >
                      <Pencil size={15} />
                    </button>
                    <button
                      onClick={() => togglePin(selected)}
                      className={cn(
                        "rounded-[10px] border p-2 transition-colors",
                        selected.is_pinned
                          ? "border-primary/40 bg-primary/10 text-primary-bright"
                          : "border-border bg-white/[0.03] text-content-subtle hover:border-border-strong hover:text-content",
                      )}
                      aria-label="Pin note"
                    >
                      <Pin size={15} fill={selected.is_pinned ? "currentColor" : "none"} />
                    </button>
                    <button
                      onClick={() => remove(selected)}
                      className="rounded-[10px] border border-border bg-white/[0.03] p-2 text-content-subtle transition-colors hover:border-danger/40 hover:text-danger"
                      aria-label="Delete note"
                    >
                      <Trash2 size={15} />
                    </button>
                  </div>
                </div>

                {selected.tags.length > 0 ? (
                  <div className="mt-3 flex flex-wrap gap-1.5">
                    {selected.tags.map((tag) => (
                      <span
                        key={tag}
                        className={cn("rounded-full border px-2.5 py-0.5 text-[10.5px]", tagTint(tag).pill)}
                      >
                        {tag}
                      </span>
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
                    className="inline-flex cursor-not-allowed items-center gap-1.5 rounded-[10px] border border-secondary/30 bg-secondary/10 px-2.5 py-1.5 text-[12px] text-secondary-soft opacity-70"
                  >
                    <Sparkles size={13} /> Summarize (AI not configured)
                  </button>
                </div>
              </div>
            ) : (
              <EmptyState
                title="Select a note"
                description="Choose an entry from the board to read it here."
                icon={<StickyNote size={20} />}
              />
            )}
          </Card>
        </div>
      )}

      <Modal
        open={open}
        onClose={() => {
          setOpen(false);
          setEditingId(null);
        }}
        title={editingId ? "Edit note" : "New note"}
        size="lg"
        footer={
          <>
            <Button
              variant="ghost"
              onClick={() => {
                setOpen(false);
                setEditingId(null);
              }}
            >
              Cancel
            </Button>
            <Button form="note-form" type="submit" loading={saving} disabled={!form.title.trim()}>
              {editingId ? "Save changes" : "Create note"}
            </Button>
          </>
        }
      >
        <form id="note-form" onSubmit={save} className="space-y-4">
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
            placeholder="work, ideas"
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
