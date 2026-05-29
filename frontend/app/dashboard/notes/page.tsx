"use client";

import { useEffect, useState } from "react";
import { Pin, Plus, StickyNote, Trash2 } from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Input } from "@/components/ui/Input";
import { Textarea } from "@/components/ui/Textarea";
import { Modal } from "@/components/ui/Modal";
import { Loading, ErrorState, EmptyState } from "@/components/ui/States";
import { notesApi, ApiException } from "@/lib/api";
import { formatDateTime, cn } from "@/lib/format";
import type { Note } from "@/types";

export default function NotesPage() {
  const [notes, setNotes] = useState<Note[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({ title: "", content: "", tags: "", is_pinned: false });

  const load = async () => {
    setError(null);
    try {
      setNotes(await notesApi.list());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load notes.");
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const create = async (event: React.FormEvent) => {
    event.preventDefault();
    setSaving(true);
    try {
      await notesApi.create({
        title: form.title,
        content: form.content || undefined,
        tags: form.tags
          .split(",")
          .map((t) => t.trim())
          .filter(Boolean),
        is_pinned: form.is_pinned,
      });
      setOpen(false);
      setForm({ title: "", content: "", tags: "", is_pinned: false });
      await load();
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
    } catch {
      void load();
    }
  };

  const remove = async (note: Note) => {
    setNotes((prev) => prev?.filter((n) => n.id !== note.id) ?? prev);
    try {
      await notesApi.remove(note.id);
    } catch {
      void load();
    }
  };

  return (
    <AppShell title="Notes" subtitle="Capture knowledge — pinned, tagged, and audited">
      <div className="mb-5 flex items-center justify-between">
        <p className="text-[13px] text-content-muted">
          {notes ? `${notes.length} note${notes.length === 1 ? "" : "s"}` : "—"}
        </p>
        <Button onClick={() => setOpen(true)}>
          <Plus size={16} /> New note
        </Button>
      </div>

      {error ? (
        <ErrorState message={error} onRetry={load} />
      ) : !notes ? (
        <Loading />
      ) : notes.length === 0 ? (
        <EmptyState
          title="No notes yet"
          description="Write down ideas, meeting notes, or plans."
          icon={<StickyNote size={20} />}
          action={
            <Button onClick={() => setOpen(true)}>
              <Plus size={16} /> New note
            </Button>
          }
        />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {notes.map((note) => (
            <Card key={note.id} hover className="flex flex-col">
              <div className="mb-2 flex items-start justify-between gap-2">
                <h3 className="text-sm font-semibold text-content">{note.title}</h3>
                <div className="flex shrink-0 items-center gap-1.5">
                  <button
                    onClick={() => togglePin(note)}
                    className={cn(
                      "transition-colors",
                      note.is_pinned ? "text-primary" : "text-content-subtle hover:text-content",
                    )}
                    aria-label="Pin note"
                  >
                    <Pin size={15} fill={note.is_pinned ? "currentColor" : "none"} />
                  </button>
                  <button
                    onClick={() => remove(note)}
                    className="text-content-subtle transition-colors hover:text-danger"
                    aria-label="Delete note"
                  >
                    <Trash2 size={15} />
                  </button>
                </div>
              </div>
              {note.content ? (
                <p className="line-clamp-4 whitespace-pre-wrap text-[13px] text-content-muted">
                  {note.content}
                </p>
              ) : (
                <p className="text-[13px] italic text-content-subtle">No content</p>
              )}
              {note.tags.length > 0 ? (
                <div className="mt-3 flex flex-wrap gap-1.5">
                  {note.tags.map((tag) => (
                    <Badge key={tag} tone="secondary">
                      {tag}
                    </Badge>
                  ))}
                </div>
              ) : null}
              <p className="mt-3 label-mono">{formatDateTime(note.updated_at)}</p>
            </Card>
          ))}
        </div>
      )}

      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title="New note"
        footer={
          <>
            <Button variant="ghost" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button form="note-form" type="submit" disabled={saving || !form.title.trim()}>
              {saving ? "Saving…" : "Create note"}
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
            value={form.content}
            onChange={(e) => setForm({ ...form, content: e.target.value })}
          />
          <Input
            id="tags"
            label="Tags (comma-separated)"
            placeholder="planning, strategy"
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
