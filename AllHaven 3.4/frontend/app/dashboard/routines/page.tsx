"use client";

import { useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";
import {
  CalendarDays,
  Check,
  ChevronLeft,
  ChevronRight,
  Clock,
  MapPin,
  Moon,
  Pencil,
  Plus,
  Repeat2,
  Search,
  Sun,
  Sunrise,
  Trash2,
  type LucideIcon,
} from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { PageHeader } from "@/components/layout/PageHeader";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Loading } from "@/components/ui/States";
import { Modal } from "@/components/ui/Modal";
import { Textarea } from "@/components/ui/Textarea";
import { Toggle } from "@/components/ui/Toggle";
import { useAppDialog } from "@/components/ui/AppDialog";
import { ApiException, routinesApi } from "@/lib/api";
import { cn } from "@/lib/format";
import type { RoutineEvent } from "@/types";

type ViewMode = "selected" | "upcoming" | "all";
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
}

const PERIODS = [
  { key: "morning", label: "Pagi", helper: "05.00 - 11.59", time: "07:00", Icon: Sunrise },
  { key: "afternoon", label: "Siang", helper: "12.00 - 16.59", time: "13:00", Icon: Sun },
  { key: "evening", label: "Malam", helper: "17.00 ke atas", time: "19:00", Icon: Moon },
] as const satisfies readonly {
  key: TimePeriod;
  label: string;
  helper: string;
  time: string;
  Icon: LucideIcon;
}[];

const DAYS = [
  { key: "mon", label: "Sen" },
  { key: "tue", label: "Sel" },
  { key: "wed", label: "Rab" },
  { key: "thu", label: "Kam" },
  { key: "fri", label: "Jum" },
  { key: "sat", label: "Sab" },
  { key: "sun", label: "Min" },
];

const REPEAT_OPTIONS: { key: RepeatRule; label: string }[] = [
  { key: "once", label: "Sekali" },
  { key: "daily", label: "Harian" },
  { key: "weekly", label: "Mingguan" },
  { key: "monthly", label: "Bulanan" },
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

function defaultStartFor(dateValue: string, period: TimePeriod): string {
  const time = PERIODS.find((item) => item.key === period)?.time ?? "07:00";
  return `${dateValue}T${time}`;
}

function setTimeOnInput(value: string, dateValue: string, time: string): string {
  const date = value ? value.slice(0, 10) : dateValue;
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
  if (rule === "daily") return "Harian";
  if (rule === "weekly") return "Mingguan";
  if (rule === "monthly") return "Bulanan";
  return "Sekali";
}

function RoutineRow({
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
    <article className="group grid gap-3 border-b border-border/70 py-3 last:border-b-0 sm:grid-cols-[5.5rem_minmax(0,1fr)_auto] sm:items-start">
      <div className="flex items-center gap-2 text-sm text-content">
        <span className={cn(
          "flex h-8 w-8 shrink-0 items-center justify-center rounded-full border",
          status === "now" ? "border-success/35 bg-success/10 text-success" : "border-border bg-surface-input text-content-muted",
        )}>
          {status === "now" ? <Check size={14} /> : <Clock size={14} />}
        </span>
        <div className="leading-tight">
          <p className="font-semibold">{routine.all_day ? "All day" : formatTime(routine.start_at)}</p>
          {routine.end_at && !routine.all_day ? <p className="text-[11px] text-content-subtle">{formatTime(routine.end_at)}</p> : null}
        </div>
      </div>

      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="min-w-0 truncate text-sm font-semibold text-content">{routine.title}</h3>
          {status === "now" ? <Badge tone="success" dot>Now</Badge> : null}
          {status === "past" ? <Badge tone="neutral">Past</Badge> : null}
          <Badge tone="secondary">{repeatLabel(routine)}</Badge>
        </div>
        <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-[12px] text-content-subtle">
          <span className="inline-flex items-center gap-1">
            <CalendarDays size={12} />
            {formatShortDay(new Date(routine.start_at))}
          </span>
          {routine.location ? (
            <span className="inline-flex items-center gap-1">
              <MapPin size={12} />
              {routine.location}
            </span>
          ) : null}
          {routine.repeat_days?.length ? (
            <span className="inline-flex items-center gap-1">
              <Repeat2 size={12} />
              {routine.repeat_days.length === DAYS.length ? "Setiap hari" : `${routine.repeat_days.length} hari`}
            </span>
          ) : null}
        </div>
        {routine.description ? (
          <p className="mt-2 max-w-3xl text-[13px] leading-relaxed text-content-muted">{routine.description}</p>
        ) : null}
      </div>

      <div className="flex items-center justify-end gap-1 opacity-100 sm:opacity-0 sm:transition-opacity sm:group-hover:opacity-100">
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
    </article>
  );
}

function PeriodSection({
  period,
  routines,
  onAdd,
  onEdit,
  onDelete,
}: {
  period: (typeof PERIODS)[number];
  routines: RoutineEvent[];
  onAdd: () => void;
  onEdit: (routine: RoutineEvent) => void;
  onDelete: (routine: RoutineEvent) => void;
}) {
  const Icon = period.Icon;
  return (
    <section className="relative grid gap-3 sm:grid-cols-[9rem_minmax(0,1fr)]">
      <div className="flex items-center gap-3 sm:block">
        <span className="mb-0 flex h-10 w-10 items-center justify-center rounded-full border border-primary/25 bg-primary/10 text-primary sm:mb-3">
          <Icon size={18} />
        </span>
        <div>
          <h2 className="text-sm font-semibold text-content">{period.label}</h2>
          <p className="text-[12px] text-content-subtle">{period.helper}</p>
        </div>
      </div>

      <div className="relative min-h-[86px] border-l border-border pl-4 sm:pl-6">
        <span className="absolute -left-[5px] top-2 h-2.5 w-2.5 rounded-full bg-primary shadow-glow-primary" />
        {routines.length ? (
          <div className="divide-y-0">
            {routines.map((routine) => (
              <RoutineRow key={routine.id} routine={routine} onEdit={onEdit} onDelete={onDelete} />
            ))}
          </div>
        ) : (
          <button
            onClick={onAdd}
            className="flex min-h-[74px] w-full items-center justify-between rounded-xl border border-dashed border-border bg-surface-low/20 px-4 text-left text-content-muted transition-colors hover:border-primary/40 hover:bg-primary/5 hover:text-primary focus-ring"
          >
            <span>
              <span className="block text-sm font-medium text-content">Belum ada routine {period.label.toLowerCase()}</span>
              <span className="mt-0.5 block text-[12px] text-content-subtle">Tambah jadwal untuk slot ini.</span>
            </span>
            <Plus size={17} />
          </button>
        )}
      </div>
    </section>
  );
}

export default function RoutinesPage() {
  const dialog = useAppDialog();
  const todayKey = dateKey(new Date());
  const [routines, setRoutines] = useState<RoutineEvent[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [view, setView] = useState<ViewMode>("selected");
  const [selectedDate, setSelectedDate] = useState(todayKey);
  const [query, setQuery] = useState("");
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
    const base = startOfLocalDay(new Date(selectedDate ? `${selectedDate}T00:00:00` : new Date()));
    return Array.from({ length: 9 }, (_, index) => addDays(base, index - 2));
  }, [selectedDate]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    const byView = view === "selected"
      ? sorted.filter((routine) => eventDayKey(routine) === selectedDate)
      : view === "upcoming"
        ? sorted.filter((routine) => eventStatus(routine) !== "past")
        : sorted;
    if (!q) return byView;
    return byView.filter((routine) =>
      [routine.title, routine.description, routine.location]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(q)),
    );
  }, [query, selectedDate, sorted, view]);

  const routinesByPeriod = useMemo(() => {
    const map: Record<TimePeriod, RoutineEvent[]> = { morning: [], afternoon: [], evening: [] };
    for (const routine of filtered) {
      map[periodFromRoutine(routine)].push(routine);
    }
    return map;
  }, [filtered]);

  const todayCount = useMemo(() => sorted.filter((routine) => eventDayKey(routine) === todayKey).length, [sorted, todayKey]);
  const upcomingCount = useMemo(() => sorted.filter((routine) => eventStatus(routine) !== "past").length, [sorted]);
  const repeatCount = useMemo(() => sorted.filter((routine) => (routine.repeat_rule ?? "once") !== "once").length, [sorted]);
  const showRepeatDays = form.repeat_rule === "daily" || form.repeat_rule === "weekly";
  const allDaysSelected = form.repeat_days.length === DAYS.length;

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
    });
    setOpen(true);
  };

  const save = async (event: FormEvent) => {
    event.preventDefault();
    if (!form.title.trim() || !form.start_at) return;
    setSaving(true);
    setError(null);
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
    const ok = await dialog.confirm({
      title: "Delete routine?",
      message: `Hapus "${routine.title}" dari jadwal lokal?`,
      confirmLabel: "Delete",
      tone: "danger",
    });
    if (!ok) return;
    setRoutines((prev) => prev?.filter((item) => item.id !== routine.id) ?? prev);
    try {
      await routinesApi.remove(routine.id);
    } catch (err) {
      setError(err instanceof ApiException ? err.message : "Failed to delete routine.");
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

  const shiftSelectedDate = (days: number) => {
    const base = new Date(`${selectedDate}T00:00:00`);
    setSelectedDate(dateKey(addDays(base, days)));
    setView("selected");
  };

  return (
    <AppShell>
      <PageHeader
        title="Routine"
        subtitle="Agenda lokal untuk rutinitas, jadwal harian, dan rencana berulang."
        actions={
          <Button onClick={() => openCreate(selectedDate, "morning")}>
            <Plus size={16} /> Add routine
          </Button>
        }
      />

      {error ? (
        <div className="mb-4 rounded-xl border border-danger/35 bg-danger/10 px-4 py-3 text-sm text-danger">
          {error}
        </div>
      ) : null}

      {!routines ? (
        <Loading label="Loading routines..." />
      ) : (
        <div className="space-y-6">
          <section className="border-b border-border pb-5">
            <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
              <div className="min-w-0">
                <div className="mb-2 flex flex-wrap items-center gap-2">
                  <Badge tone="primary" dot>Local DB</Badge>
                  <Badge tone="neutral">{todayCount} today</Badge>
                  <Badge tone="neutral">{upcomingCount} upcoming</Badge>
                  <Badge tone="secondary">{repeatCount} repeat</Badge>
                </div>
                <h2 className="text-xl font-semibold tracking-tight text-content">{formatLongDay(selectedDate)}</h2>
                <p className="mt-1 max-w-2xl text-sm leading-relaxed text-content-muted">
                  Routine tersimpan di database lokal. Jika Supabase aktif, data akan dimirror di background tanpa mengganggu app.
                </p>
              </div>

              <div className="flex flex-col gap-2 sm:flex-row sm:items-end">
                <div className="relative sm:w-64">
                  <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-content-subtle" />
                  <input
                    value={query}
                    onChange={(event) => setQuery(event.target.value)}
                    placeholder="Cari routine..."
                    className="h-10 w-full rounded-lg border border-border bg-surface-input pl-9 pr-3 text-sm text-content placeholder:text-content-subtle focus:border-primary/70 focus:outline-none focus:ring-1 focus:ring-primary/30"
                  />
                </div>
                <Input
                  id="routine-date"
                  type="date"
                  value={selectedDate}
                  onChange={(event) => {
                    setSelectedDate(event.target.value || todayKey);
                    setView("selected");
                  }}
                  className="sm:w-44"
                />
              </div>
            </div>

            <div className="mt-5 flex items-center gap-2">
              <button
                onClick={() => shiftSelectedDate(-1)}
                className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-border bg-surface-input text-content-muted transition-colors hover:border-border-strong hover:text-content focus-ring"
                aria-label="Previous day"
              >
                <ChevronLeft size={16} />
              </button>
              <div className="custom-scrollbar flex min-w-0 flex-1 gap-2 overflow-x-auto pb-1">
                {dayStrip.map((day) => {
                  const key = dateKey(day);
                  const count = sorted.filter((routine) => eventDayKey(routine) === key).length;
                  const active = selectedDate === key && view === "selected";
                  return (
                    <button
                      key={key}
                      onClick={() => {
                        setSelectedDate(key);
                        setView("selected");
                      }}
                      className={cn(
                        "min-w-[5.25rem] rounded-full border px-3 py-2 text-left transition-colors focus-ring",
                        active
                          ? "border-primary/50 bg-primary text-primary-fg"
                          : "border-border bg-surface-input/50 text-content-muted hover:border-border-strong hover:text-content",
                      )}
                    >
                      <span className="block text-[11px] uppercase tracking-wide">{day.toLocaleDateString("id-ID", { weekday: "short" })}</span>
                      <span className="block text-sm font-semibold">{day.getDate()}</span>
                      <span className="block text-[10.5px] opacity-80">{count ? `${count} item` : "empty"}</span>
                    </button>
                  );
                })}
              </div>
              <button
                onClick={() => shiftSelectedDate(1)}
                className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-border bg-surface-input text-content-muted transition-colors hover:border-border-strong hover:text-content focus-ring"
                aria-label="Next day"
              >
                <ChevronRight size={16} />
              </button>
            </div>

            <div className="mt-4 flex flex-wrap gap-2">
              {[
                ["selected", "Tanggal ini"],
                ["upcoming", "Upcoming"],
                ["all", "Semua"],
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

          {filtered.length === 0 ? (
            <div className="rounded-xl border border-dashed border-border bg-surface-low/20 px-4 py-4 text-sm text-content-muted">
              Belum ada routine untuk tampilan ini. Pilih Pagi, Siang, atau Malam di bawah untuk mulai.
            </div>
          ) : null}

          <div className="space-y-8">
            {PERIODS.map((period) => (
              <PeriodSection
                key={period.key}
                period={period}
                routines={routinesByPeriod[period.key]}
                onAdd={() => openCreate(selectedDate, period.key)}
                onEdit={openEdit}
                onDelete={remove}
              />
            ))}
          </div>
        </div>
      )}

      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title={editing ? "Edit routine" : "Add routine"}
        description="Isi yang penting saja: nama, repeat, dan waktu."
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
            label="Nama routine"
            required
            placeholder="Kuliah, coding, review pagi..."
            value={form.title}
            onChange={(event) => setForm({ ...form, title: event.target.value })}
            className="h-12 text-base font-semibold"
          />

          <div className="grid gap-3 lg:grid-cols-[1fr_1fr]">
            <div>
              <p className="mb-2 text-[12px] font-medium uppercase tracking-wide text-content-muted">Repeat</p>
              <div className="grid grid-cols-2 gap-2">
                {REPEAT_OPTIONS.map((item) => (
                  <button
                    key={item.key}
                    type="button"
                    onClick={() => setForm({ ...form, repeat_rule: item.key })}
                    className={cn(
                      "h-10 rounded-lg border text-sm font-medium transition-colors focus-ring",
                      form.repeat_rule === item.key
                        ? "border-primary/55 bg-primary text-primary-fg"
                        : "border-border bg-surface-input/45 text-content-muted hover:border-border-strong hover:text-content",
                    )}
                  >
                    {item.label}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <p className="mb-2 text-[12px] font-medium uppercase tracking-wide text-content-muted">Waktu</p>
              <div className="grid grid-cols-3 gap-2">
                {PERIODS.map((period) => {
                  const Icon = period.Icon;
                  const active = form.time_period === period.key;
                  return (
                    <button
                      key={period.key}
                      type="button"
                      onClick={() => setPeriod(period.key)}
                      className={cn(
                        "flex h-10 items-center justify-center gap-1.5 rounded-lg border text-sm font-medium transition-colors focus-ring",
                        active
                          ? "border-primary/55 bg-primary text-primary-fg"
                          : "border-border bg-surface-input/45 text-content-muted hover:border-border-strong hover:text-content",
                      )}
                    >
                      <Icon size={15} /> {period.label}
                    </button>
                  );
                })}
              </div>
            </div>
          </div>

          {showRepeatDays ? (
            <div className="rounded-xl border border-border bg-surface-low/20 p-3">
              <div className="mb-3 flex items-center justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold text-content">Hari repeat</p>
                  <p className="mt-0.5 text-[12px] text-content-subtle">Pilih hari routine ini berjalan.</p>
                </div>
                <div className="flex items-center gap-2 text-[12px] text-content-muted">
                  <span>Setiap hari</span>
                  <Toggle
                    checked={allDaysSelected}
                    onChange={(checked) =>
                      setForm({ ...form, repeat_days: checked ? DAYS.map((day) => day.key) : [] })
                    }
                    label="Every day"
                  />
                </div>
              </div>
              <div className="grid grid-cols-7 gap-1.5 sm:gap-2">
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
                        "flex aspect-square min-h-9 items-center justify-center rounded-full border text-[12px] font-semibold transition-colors focus-ring",
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

          <div className="flex items-center justify-between rounded-xl border border-border bg-surface-low/20 px-3 py-2">
            <div>
              <p className="text-sm font-medium text-content">All day</p>
              <p className="text-[12px] text-content-subtle">Gunakan kalau tidak perlu jam detail.</p>
            </div>
            <Toggle
              checked={form.all_day}
              onChange={(next) => setForm({ ...form, all_day: next })}
              label="All day"
            />
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <Input
              id="location"
              label="Tempat"
              placeholder="Rumah, kampus, online..."
              value={form.location}
              onChange={(event) => setForm({ ...form, location: event.target.value })}
            />
            <Textarea
              id="description"
              label="Notes"
              placeholder="Catatan singkat untuk routine ini"
              value={form.description}
              onChange={(event) => setForm({ ...form, description: event.target.value })}
            />
          </div>
        </form>
      </Modal>
    </AppShell>
  );
}
