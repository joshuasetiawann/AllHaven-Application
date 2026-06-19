"use client";

import { useEffect, useMemo, useState } from "react";
import { Plus, Sparkles } from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { PageHeader } from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/Button";
import { ErrorState } from "@/components/ui/States";
import { useAppDialog } from "@/components/ui/AppDialog";
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
  expandForDay,
  isUpcoming,
  formatLongDay,
  periodFromRoutine,
  startOfLocalDay,
} from "@/components/routines/shared";

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
        subtitle="A calm local planner for your habits, daily schedule, and recurring plans."
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <Button variant="secondary" onClick={() => openGenerate("morning")}>
              <Sparkles size={16} /> Generate with AI
            </Button>
            <Button onClick={() => openCreate("morning")}>
              <Plus size={16} /> Add routine
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
        <div className="space-y-6">
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

          <div key={`${view}-${selectedDate}`} className="animate-fade-in space-y-6">
            <div>
              <h2 className="text-lg font-semibold tracking-tight text-content">
                {view === "selected" ? formatLongDay(selectedDate) : view === "upcoming" ? "Upcoming routines" : "All routines"}
              </h2>
              <p className="mt-0.5 text-[13px] text-content-muted">
                {filtered.length} {filtered.length === 1 ? "routine" : "routines"} in this view.
              </p>
            </div>

            {filtered.length === 0 ? (
              <RoutineEmptyState
                onAdd={() => openCreate("morning")}
                onGenerate={() => openGenerate("morning")}
              />
            ) : (
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
            )}
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
