"use client";

import { useEffect, useMemo, useState } from "react";
import { CalendarClock, Check, Plus, Repeat2, Sparkles } from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { PageHeader } from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/Button";
import { Card, CardHeader } from "@/components/ui/Card";
import { ErrorState } from "@/components/ui/States";
import { useAppDialog } from "@/components/ui/AppDialog";
import { cn } from "@/lib/format";
import { ApiException, routinesApi } from "@/lib/api";
import type { RoutineEvent, RoutineSyncInfo } from "@/types";
import { DateStrip } from "@/components/routines/DateStrip";
import { GenerateModal } from "@/components/routines/GenerateModal";
import { PeriodSection } from "@/components/routines/PeriodSection";
import { RoutineEmptyState } from "@/components/routines/RoutineEmptyState";
import { RoutineFormModal } from "@/components/routines/RoutineFormModal";
import { RoutineSkeleton } from "@/components/routines/RoutineSkeleton";
import { RoutineToolbar } from "@/components/routines/RoutineToolbar";
import { SummaryCards } from "@/components/routines/SummaryCards";
import {
  PERIODS,
  type TimePeriod,
  type ViewMode,
  addDays,
  baseOf,
  countOn,
  dateKey,
  eventStatus,
  expandForDay,
  isUpcoming,
  formatLongDay,
  periodFromRoutine,
  repeatLabel,
  startOfLocalDay,
} from "@/components/routines/shared";

/** Conic-gradient progress dial — "N% · x/y blocks" from real completion data. */
function ProgressCard({ label, done, total }: { label: string; done: number; total: number }) {
  const pct = total ? Math.round((done / total) * 100) : 0;
  return (
    <Card padding="none" className="p-[22px] text-center">
      <p className="label-mono mb-4">{label}</p>
      <div
        className="mx-auto flex h-32 w-32 items-center justify-center rounded-full shadow-[0_0_34px_rgb(var(--color-primary)/0.22)]"
        role="img"
        aria-label={`${pct}% of blocks completed — ${done} of ${total}`}
        style={{
          background: `conic-gradient(rgb(var(--color-primary)) 0% ${pct}%, rgba(255,255,255,0.06) ${pct}% 100%)`,
        }}
      >
        <div className="flex h-[98px] w-[98px] flex-col items-center justify-center rounded-full bg-bg-deep">
          <span className="text-[26px] font-semibold leading-tight text-content">{pct}%</span>
          <span className="text-[11px] text-content-faint">
            {done} / {total} blocks
          </span>
        </div>
      </div>
    </Card>
  );
}

/** Habit-style list of the repeating blocks in view: green check tiles, pending unchecked. */
function HabitsCard({ habits }: { habits: RoutineEvent[] }) {
  return (
    <Card padding="none" className="p-[22px]">
      <h2 className="text-[15px] font-semibold text-content">Habits</h2>
      <p className="mb-4 mt-0.5 text-[12px] text-content-subtle">Repeating blocks in this view.</p>
      {habits.length ? (
        <div className="flex flex-col gap-3.5">
          {habits.map((habit) => {
            const status = eventStatus(habit);
            return (
              <div key={habit.id} className="flex items-center justify-between gap-2">
                <span
                  className={cn(
                    "flex min-w-0 items-center gap-2.5 text-[13px]",
                    status === "upcoming" ? "text-content-muted" : "text-content",
                  )}
                >
                  <span
                    className={cn(
                      "flex h-7 w-7 shrink-0 items-center justify-center rounded-sm",
                      status === "past" && "bg-success/[0.13] text-success-soft",
                      status === "now" && "bg-primary/[0.14] text-primary-bright",
                      status === "upcoming" && "border-[1.5px] border-border-strong",
                    )}
                  >
                    {status !== "upcoming" ? <Check size={15} /> : null}
                  </span>
                  <span className="truncate">{habit.title}</span>
                </span>
                {status === "upcoming" ? (
                  <span className="shrink-0 text-[12px] text-content-faint">Pending</span>
                ) : (
                  <span
                    className={cn(
                      "inline-flex shrink-0 items-center gap-1.5 text-[12px]",
                      status === "now" ? "text-primary-bright" : "text-success-soft",
                    )}
                  >
                    <Repeat2 size={13} /> {repeatLabel(habit)}
                  </span>
                )}
              </div>
            );
          })}
        </div>
      ) : (
        <p className="rounded-md border border-dashed border-border bg-surface-input/25 px-3 py-4 text-center text-[12.5px] text-content-muted">
          No repeating blocks in this view yet.
        </p>
      )}
    </Card>
  );
}

export default function RoutinesPage() {
  const dialog = useAppDialog();
  const todayKey = dateKey(new Date());

  const [routines, setRoutines] = useState<RoutineEvent[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sync, setSync] = useState<RoutineSyncInfo>({ status: "local_first", configured: false });

  const [view, setView] = useState<ViewMode>("selected");
  const [selectedDate, setSelectedDate] = useState(todayKey);
  const [query, setQuery] = useState("");

  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<RoutineEvent | null>(null);
  const [formPeriod, setFormPeriod] = useState<TimePeriod>("morning");

  const [genOpen, setGenOpen] = useState(false);
  const [genPeriod, setGenPeriod] = useState<TimePeriod>("morning");

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
    void routinesApi.syncStatus().then(setSync);
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
    const byView: RoutineEvent[] =
      view === "selected"
        ? expandForDay(sorted, selectedDate)
        : view === "upcoming"
          ? sorted.filter(isUpcoming)
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

  const todayCount = useMemo(() => countOn(sorted, todayKey), [sorted, todayKey]);
  const upcomingCount = useMemo(() => sorted.filter(isUpcoming).length, [sorted]);
  const repeatCount = useMemo(
    () => sorted.filter((routine) => (routine.repeat_rule ?? "once") !== "once").length,
    [sorted],
  );

  // Presentational derivations for the right column (dial + habits).
  const doneBlocks = filtered.filter((routine) => eventStatus(routine) === "past").length;
  const habitBlocks = filtered.filter((routine) => (routine.repeat_rule ?? "once") !== "once");

  const openCreate = (period: TimePeriod = "morning") => {
    setEditing(null);
    setFormPeriod(period);
    setFormOpen(true);
  };

  const openEdit = (routine: RoutineEvent) => {
    // Recurring instances are display-only clones; edit the underlying routine.
    const base = baseOf(routine);
    setEditing(base);
    setFormPeriod(periodFromRoutine(base));
    setFormOpen(true);
  };

  const openGenerate = (period: TimePeriod = "morning") => {
    setGenPeriod(period);
    setGenOpen(true);
  };

  const remove = async (routine: RoutineEvent) => {
    // Deleting any occurrence removes the whole (possibly recurring) routine.
    const base = baseOf(routine);
    const ok = await dialog.confirm({
      title: "Delete routine?",
      message: `Remove "${base.title}" from your local schedule?`,
      confirmLabel: "Delete",
      tone: "danger",
    });
    if (!ok) return;
    setRoutines((prev) => prev?.filter((item) => item.id !== base.id) ?? prev);
    try {
      await routinesApi.remove(base.id);
    } catch (err) {
      setError(err instanceof ApiException ? err.message : "Failed to delete routine.");
      void load();
    }
  };

  const shiftSelectedDate = (days: number) => {
    const base = new Date(`${selectedDate}T00:00:00`);
    setSelectedDate(dateKey(addDays(base, days)));
    setView("selected");
  };

  const selectDate = (key: string) => {
    setSelectedDate(key);
    setView("selected");
  };

  return (
    <AppShell>
      <PageHeader
        title="Routine"
        subtitle={`${formatLongDay(todayKey)} · your day at a glance`}
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <Button variant="secondary" onClick={() => openGenerate("morning")}>
              <Sparkles size={16} /> Generate with AI
            </Button>
            <Button onClick={() => openCreate("morning")}>
              <Plus size={16} /> Add block
            </Button>
          </div>
        }
      />

      {error ? (
        <div className="mb-4">
          <ErrorState message={error} onRetry={() => void load()} />
        </div>
      ) : null}

      {!routines ? (
        <RoutineSkeleton />
      ) : (
        <div className="space-y-5">
          <SummaryCards today={todayCount} upcoming={upcomingCount} repeating={repeatCount} sync={sync} />

          <RoutineToolbar
            view={view}
            onView={setView}
            query={query}
            onQuery={setQuery}
            date={selectedDate}
            onDate={selectDate}
            todayKey={todayKey}
          />

          <DateStrip
            days={dayStrip}
            selectedDate={selectedDate}
            isActive={view === "selected"}
            countFor={(key) => countOn(sorted, key)}
            onSelect={selectDate}
            onShift={shiftSelectedDate}
          />

          <div
            key={`${view}-${selectedDate}`}
            className="grid animate-fade-in items-start gap-5 lg:grid-cols-[2fr_1fr]"
          >
            {filtered.length === 0 ? (
              <RoutineEmptyState
                onAdd={() => openCreate("morning")}
                onGenerate={() => openGenerate("morning")}
              />
            ) : (
              <Card padding="lg">
                <CardHeader
                  icon={<CalendarClock size={16} />}
                  title={
                    view === "selected"
                      ? formatLongDay(selectedDate)
                      : view === "upcoming"
                        ? "Upcoming routines"
                        : "All routines"
                  }
                  subtitle={`${filtered.length} ${filtered.length === 1 ? "block" : "blocks"} in this view`}
                />
                <div className="space-y-6">
                  {PERIODS.map((period) => (
                    <PeriodSection
                      key={period.key}
                      period={period}
                      routines={routinesByPeriod[period.key]}
                      onAdd={() => openCreate(period.key)}
                      onGenerate={() => openGenerate(period.key)}
                      onEdit={openEdit}
                      onDelete={remove}
                    />
                  ))}
                </div>
              </Card>
            )}

            <div className="flex flex-col gap-5">
              <ProgressCard
                label={view === "selected" ? "Today's progress" : "Completed blocks"}
                done={doneBlocks}
                total={filtered.length}
              />
              <HabitsCard habits={habitBlocks} />
            </div>
          </div>
        </div>
      )}

      <RoutineFormModal
        open={formOpen}
        onClose={() => setFormOpen(false)}
        editing={editing}
        selectedDate={selectedDate}
        initialPeriod={formPeriod}
        onSaved={() => void load()}
      />

      <GenerateModal
        open={genOpen}
        onClose={() => setGenOpen(false)}
        date={selectedDate}
        defaultPeriod={genPeriod}
        onSaved={() => void load()}
      />
    </AppShell>
  );
}
