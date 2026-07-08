"use client";

import { useEffect, useMemo, useState } from "react";
import {
  CalendarDays,
  CheckCircle2,
  Clock,
  MapPin,
  Pencil,
  Plus,
  Repeat2,
  Trash2,
} from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { PageHeader } from "@/components/layout/PageHeader";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardHeader } from "@/components/ui/Card";
import { EmptyState, ErrorState, Loading } from "@/components/ui/States";
import { Input } from "@/components/ui/Input";
import { Modal } from "@/components/ui/Modal";
import { Textarea } from "@/components/ui/Textarea";
import { Toggle } from "@/components/ui/Toggle";
import { ApiException, routinesApi } from "@/lib/api";
import { cn } from "@/lib/format";
import type { RoutineEvent } from "@/types";

type ViewMode = "today" | "selected" | "upcoming" | "all";

interface RoutineForm {
  title: string;
  description: string;
  location: string;
  start_at: string;
  end_at: string;
  all_day: boolean;
}

const emptyForm: RoutineForm = {
  title: "",
  description: "",
  location: "",
  start_at: "",
  end_at: "",
  all_day: false,
};

function pad(value: number): string {
  return String(value).padStart(2, "0");
}

function dateKey(date: Date): string {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

function startOfLocalDay(date: Date): Date {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate());
}

function addDays(date: Date, days: number): Date {
  const next = new Date(date);
  next.setDate(next.getDate() + days);
  return next;
}

function isoToLocalInput(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function defaultStartFor(dateKeyValue: string): string {
  const now = new Date();
  const hour = dateKey(now) === dateKeyValue ? Math.min(now.getHours() + 1, 23) : 9;
  return `${dateKeyValue}T${pad(hour)}:00`;
}

function formatDay(date: Date): string {
  return date.toLocaleDateString("en-US", { weekday: "long", month: "short", day: "numeric" });
}

function formatLongDay(key: string): string {
  return new Date(`${key}T00:00:00`).toLocaleDateString("en-US", {
    weekday: "long",
    month: "long",
    day: "numeric",
    year: "numeric",
  });
}

function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" });
}

function eventDayKey(event: RoutineEvent): string {
  return dateKey(new Date(event.start_at));
}

function isToday(event: RoutineEvent): boolean {
  return eventDayKey(event) === dateKey(new Date());
}

function eventStatus(event: RoutineEvent): "past" | "now" | "upcoming" {
  const now = Date.now();
  const startDate = new Date(event.start_at);
  if (event.all_day) {
    const start = startOfLocalDay(startDate).getTime();
    const end = addDays(startOfLocalDay(startDate), 1).getTime() - 1;
    if (end < now) return "past";
    if (start <= now && now <= end) return "now";
    return "upcoming";
  }
  const start = startDate.getTime();
  const end = event.end_at ? new Date(event.end_at).getTime() : start;
  if (end < now) return "past";
  if (start <= now && now <= end) return "now";
  return "upcoming";
}

function RoutineCard({
  routine,
  onEdit,
  onDelete,
}: {
  routine: RoutineEvent;
  onEdit: (routine: RoutineEvent) => void;
  onDelete: (routine: RoutineEvent) => void;
}) {
  const status = eventStatus(routine);
  return (
    <Card className="p-4" hover>
      <div className="flex items-start gap-3">
        <div
          className={cn(
            "flex h-11 w-11 shrink-0 flex-col items-center justify-center rounded-xl border font-mono text-[11px]",
            status === "past"
              ? "border-border bg-surface-input text-content-subtle"
              : "border-primary/25 bg-primary/10 text-primary",
          )}
        >
          {routine.all_day ? "ALL" : formatTime(routine.start_at)}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <p className="min-w-0 truncate text-sm font-semibold text-content">{routine.title}</p>
            {routine.all_day ? <Badge tone="secondary">All day</Badge> : null}
            {status === "now" ? <Badge tone="success" dot>Now</Badge> : null}
            {status === "past" ? <Badge tone="neutral">Done window</Badge> : null}
          </div>
          <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-[12px] text-content-subtle">
            <span className="inline-flex items-center gap-1">
              <Clock size={12} />
              {routine.all_day ? formatLongDay(eventDayKey(routine)) : `${formatTime(routine.start_at)}${routine.end_at ? ` - ${formatTime(routine.end_at)}` : ""}`}
            </span>
            {routine.location ? (
              <span className="inline-flex items-center gap-1">
                <MapPin size={12} /> {routine.location}
              </span>
            ) : null}
          </div>
          {routine.description ? (
            <p className="mt-2 text-[13px] leading-relaxed text-content-muted">{routine.description}</p>
          ) : null}
        </div>
        <div className="flex shrink-0 items-center gap-1">
          <button
            onClick={() => onEdit(routine)}
            className="rounded-lg p-2 text-content-subtle transition-colors hover:bg-surface-high hover:text-primary focus-ring"
            aria-label="Edit routine"
          >
            <Pencil size={15} />
          </button>
          <button
            onClick={() => onDelete(routine)}
            className="rounded-lg p-2 text-content-subtle transition-colors hover:bg-danger/10 hover:text-danger focus-ring"
            aria-label="Delete routine"
          >
            <Trash2 size={15} />
          </button>
        </div>
      </div>
    </Card>
  );
}

export default function RoutinesPage() {
  const todayKey = dateKey(new Date());
  const [routines, setRoutines] = useState<RoutineEvent[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [view, setView] = useState<ViewMode>("today");
  const [selectedDate, setSelectedDate] = useState(todayKey);
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [editing, setEditing] = useState<RoutineEvent | null>(null);
  const [form, setForm] = useState<RoutineForm>(emptyForm);

  const load = async () => {
    setError(null);
    try {
      setRoutines(await routinesApi.list());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load routines.");
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const sorted = useMemo(
    () => [...(routines ?? [])].sort((a, b) => new Date(a.start_at).getTime() - new Date(b.start_at).getTime()),
    [routines],
  );

  const dayStrip = useMemo(() => {
    const base = startOfLocalDay(new Date());
    return Array.from({ length: 7 }, (_, index) => addDays(base, index));
  }, []);

  const todayRoutines = useMemo(() => sorted.filter(isToday), [sorted]);
  const upcomingRoutines = useMemo(
    () => sorted.filter((routine) => eventStatus(routine) !== "past"),
    [sorted],
  );
  const selectedRoutines = useMemo(
    () => sorted.filter((routine) => eventDayKey(routine) === selectedDate),
    [selectedDate, sorted],
  );
  const visibleRoutines = useMemo(() => {
    if (view === "today") return todayRoutines;
    if (view === "selected") return selectedRoutines;
    if (view === "upcoming") return upcomingRoutines;
    return sorted;
  }, [selectedRoutines, sorted, todayRoutines, upcomingRoutines, view]);

  const grouped = useMemo(() => {
    const map = new Map<string, RoutineEvent[]>();
    for (const routine of visibleRoutines) {
      const key = eventDayKey(routine);
      const list = map.get(key) ?? [];
      list.push(routine);
      map.set(key, list);
    }
    return Array.from(map.entries());
  }, [visibleRoutines]);

  const nextRoutine = upcomingRoutines[0] ?? null;

  const openCreate = (dateValue = selectedDate) => {
    setEditing(null);
    setForm({ ...emptyForm, start_at: defaultStartFor(dateValue) });
    setOpen(true);
  };

  const openEdit = (routine: RoutineEvent) => {
    setEditing(routine);
    setForm({
      title: routine.title,
      description: routine.description ?? "",
      location: routine.location ?? "",
      start_at: isoToLocalInput(routine.start_at),
      end_at: isoToLocalInput(routine.end_at),
      all_day: routine.all_day,
    });
    setOpen(true);
  };

  const save = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!form.title.trim() || !form.start_at) return;
    setSaving(true);
    try {
      const payload = {
        title: form.title.trim(),
        description: form.description.trim() || undefined,
        location: form.location.trim() || undefined,
        start_at: new Date(form.start_at).toISOString(),
        end_at: form.end_at ? new Date(form.end_at).toISOString() : undefined,
        all_day: form.all_day,
      };
      if (editing) {
        await routinesApi.update(editing.id, payload);
      } else {
        await routinesApi.create(payload);
      }
      setOpen(false);
      setForm(emptyForm);
      setEditing(null);
      await load();
    } catch (err) {
      setError(err instanceof ApiException ? err.message : "Failed to save routine.");
    } finally {
      setSaving(false);
    }
  };

  const remove = async (routine: RoutineEvent) => {
    setRoutines((prev) => prev?.filter((item) => item.id !== routine.id) ?? prev);
    try {
      await routinesApi.remove(routine.id);
    } catch {
      void load();
    }
  };

  return (
    <AppShell>
      <PageHeader
        title="Routine"
        subtitle="A schedule board for routines and time-based plans. Tasks stay for work items; Routine keeps the day and hour clear."
        actions={
          <Button onClick={() => openCreate(todayKey)}>
            <Plus size={16} /> Add routine
          </Button>
        }
      />

      {error ? (
        <ErrorState message={error} onRetry={load} />
      ) : !routines ? (
        <Loading label="Loading routines..." />
      ) : (
        <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
          <section className="space-y-5">
            <Card gradient padding="lg">
              <div className="mb-5 flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                <div className="min-w-0">
                  <div className="mb-2 flex flex-wrap items-center gap-2">
                    <Badge tone="primary" dot>Today</Badge>
                    <Badge tone="neutral">Any date, exact time</Badge>
                  </div>
                  <h2 className="text-xl font-semibold tracking-tight text-content">
                    {formatLongDay(selectedDate)}
                  </h2>
                  <p className="mt-1 text-[13px] text-content-muted">
                    Pick a day, add the hour, and keep recurring life/work rhythms away from task clutter.
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button variant="ghost" onClick={() => setView("today")}>
                    Today
                  </Button>
                  <Button variant="ghost" onClick={() => setView("upcoming")}>
                    Upcoming
                  </Button>
                  <Button variant="ghost" onClick={() => setView("all")}>
                    All
                  </Button>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-7">
                {dayStrip.map((day) => {
                  const key = dateKey(day);
                  const count = sorted.filter((routine) => eventDayKey(routine) === key).length;
                  const active = selectedDate === key;
                  return (
                    <button
                      key={key}
                      onClick={() => {
                        setSelectedDate(key);
                        setView("selected");
                      }}
                      className={cn(
                        "rounded-xl border p-3 text-left transition-all focus-ring",
                        active
                          ? "border-primary/45 bg-primary/12 text-content shadow-glow-primary"
                          : "border-border bg-surface-input/55 text-content-muted hover:border-border-strong hover:bg-surface-raised/70 hover:text-content",
                      )}
                    >
                      <span className="block text-[11px] uppercase tracking-wide text-content-subtle">
                        {day.toLocaleDateString("en-US", { weekday: "short" })}
                      </span>
                      <span className="mt-1 block text-lg font-semibold text-content">{day.getDate()}</span>
                      <span className="mt-1 block text-[11px] text-content-subtle">
                        {count ? `${count} routine${count > 1 ? "s" : ""}` : "Open"}
                      </span>
                    </button>
                  );
                })}
              </div>
            </Card>

            <div className="grid gap-3 sm:grid-cols-3">
              <Card className="p-4">
                <div className="mb-3 flex h-9 w-9 items-center justify-center rounded-lg border border-primary/20 bg-primary/10 text-primary">
                  <CalendarDays size={17} />
                </div>
                <p className="text-[11px] uppercase tracking-wide text-content-subtle">Today</p>
                <p className="mt-1 text-2xl font-semibold text-content">{todayRoutines.length}</p>
              </Card>
              <Card className="p-4">
                <div className="mb-3 flex h-9 w-9 items-center justify-center rounded-lg border border-success/20 bg-success/10 text-success">
                  <CheckCircle2 size={17} />
                </div>
                <p className="text-[11px] uppercase tracking-wide text-content-subtle">Upcoming</p>
                <p className="mt-1 text-2xl font-semibold text-content">{upcomingRoutines.length}</p>
              </Card>
              <Card className="p-4">
                <div className="mb-3 flex h-9 w-9 items-center justify-center rounded-lg border border-secondary/25 bg-secondary/10 text-secondary-soft">
                  <Repeat2 size={17} />
                </div>
                <p className="text-[11px] uppercase tracking-wide text-content-subtle">All-day</p>
                <p className="mt-1 text-2xl font-semibold text-content">
                  {sorted.filter((routine) => routine.all_day).length}
                </p>
              </Card>
            </div>

            {visibleRoutines.length === 0 ? (
              <EmptyState
                title="No routines in this view"
                description="Add a routine with a date and time, or switch to another view."
                icon={<Repeat2 size={20} />}
                action={
                  <Button onClick={() => openCreate(view === "today" ? todayKey : selectedDate)}>
                    <Plus size={16} /> Add routine
                  </Button>
                }
              />
            ) : (
              <div className="space-y-6">
                {grouped.map(([key, routinesForDay]) => (
                  <div key={key}>
                    <div className="mb-2.5 flex items-center justify-between gap-3">
                      <h2 className="text-[13px] font-semibold uppercase tracking-wide text-content-muted">
                        {formatLongDay(key)}
                      </h2>
                      <Badge tone={key === todayKey ? "primary" : "neutral"}>
                        {routinesForDay.length} item{routinesForDay.length > 1 ? "s" : ""}
                      </Badge>
                    </div>
                    <div className="space-y-2.5">
                      {routinesForDay.map((routine) => (
                        <RoutineCard
                          key={routine.id}
                          routine={routine}
                          onEdit={openEdit}
                          onDelete={remove}
                        />
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>

          <aside className="space-y-5">
            <Card>
              <CardHeader
                title="Next routine"
                subtitle={nextRoutine ? formatDay(new Date(nextRoutine.start_at)) : "No upcoming schedule"}
                icon={<Clock size={18} />}
              />
              {nextRoutine ? (
                <div className="rounded-xl border border-primary/20 bg-primary/10 p-4">
                  <p className="text-[15px] font-semibold text-content">{nextRoutine.title}</p>
                  <p className="mt-1 text-[13px] text-primary">
                    {nextRoutine.all_day ? "All day" : `${formatTime(nextRoutine.start_at)}${nextRoutine.end_at ? ` - ${formatTime(nextRoutine.end_at)}` : ""}`}
                  </p>
                  {nextRoutine.description ? (
                    <p className="mt-2 text-[13px] leading-relaxed text-content-muted">
                      {nextRoutine.description}
                    </p>
                  ) : null}
                </div>
              ) : (
                <p className="text-[13px] text-content-muted">Your next routine will show here after you add one.</p>
              )}
            </Card>

            <Card>
              <CardHeader title="Jump to date" subtitle="Plan today, tomorrow, or far ahead." icon={<CalendarDays size={18} />} />
              <Input
                id="routine-date"
                label="Selected day"
                type="date"
                value={selectedDate}
                onChange={(event) => {
                  setSelectedDate(event.target.value || todayKey);
                  setView("selected");
                }}
              />
              <div className="mt-3 flex flex-wrap gap-2">
                <Button variant="ghost" size="sm" onClick={() => openCreate(selectedDate)}>
                  <Plus size={14} /> Add here
                </Button>
                <Button
                  variant="subtle"
                  size="sm"
                  onClick={() => {
                    setSelectedDate(todayKey);
                    setView("today");
                  }}
                >
                  Today
                </Button>
              </div>
            </Card>

            <Card>
              <CardHeader title="Routine vs Task" icon={<Repeat2 size={18} />} />
              <div className="space-y-3 text-[13px] leading-relaxed text-content-muted">
                <p>
                  Use <span className="font-medium text-content">Routine</span> for schedule blocks with dates and hours.
                </p>
                <p>
                  Use <span className="font-medium text-content">Tasks</span> for work items, checklists, and things that need progress tracking.
                </p>
              </div>
            </Card>
          </aside>
        </div>
      )}

      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title={editing ? "Edit routine" : "Add routine"}
        description="Set the date, start time, and optional end time."
        size="lg"
        footer={
          <>
            <Button variant="ghost" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button
              form="routine-form"
              type="submit"
              loading={saving}
              disabled={!form.title.trim() || !form.start_at}
            >
              {editing ? "Save routine" : "Create routine"}
            </Button>
          </>
        }
      >
        <form id="routine-form" onSubmit={save} className="space-y-4">
          <Input
            id="title"
            label="Routine title"
            required
            placeholder="Morning review, class, workout, client call..."
            value={form.title}
            onChange={(event) => setForm({ ...form, title: event.target.value })}
          />
          <Textarea
            id="description"
            label="Notes"
            placeholder="What should happen during this routine?"
            value={form.description}
            onChange={(event) => setForm({ ...form, description: event.target.value })}
          />
          <Input
            id="location"
            label="Place or context"
            placeholder="Home, campus, office, online..."
            value={form.location}
            onChange={(event) => setForm({ ...form, location: event.target.value })}
          />
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <Input
              id="start_at"
              label="Start"
              type="datetime-local"
              required
              value={form.start_at}
              onChange={(event) => setForm({ ...form, start_at: event.target.value })}
            />
            <Input
              id="end_at"
              label="End"
              type="datetime-local"
              value={form.end_at}
              onChange={(event) => setForm({ ...form, end_at: event.target.value })}
            />
          </div>
          <label className="flex items-center gap-2 text-[13px] text-content-muted">
            <Toggle
              checked={form.all_day}
              onChange={(next) => setForm({ ...form, all_day: next })}
              label="All day"
            />
            All-day routine
          </label>
        </form>
      </Modal>
    </AppShell>
  );
}
