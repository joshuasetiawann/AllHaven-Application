import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Modal } from "@/components/ui/Modal";
import { Textarea } from "@/components/ui/Textarea";
import { Toggle } from "@/components/ui/Toggle";
import { cn } from "@/lib/format";
import { ApiException, routinesApi } from "@/lib/api";
import type { RoutineEvent } from "@/types";
import {
  DAYS,
  PERIODS,
  REPEAT_OPTIONS,
  type RoutineForm,
  type TimePeriod,
  defaultStartFor,
  emptyForm,
  isoToLocalInput,
  periodFromHour,
  periodFromRoutine,
  setTimeOnInput,
} from "./shared";

/** Self-contained Add/Edit routine form. Handles its own create/update calls. */
export function RoutineFormModal({
  open,
  onClose,
  editing,
  selectedDate,
  initialPeriod,
  onSaved,
}: {
  open: boolean;
  onClose: () => void;
  editing: RoutineEvent | null;
  selectedDate: string;
  initialPeriod: TimePeriod;
  onSaved: () => void;
}) {
  const [form, setForm] = useState<RoutineForm>(emptyForm);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setError(null);
    if (editing) {
      setForm({
        title: editing.title,
        description: editing.description ?? "",
        location: editing.location ?? "",
        start_at: isoToLocalInput(editing.start_at),
        end_at: isoToLocalInput(editing.end_at),
        all_day: editing.all_day,
        time_period: periodFromRoutine(editing),
        repeat_rule: (editing.repeat_rule ?? "once") as RoutineForm["repeat_rule"],
        repeat_days: editing.repeat_days?.length ? editing.repeat_days : [],
      });
    } else {
      setForm({ ...emptyForm, time_period: initialPeriod, start_at: defaultStartFor(selectedDate, initialPeriod) });
    }
  }, [open, editing, initialPeriod, selectedDate]);

  const showRepeatDays = form.repeat_rule === "daily" || form.repeat_rule === "weekly";
  const allDaysSelected = form.repeat_days.length === DAYS.length;

  const setPeriod = (period: TimePeriod) => {
    const time = PERIODS.find((item) => item.key === period)?.time ?? "07:00";
    setForm((current) => ({
      ...current,
      time_period: period,
      start_at: setTimeOnInput(current.start_at, selectedDate, time),
    }));
  };

  const submit = async (event: FormEvent) => {
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
      onSaved();
      onClose();
    } catch (err) {
      setError(err instanceof ApiException ? err.message : "Failed to save routine.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={editing ? "Edit routine" : "Add routine"}
      description="Keep it simple: name, repeat, and time."
      size="lg"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
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
      <form id="routine-form" onSubmit={submit} className="space-y-4">
        {error ? (
          <div className="rounded-md border border-danger/35 bg-danger/10 px-3 py-2 text-[13px] text-danger">
            {error}
          </div>
        ) : null}

        <Input
          id="title"
          label="Routine name"
          required
          placeholder="Study, workout, morning review..."
          value={form.title}
          onChange={(event) => setForm({ ...form, title: event.target.value })}
          className="h-12 text-base font-semibold"
        />

        <div className="grid gap-3 lg:grid-cols-[1fr_1fr]">
          <div>
            <p className="label-mono mb-2">Repeat</p>
            <div className="grid grid-cols-2 gap-2">
              {REPEAT_OPTIONS.map((item) => (
                <button
                  key={item.key}
                  type="button"
                  onClick={() => setForm({ ...form, repeat_rule: item.key })}
                  className={cn(
                    "h-10 rounded-md border text-sm font-medium transition-colors focus-ring",
                    form.repeat_rule === item.key
                      ? "grad-primary border-transparent font-semibold text-primary-fg shadow-btn-primary"
                      : "border-border bg-surface-input/45 text-content-muted hover:border-border-strong hover:text-content",
                  )}
                >
                  {item.label}
                </button>
              ))}
            </div>
          </div>

          <div>
            <p className="label-mono mb-2">Time of day</p>
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
                      "flex h-10 items-center justify-center gap-1.5 rounded-md border text-sm font-medium transition-colors focus-ring",
                      active
                        ? "grad-primary border-transparent font-semibold text-primary-fg shadow-btn-primary"
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
          <div className="glass-tile p-3">
            <div className="mb-3 flex items-center justify-between gap-3">
              <div>
                <p className="text-sm font-semibold text-content">Repeat days</p>
                <p className="mt-0.5 text-[12px] text-content-subtle">Pick the days this routine runs.</p>
              </div>
              <div className="flex items-center gap-2 text-[12px] text-content-muted">
                <span>Every day</span>
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
                        ? "grad-primary border-transparent text-primary-fg shadow-toggle-on"
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

        <div className="glass-tile flex items-center justify-between px-3 py-2">
          <div>
            <p className="text-sm font-medium text-content">All day</p>
            <p className="text-[12px] text-content-subtle">Use this when you don&apos;t need an exact time.</p>
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
            label="Location"
            placeholder="Home, campus, online..."
            value={form.location}
            onChange={(event) => setForm({ ...form, location: event.target.value })}
          />
          <Textarea
            id="description"
            label="Notes"
            placeholder="Short note for this routine"
            value={form.description}
            onChange={(event) => setForm({ ...form, description: event.target.value })}
          />
        </div>
      </form>
    </Modal>
  );
}
