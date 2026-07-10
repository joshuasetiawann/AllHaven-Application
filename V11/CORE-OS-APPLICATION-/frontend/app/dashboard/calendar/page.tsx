"use client";

import { useEffect, useMemo, useState } from "react";
import { CalendarDays, Clock, MapPin, Pencil, Plus, Trash2 } from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { PageHeader } from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { Textarea } from "@/components/ui/Textarea";
import { Badge } from "@/components/ui/Badge";
import { Toggle } from "@/components/ui/Toggle";
import { Modal } from "@/components/ui/Modal";
import { EmptyState, ErrorState, Loading } from "@/components/ui/States";
import { calendarApi, ApiException } from "@/lib/api";
import type { CalendarEvent } from "@/types";

interface EventForm {
  title: string;
  description: string;
  location: string;
  start_at: string;
  end_at: string;
  all_day: boolean;
}

const emptyForm: EventForm = {
  title: "",
  description: "",
  location: "",
  start_at: "",
  end_at: "",
  all_day: false,
};

// Convert an ISO string into the value a datetime-local input expects (local time).
function isoToLocalInput(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function dayKey(iso: string): string {
  const d = new Date(iso);
  return new Date(d.getFullYear(), d.getMonth(), d.getDate()).toISOString();
}

function formatDayHeading(iso: string): string {
  return new Date(iso).toLocaleDateString("en-US", {
    weekday: "long",
    month: "long",
    day: "numeric",
    year: "numeric",
  });
}

function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" });
}

export default function CalendarPage() {
  const [events, setEvents] = useState<CalendarEvent[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [editing, setEditing] = useState<CalendarEvent | null>(null);
  const [form, setForm] = useState<EventForm>(emptyForm);

  const load = async () => {
    setError(null);
    try {
      setEvents(await calendarApi.list());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load events.");
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const grouped = useMemo(() => {
    const list = [...(events ?? [])].sort(
      (a, b) => new Date(a.start_at).getTime() - new Date(b.start_at).getTime(),
    );
    const map = new Map<string, CalendarEvent[]>();
    for (const ev of list) {
      const key = dayKey(ev.start_at);
      const arr = map.get(key) ?? [];
      arr.push(ev);
      map.set(key, arr);
    }
    return Array.from(map.entries());
  }, [events]);

  const openCreate = () => {
    setEditing(null);
    setForm(emptyForm);
    setOpen(true);
  };

  const openEdit = (ev: CalendarEvent) => {
    setEditing(ev);
    setForm({
      title: ev.title,
      description: ev.description ?? "",
      location: ev.location ?? "",
      start_at: isoToLocalInput(ev.start_at),
      end_at: isoToLocalInput(ev.end_at),
      all_day: ev.all_day,
    });
    setOpen(true);
  };

  const save = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!form.title.trim() || !form.start_at) return;
    setSaving(true);
    try {
      const payload = {
        title: form.title,
        description: form.description || undefined,
        location: form.location || undefined,
        start_at: new Date(form.start_at).toISOString(),
        end_at: form.end_at ? new Date(form.end_at).toISOString() : undefined,
        all_day: form.all_day,
      };
      if (editing) {
        await calendarApi.update(editing.id, payload);
      } else {
        await calendarApi.create(payload);
      }
      setOpen(false);
      setForm(emptyForm);
      setEditing(null);
      await load();
    } catch (err) {
      setError(err instanceof ApiException ? err.message : "Failed to save event.");
    } finally {
      setSaving(false);
    }
  };

  const remove = async (ev: CalendarEvent) => {
    setEvents((prev) => prev?.filter((e) => e.id !== ev.id) ?? prev);
    try {
      await calendarApi.remove(ev.id);
    } catch {
      void load();
    }
  };

  return (
    <AppShell>
      <PageHeader
        title="Calendar"
        subtitle="Your workspace agenda."
        actions={
          <Button onClick={openCreate}>
            <Plus size={16} /> New event
          </Button>
        }
      />

      <Card className="mb-5" padding="sm">
        <p className="text-[12.5px] text-content-muted">
          Local events only — Google Calendar sync status is shown in Settings → Connected Tools.
        </p>
      </Card>

      {error ? (
        <ErrorState message={error} onRetry={load} />
      ) : !events ? (
        <Loading />
      ) : events.length === 0 ? (
        <EmptyState
          title="No events yet"
          description="Create your first event to start building your agenda."
          icon={<CalendarDays size={20} />}
          action={
            <Button onClick={openCreate}>
              <Plus size={16} /> New event
            </Button>
          }
        />
      ) : (
        <div className="space-y-6">
          {grouped.map(([key, dayEvents]) => (
            <div key={key}>
              <h2 className="mb-2.5 text-[13px] font-semibold uppercase tracking-wide text-content-muted">
                {formatDayHeading(key)}
              </h2>
              <div className="space-y-2.5">
                {dayEvents.map((ev) => (
                  <Card key={ev.id} className="p-4" hover>
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <p className="text-sm font-medium text-content">{ev.title}</p>
                          {ev.all_day ? <Badge tone="secondary">All day</Badge> : null}
                        </div>
                        <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-[12px] text-content-subtle">
                          {!ev.all_day ? (
                            <span className="inline-flex items-center gap-1">
                              <Clock size={12} />
                              {formatTime(ev.start_at)}
                              {ev.end_at ? ` – ${formatTime(ev.end_at)}` : ""}
                            </span>
                          ) : null}
                          {ev.location ? (
                            <span className="inline-flex items-center gap-1">
                              <MapPin size={12} /> {ev.location}
                            </span>
                          ) : null}
                        </div>
                        {ev.description ? (
                          <p className="mt-2 text-[13px] text-content-muted">{ev.description}</p>
                        ) : null}
                      </div>
                      <div className="flex shrink-0 items-center gap-1.5">
                        <button
                          onClick={() => openEdit(ev)}
                          className="rounded-md p-2 text-content-subtle transition-colors hover:text-primary"
                          aria-label="Edit event"
                        >
                          <Pencil size={15} />
                        </button>
                        <button
                          onClick={() => remove(ev)}
                          className="rounded-md p-2 text-content-subtle transition-colors hover:text-danger"
                          aria-label="Delete event"
                        >
                          <Trash2 size={15} />
                        </button>
                      </div>
                    </div>
                  </Card>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title={editing ? "Edit event" : "New event"}
        size="lg"
        footer={
          <>
            <Button variant="ghost" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button
              form="event-form"
              type="submit"
              loading={saving}
              disabled={!form.title.trim() || !form.start_at}
            >
              {editing ? "Save changes" : "Create event"}
            </Button>
          </>
        }
      >
        <form id="event-form" onSubmit={save} className="space-y-4">
          <Input
            id="title"
            label="Title"
            required
            placeholder="Event title"
            value={form.title}
            onChange={(e) => setForm({ ...form, title: e.target.value })}
          />
          <Textarea
            id="description"
            label="Description"
            placeholder="Optional details"
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
          />
          <Input
            id="location"
            label="Location"
            placeholder="Optional location"
            value={form.location}
            onChange={(e) => setForm({ ...form, location: e.target.value })}
          />
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <Input
              id="start_at"
              label="Start"
              type="datetime-local"
              required
              value={form.start_at}
              onChange={(e) => setForm({ ...form, start_at: e.target.value })}
            />
            <Input
              id="end_at"
              label="End (optional)"
              type="datetime-local"
              value={form.end_at}
              onChange={(e) => setForm({ ...form, end_at: e.target.value })}
            />
          </div>
          <label className="flex items-center gap-2 text-[13px] text-content-muted">
            <Toggle
              checked={form.all_day}
              onChange={(next) => setForm({ ...form, all_day: next })}
              label="All day"
            />
            All-day event
          </label>
        </form>
      </Modal>
    </AppShell>
  );
}
