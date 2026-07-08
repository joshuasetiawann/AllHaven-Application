"use client";

import { useEffect, useMemo, useState } from "react";
import type { ComponentType, FormEvent } from "react";
import {
  BookOpen,
  Briefcase,
  CalendarDays,
  CheckCircle2,
  Clock,
  Coffee,
  Dumbbell,
  Flame,
  MapPin,
  Moon,
  Pencil,
  Plus,
  Repeat2,
  Sparkles,
  Star,
  SunMedium,
  Trash2,
} from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { PageHeader } from "@/components/layout/PageHeader";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardHeader } from "@/components/ui/Card";
import { Loading } from "@/components/ui/States";
import { Input } from "@/components/ui/Input";
import { Modal } from "@/components/ui/Modal";
import { Textarea } from "@/components/ui/Textarea";
import { Toggle } from "@/components/ui/Toggle";
import { ApiException, routinesApi } from "@/lib/api";
import { cn } from "@/lib/format";
import type { RoutineEvent } from "@/types";

type ViewMode = "today" | "selected" | "upcoming" | "all";
type TimePeriod = "morning" | "afternoon" | "evening";
type RepeatRule = "once" | "daily" | "weekly" | "monthly";

interface RoutineForm {
  title: string;
  description: string;
  location: string;
  start_at: string;
  end_at: string;
  all_day: boolean;
  time_period: TimePeriod;
  repeat_rule: RepeatRule;
  repeat_days: string[];
  icon: string;
  color: string;
}

const ICON_OPTIONS: { key: string; label: string; Icon: ComponentType<{ size?: number; className?: string }> }[] = [
  { key: "star", label: "Focus", Icon: Star },
  { key: "sparkles", label: "Create", Icon: Sparkles },
  { key: "book", label: "Study", Icon: BookOpen },
  { key: "briefcase", label: "Work", Icon: Briefcase },
  { key: "dumbbell", label: "Health", Icon: Dumbbell },
  { key: "coffee", label: "Break", Icon: Coffee },
  { key: "flame", label: "Priority", Icon: Flame },
  { key: "moon", label: "Rest", Icon: Moon },
];

const COLOR_OPTIONS = [
  {
    key: "cyan",
    label: "Cyan",
    swatch: "bg-primary",
    soft: "border-primary/30 bg-primary/10 text-primary",
    line: "bg-primary",
  },
  {
    key: "violet",
    label: "Violet",
    swatch: "bg-secondary",
    soft: "border-secondary/35 bg-secondary/15 text-secondary-soft",
    line: "bg-secondary",
  },
  {
    key: "green",
    label: "Green",
    swatch: "bg-success",
    soft: "border-success/30 bg-success/10 text-success",
    line: "bg-success",
  },
  {
    key: "amber",
    label: "Amber",
    swatch: "bg-warning",
    soft: "border-warning/35 bg-warning/10 text-warning",
    line: "bg-warning",
  },
  {
    key: "rose",
    label: "Rose",
    swatch: "bg-danger",
    soft: "border-danger/35 bg-danger/10 text-danger",
    line: "bg-danger",
  },
] as const;

const PERIODS: { key: TimePeriod; label: string; helper: string; time: string; Icon: ComponentType<{ size?: number }> }[] = [
  { key: "morning", label: "Pagi", helper: "05.00-11.59", time: "07:00", Icon: SunMedium },
  { key: "afternoon", label: "Siang", helper: "12.00-16.59", time: "13:00", Icon: Coffee },
  { key: "evening", label: "Malam", helper: "17.00+", time: "19:00", Icon: Moon },
];

const DAYS = [
  { key: "mon", label: "Sen" },
  { key: "tue", label: "Sel" },
  { key: "wed", label: "Rab" },
  { key: "thu", label: "Kam" },
  { key: "fri", label: "Jum" },
  { key: "sat", label: "Sab" },
  { key: "sun", label: "Min" },
];

const emptyForm: RoutineForm = {
  title: "",
  description: "",
  location: "",
  start_at: "",
  end_at: "",
  all_day: false,
  time_period: "morning",
  repeat_rule: "daily",
  repeat_days: DAYS.map((day) => day.key),
  icon: "star",
  color: "cyan",
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

function periodFromHour(hour: number): TimePeriod {
  if (hour >= 5 && hour < 12) return "morning";
  if (hour >= 12 && hour < 17) return "afternoon";
  return "evening";
}

function periodFromRoutine(routine: RoutineEvent): TimePeriod {
  if (routine.time_period === "morning" || routine.time_period === "afternoon" || routine.time_period === "evening") {
    return routine.time_period;
  }
  return periodFromHour(new Date(routine.start_at).getHours());
}

function colorFor(key: string | null | undefined) {
  return COLOR_OPTIONS.find((item) => item.key === key) ?? COLOR_OPTIONS[0];
}

function iconFor(key: string | null | undefined) {
  return ICON_OPTIONS.find((item) => item.key === key) ?? ICON_OPTIONS[0];
}

function defaultStartFor(dateKeyValue: string, period: TimePeriod): string {
  const time = PERIODS.find((item) => item.key === period)?.time ?? "07:00";
  return `${dateKeyValue}T${time}`;
}

function setTimeOnInput(value: string, dateKeyValue: string, time: string): string {
  const date = value ? value.slice(0, 10) : dateKeyValue;
  return `${date}T${time}`;
}

function formatLongDay(key: string): string {
  return new Date(`${key}T00:00:00`).toLocaleDateString("id-ID", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

function formatShortDay(date: Date): string {
  return date.toLocaleDateString("id-ID", { weekday: "short", day: "numeric", month: "short" });
}

function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString("id-ID", { hour: "2-digit", minute: "2-digit" });
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

function repeatLabel(routine: RoutineEvent): string {
  const rule = routine.repeat_rule ?? "once";
  if (rule === "daily") return "Daily";
  if (rule === "weekly") return "Weekly";
  if (rule === "monthly") return "Monthly";
  return "Once";
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
  const period = PERIODS.find((item) => item.key === periodFromRoutine(routine)) ?? PERIODS[0];
  const color = colorFor(routine.color);
  const icon = iconFor(routine.icon);
  const Icon = icon.Icon;
  return (
    <article className="group relative overflow-hidden rounded-xl border border-border bg-surface/80 p-4 transition-all hover:border-border-strong hover:bg-surface-raised/80">
      <span className={cn("absolute inset-y-0 left-0 w-1", color.line)} />
      <div className="flex items-start gap-3 pl-1">
        <div className={cn("flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl border", color.soft)}>
          <Icon size={20} />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="min-w-0 truncate text-sm font-semibold text-content">{routine.title}</h3>
            {status === "now" ? <Badge tone="success" dot>Now</Badge> : null}
            {status === "past" ? <Badge tone="neutral">Past</Badge> : null}
          </div>
          <div className="mt-2 flex flex-wrap items-center gap-2 text-[12px] text-content-subtle">
            <Badge tone="secondary">{period.label}</Badge>
            <span className="inline-flex items-center gap-1">
              <Clock size={12} />
              {routine.all_day ? "All day" : `${formatTime(routine.start_at)}${routine.end_at ? ` - ${formatTime(routine.end_at)}` : ""}`}
            </span>
            <span className="inline-flex items-center gap-1">
              <Repeat2 size={12} />
              {repeatLabel(routine)}
            </span>
          </div>
          {routine.location ? (
            <p className="mt-2 inline-flex items-center gap-1 text-[12px] text-content-subtle">
              <MapPin size={12} /> {routine.location}
            </p>
          ) : null}
          {routine.description ? (
            <p className="mt-2 overflow-hidden text-ellipsis text-[13px] leading-relaxed text-content-muted">{routine.description}</p>
          ) : null}
        </div>
        <div className="flex shrink-0 items-center gap-1 opacity-100 transition-opacity sm:opacity-0 sm:group-hover:opacity-100">
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
    </article>
  );
}

function PeriodColumn({
  period,
  routines,
  onEdit,
  onDelete,
  onAdd,
}: {
  period: (typeof PERIODS)[number];
  routines: RoutineEvent[];
  onEdit: (routine: RoutineEvent) => void;
  onDelete: (routine: RoutineEvent) => void;
  onAdd: () => void;
}) {
  const Icon = period.Icon;
  return (
    <section className="min-h-[240px] rounded-2xl border border-border bg-surface-low/35 p-3">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <span className="flex h-9 w-9 items-center justify-center rounded-xl border border-primary/20 bg-primary/10 text-primary">
            <Icon size={17} />
          </span>
          <div>
            <h2 className="text-sm font-semibold text-content">{period.label}</h2>
            <p className="text-[11px] text-content-subtle">{period.helper}</p>
          </div>
        </div>
        <Badge tone={routines.length ? "primary" : "neutral"}>{routines.length}</Badge>
      </div>
      {routines.length ? (
        <div className="space-y-2.5">
          {routines.map((routine) => (
            <RoutineCard key={routine.id} routine={routine} onEdit={onEdit} onDelete={onDelete} />
          ))}
        </div>
      ) : (
        <button
          onClick={onAdd}
          className="flex min-h-[150px] w-full flex-col items-center justify-center rounded-xl border border-dashed border-border bg-surface-input/25 px-4 text-center text-content-subtle transition-colors hover:border-primary/40 hover:bg-primary/5 hover:text-primary focus-ring"
        >
          <Plus size={18} />
          <span className="mt-2 text-sm font-medium">Add {period.label.toLowerCase()} routine</span>
        </button>
      )}
    </section>
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

  const routinesByPeriod = useMemo(() => {
    const map: Record<TimePeriod, RoutineEvent[]> = { morning: [], afternoon: [], evening: [] };
    for (const routine of visibleRoutines) {
      map[periodFromRoutine(routine)].push(routine);
    }
    return map;
  }, [visibleRoutines]);

  const nextRoutine = upcomingRoutines[0] ?? null;

  const openCreate = (dateValue = selectedDate, period: TimePeriod = "morning") => {
    setEditing(null);
    setForm({ ...emptyForm, time_period: period, start_at: defaultStartFor(dateValue, period) });
    setOpen(true);
  };

  const openEdit = (routine: RoutineEvent) => {
    const period = periodFromRoutine(routine);
    setEditing(routine);
    setForm({
      title: routine.title,
      description: routine.description ?? "",
      location: routine.location ?? "",
      start_at: isoToLocalInput(routine.start_at),
      end_at: isoToLocalInput(routine.end_at),
      all_day: routine.all_day,
      time_period: period,
      repeat_rule: (routine.repeat_rule ?? "once") as RepeatRule,
      repeat_days: routine.repeat_days?.length ? routine.repeat_days : [],
      icon: routine.icon ?? "star",
      color: routine.color ?? "cyan",
    });
    setOpen(true);
  };

  const save = async (event: FormEvent) => {
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
        time_period: form.time_period,
        repeat_rule: form.repeat_rule,
        repeat_days: showRepeatDays ? form.repeat_days : [],
        icon: form.icon,
        color: form.color,
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

  const setPeriod = (period: TimePeriod) => {
    const time = PERIODS.find((item) => item.key === period)?.time ?? "07:00";
    setForm((current) => ({
      ...current,
      time_period: period,
      start_at: setTimeOnInput(current.start_at, selectedDate, time),
    }));
  };

  const allDaysSelected = form.repeat_days.length === DAYS.length;
  const showRepeatDays = form.repeat_rule === "daily" || form.repeat_rule === "weekly";
  const displayDate = view === "today" ? todayKey : selectedDate;

  return (
    <AppShell>
      <PageHeader
        title="Routine"
        subtitle="Jadwal pribadi yang tersimpan di database lokal AllHaven. Tidak perlu Google Calendar."
        actions={
          <Button onClick={() => openCreate(displayDate, "morning")}>
            <Plus size={16} /> Add routine
          </Button>
        }
      />

      {error ? (
        <div className="rounded-2xl border border-danger/35 bg-danger/10 p-6 text-center">
          <p className="text-sm font-semibold text-content">Routine belum bisa dimuat</p>
          <p className="mx-auto mt-2 max-w-xl text-[13px] leading-relaxed text-content-muted">
            Data Routine memakai database lokal. Kalau baru update, restart backend lalu coba lagi.
          </p>
          <Button className="mt-4" variant="danger" onClick={load}>
            Try again
          </Button>
        </div>
      ) : !routines ? (
        <Loading label="Loading routines..." />
      ) : (
        <div className="space-y-6">
          <section className="rounded-2xl border border-border bg-surface/70 p-4 sm:p-5">
            <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
              <div className="min-w-0">
                <div className="mb-2 flex flex-wrap items-center gap-2">
                  <Badge tone="primary" dot>Local DB</Badge>
                  <Badge tone="secondary">Pagi / Siang / Malam</Badge>
                  <Badge tone="neutral">{visibleRoutines.length} visible</Badge>
                </div>
                <h2 className="text-xl font-semibold tracking-tight text-content">{formatLongDay(displayDate)}</h2>
                <p className="mt-1 max-w-2xl text-sm leading-relaxed text-content-muted">
                  Buat rutinitas yang berulang, jadwal hari ini, atau rencana jauh ke depan. Tasks tetap untuk kerjaan; Routine untuk pola harian dan jam.
                </p>
              </div>
              <div className="grid gap-2 sm:grid-cols-[minmax(190px,1fr)_auto]">
                <Input
                  id="routine-date"
                  label="Pilih tanggal"
                  type="date"
                  value={selectedDate}
                  onChange={(event) => {
                    setSelectedDate(event.target.value || todayKey);
                    setView("selected");
                  }}
                />
                <Button className="self-end" variant="ghost" onClick={() => openCreate(selectedDate, "morning")}>
                  <Plus size={15} /> Add here
                </Button>
              </div>
            </div>

            <div className="mt-5 grid grid-cols-2 gap-2 md:grid-cols-4 xl:grid-cols-7">
              {dayStrip.map((day) => {
                const key = dateKey(day);
                const count = sorted.filter((routine) => eventDayKey(routine) === key).length;
                const active = selectedDate === key || (view === "today" && key === todayKey);
                return (
                  <button
                    key={key}
                    onClick={() => {
                      setSelectedDate(key);
                      setView(key === todayKey ? "today" : "selected");
                    }}
                    className={cn(
                      "rounded-xl border p-3 text-left transition-all focus-ring",
                      active
                        ? "border-primary/45 bg-primary/12 text-content shadow-glow-primary"
                        : "border-border bg-surface-input/45 text-content-muted hover:border-border-strong hover:bg-surface-raised/70 hover:text-content",
                    )}
                  >
                    <span className="block text-[11px] uppercase tracking-wide text-content-subtle">
                      {day.toLocaleDateString("id-ID", { weekday: "short" })}
                    </span>
                    <span className="mt-1 block text-lg font-semibold text-content">{day.getDate()}</span>
                    <span className="mt-1 block text-[11px] text-content-subtle">
                      {count ? `${count} routine` : "Open"}
                    </span>
                  </button>
                );
              })}
            </div>

            <div className="mt-4 flex flex-wrap gap-2">
              {[
                ["today", "Today"],
                ["selected", "Selected"],
                ["upcoming", "Upcoming"],
                ["all", "All"],
              ].map(([key, label]) => (
                <Button
                  key={key}
                  variant={view === key ? "primary" : "ghost"}
                  size="sm"
                  onClick={() => setView(key as ViewMode)}
                >
                  {label}
                </Button>
              ))}
            </div>
          </section>

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
              <p className="text-[11px] uppercase tracking-wide text-content-subtle">Repeat</p>
              <p className="mt-1 text-2xl font-semibold text-content">
                {sorted.filter((routine) => (routine.repeat_rule ?? "once") !== "once").length}
              </p>
            </Card>
          </div>

          {visibleRoutines.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-border bg-surface-low/35 px-4 py-3 text-sm text-content-muted">
              Pilih slot Pagi, Siang, atau Malam di bawah untuk mulai menyusun routine.
            </div>
          ) : null}

          <div className="grid gap-4 xl:grid-cols-3">
            {PERIODS.map((period) => (
              <PeriodColumn
                key={period.key}
                period={period}
                routines={routinesByPeriod[period.key]}
                onEdit={openEdit}
                onDelete={remove}
                onAdd={() => openCreate(displayDate, period.key)}
              />
            ))}
          </div>

          <aside className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_360px]">
            <Card>
              <CardHeader
                title="Next routine"
                subtitle={nextRoutine ? formatShortDay(new Date(nextRoutine.start_at)) : "No upcoming schedule"}
                icon={<Clock size={18} />}
              />
              {nextRoutine ? (
                <RoutineCard routine={nextRoutine} onEdit={openEdit} onDelete={remove} />
              ) : (
                <p className="text-[13px] text-content-muted">Routine berikutnya akan muncul setelah kamu menambahkan jadwal.</p>
              )}
            </Card>
            <Card>
              <CardHeader title="Storage" subtitle="Local-first schedule" icon={<Repeat2 size={18} />} />
              <div className="space-y-2 text-[13px] leading-relaxed text-content-muted">
                <p>Routine memakai database backend AllHaven, bukan Google Calendar.</p>
                <p>Jika nanti Supabase sync diaktifkan, data tetap lewat backend dan tidak mengirim status palsu.</p>
              </div>
            </Card>
          </aside>
        </div>
      )}

      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title={editing ? "Edit routine" : "Add routine"}
        description="Bangun rutinitas dengan nama, warna, repeat, dan slot waktu."
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
        <form id="routine-form" onSubmit={save} className="space-y-5">
          <Input
            id="title"
            label="Name your routine"
            required
            placeholder="Morning review, kuliah, gym, coding session..."
            value={form.title}
            onChange={(event) => setForm({ ...form, title: event.target.value })}
            className="h-12 text-base font-semibold"
          />

          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <p className="mb-2 text-[12px] font-medium uppercase tracking-wide text-content-muted">Icon</p>
              <div className="grid grid-cols-4 gap-2">
                {ICON_OPTIONS.map(({ key, label, Icon }) => (
                  <button
                    key={key}
                    type="button"
                    title={label}
                    onClick={() => setForm({ ...form, icon: key })}
                    className={cn(
                      "flex h-12 items-center justify-center rounded-xl border transition-colors focus-ring",
                      form.icon === key
                        ? "border-primary/50 bg-primary/12 text-primary"
                        : "border-border bg-surface-input/50 text-content-muted hover:border-border-strong hover:text-content",
                    )}
                  >
                    <Icon size={20} />
                  </button>
                ))}
              </div>
            </div>
            <div>
              <p className="mb-2 text-[12px] font-medium uppercase tracking-wide text-content-muted">Color</p>
              <div className="grid grid-cols-5 gap-2">
                {COLOR_OPTIONS.map((item) => (
                  <button
                    key={item.key}
                    type="button"
                    title={item.label}
                    onClick={() => setForm({ ...form, color: item.key })}
                    className={cn(
                      "flex h-12 items-center justify-center rounded-xl border bg-surface-input/50 transition-colors focus-ring",
                      form.color === item.key ? "border-primary/60" : "border-border hover:border-border-strong",
                    )}
                  >
                    <span className={cn("h-6 w-6 rounded-full", item.swatch)} />
                  </button>
                ))}
              </div>
            </div>
          </div>

          <div>
            <p className="mb-2 text-[12px] font-medium uppercase tracking-wide text-content-muted">Repeat</p>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
              {[
                ["once", "Once"],
                ["daily", "Daily"],
                ["weekly", "Weekly"],
                ["monthly", "Monthly"],
              ].map(([key, label]) => (
                <button
                  key={key}
                  type="button"
                  onClick={() => setForm({ ...form, repeat_rule: key as RepeatRule })}
                  className={cn(
                    "h-10 rounded-xl border text-sm font-medium transition-colors focus-ring",
                    form.repeat_rule === key
                      ? "border-primary/55 bg-primary text-primary-fg"
                      : "border-border bg-surface-input/45 text-content-muted hover:border-border-strong hover:text-content",
                  )}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>

          {showRepeatDays ? (
            <div className="rounded-2xl border border-border bg-surface-low/35 p-4">
              <div className="mb-3 flex items-center justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold text-content">Repeat days</p>
                  <p className="mt-0.5 text-[12px] text-content-subtle">Pilih hari routine ini berjalan.</p>
                </div>
                <Toggle
                  checked={allDaysSelected}
                  onChange={(checked) =>
                    setForm({ ...form, repeat_days: checked ? DAYS.map((day) => day.key) : [] })
                  }
                  label="Every day"
                />
              </div>
              <div className="grid grid-cols-7 gap-2">
                {DAYS.map((day) => {
                  const active = form.repeat_days.includes(day.key);
                  return (
                    <button
                      key={day.key}
                      type="button"
                      onClick={() =>
                        setForm({
                          ...form,
                          repeat_days: active
                            ? form.repeat_days.filter((item) => item !== day.key)
                            : [...form.repeat_days, day.key],
                        })
                      }
                      className={cn(
                        "flex aspect-square min-h-10 items-center justify-center rounded-full border text-[12px] font-semibold transition-colors focus-ring sm:text-sm",
                        active
                          ? "border-primary/50 bg-primary text-primary-fg"
                          : "border-border bg-surface-input/45 text-content-muted hover:border-border-strong hover:text-content",
                      )}
                    >
                      {day.label}
                    </button>
                  );
                })}
              </div>
            </div>
          ) : null}

          <div className="rounded-2xl border border-border bg-surface-low/35 p-4">
            <div className="mb-3">
              <p className="text-sm font-semibold text-content">Waktu routine</p>
              <p className="mt-0.5 text-[12px] text-content-subtle">Pilih slot cepat, jamnya tetap bisa disesuaikan manual.</p>
            </div>
            <div className="grid gap-2 sm:grid-cols-3">
              {PERIODS.map((period) => {
                const Icon = period.Icon;
                const active = form.time_period === period.key;
                return (
                  <button
                    key={period.key}
                    type="button"
                    onClick={() => setPeriod(period.key)}
                    className={cn(
                      "flex items-center justify-center gap-2 rounded-xl border px-3 py-3 text-sm font-medium transition-colors focus-ring",
                      active
                        ? "border-primary/55 bg-primary text-primary-fg"
                        : "border-border bg-surface-input/45 text-content-muted hover:border-border-strong hover:text-content",
                    )}
                  >
                    <Icon size={16} /> {period.label}
                  </button>
                );
              })}
            </div>
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <Input
              id="start_at"
              label="Start"
              type="datetime-local"
              required
              value={form.start_at}
              onChange={(event) => {
                const value = event.target.value;
                const hour = value ? Number(value.slice(11, 13)) : 7;
                setForm({ ...form, start_at: value, time_period: periodFromHour(hour) });
              }}
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

          <div className="grid gap-3 sm:grid-cols-2">
            <Input
              id="location"
              label="Place or context"
              placeholder="Home, campus, office, online..."
              value={form.location}
              onChange={(event) => setForm({ ...form, location: event.target.value })}
            />
            <Textarea
              id="description"
              label="Notes"
              placeholder="Apa yang harus dilakukan di routine ini?"
              value={form.description}
              onChange={(event) => setForm({ ...form, description: event.target.value })}
            />
          </div>
        </form>
      </Modal>
    </AppShell>
  );
}
