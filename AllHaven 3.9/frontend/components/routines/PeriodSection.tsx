import { CalendarDays, Check, Clock, MapPin, Pencil, Plus, Repeat2, Sparkles, Trash2 } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { cn } from "@/lib/format";
import type { RoutineEvent } from "@/types";
import { DAYS, PERIODS, eventStatus, formatShortDay, formatTime, repeatLabel } from "./shared";

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
    <article className="group grid animate-fade-in gap-3 rounded-xl border border-border bg-surface-input/40 p-3 transition-colors hover:border-border-strong hover:bg-surface-raised/60 sm:grid-cols-[5rem_minmax(0,1fr)_auto] sm:items-start">
      <div className="flex items-center gap-2 text-sm text-content">
        <span
          className={cn(
            "flex h-8 w-8 shrink-0 items-center justify-center rounded-full border",
            status === "now"
              ? "border-success/35 bg-success/10 text-success"
              : "border-border bg-surface-input text-content-muted",
          )}
        >
          {status === "now" ? <Check size={14} /> : <Clock size={14} />}
        </span>
        <div className="leading-tight">
          <p className="font-semibold">{routine.all_day ? "All day" : formatTime(routine.start_at)}</p>
          {routine.end_at && !routine.all_day ? (
            <p className="text-[11px] text-content-subtle">{formatTime(routine.end_at)}</p>
          ) : null}
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
              {routine.repeat_days.length === DAYS.length ? "Every day" : `${routine.repeat_days.length} days`}
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

export function PeriodSection({
  period,
  routines,
  onAdd,
  onGenerate,
  onEdit,
  onDelete,
}: {
  period: (typeof PERIODS)[number];
  routines: RoutineEvent[];
  onAdd: () => void;
  onGenerate: () => void;
  onEdit: (routine: RoutineEvent) => void;
  onDelete: (routine: RoutineEvent) => void;
}) {
  const Icon = period.Icon;
  return (
    <section className="relative grid gap-3 sm:grid-cols-[9rem_minmax(0,1fr)]">
      <div className="flex items-center justify-between gap-3 sm:block">
        <div className="flex items-center gap-3 sm:block">
          <span className="flex h-10 w-10 items-center justify-center rounded-xl border border-primary/25 bg-primary/10 text-primary sm:mb-3">
            <Icon size={18} />
          </span>
          <div>
            <h2 className="text-sm font-semibold text-content">{period.label}</h2>
            <p className="text-[12px] text-content-subtle">{period.helper}</p>
          </div>
        </div>
      </div>

      <div className="relative min-h-[64px] border-l border-border pl-4 sm:pl-6">
        <span className="absolute -left-[5px] top-2 h-2.5 w-2.5 rounded-full bg-primary shadow-glow-primary" />
        {routines.length ? (
          <div className="space-y-2">
            {routines.map((routine) => (
              <RoutineRow key={routine.id} routine={routine} onEdit={onEdit} onDelete={onDelete} />
            ))}
            <div className="flex flex-wrap gap-2 pt-1">
              <SlotAction icon={<Plus size={15} />} label="Add" onClick={onAdd} variant="add" />
              <SlotAction icon={<Sparkles size={15} />} label="Generate" onClick={onGenerate} variant="generate" />
            </div>
          </div>
        ) : (
          <div className="flex flex-col gap-3 rounded-xl border border-dashed border-border bg-surface-input/25 px-4 py-4 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-[13px] text-content-muted">
              No routines for the {period.label.toLowerCase()} yet.
            </p>
            <div className="flex flex-wrap gap-2">
              <SlotAction icon={<Plus size={15} />} label="Add" onClick={onAdd} variant="add" />
              <SlotAction icon={<Sparkles size={15} />} label="Generate" onClick={onGenerate} variant="generate" />
            </div>
          </div>
        )}
      </div>
    </section>
  );
}

function SlotAction({
  icon,
  label,
  onClick,
  variant,
}: {
  icon: React.ReactNode;
  label: string;
  onClick: () => void;
  variant: "add" | "generate";
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "inline-flex h-8 items-center gap-1.5 rounded-lg border px-3 text-[13px] font-medium transition-colors focus-ring",
        variant === "add"
          ? "border-border bg-surface-input/50 text-content hover:border-primary/50 hover:text-primary"
          : "border-secondary/30 bg-secondary/12 text-secondary-soft hover:border-secondary/50 hover:bg-secondary/20",
      )}
    >
      {icon}
      {label}
    </button>
  );
}
