import { CalendarDays, MapPin, Pencil, Plus, Repeat2, Sparkles, Trash2 } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { cn } from "@/lib/format";
import type { RoutineEvent } from "@/types";
import {
  DAYS,
  PERIODS,
  type TimePeriod,
  eventStatus,
  formatShortDay,
  formatTime,
  repeatLabel,
} from "./shared";

/**
 * Aurora timeline tones per period — morning=green, afternoon=cyan,
 * evening=violet — used for the rail dot, the block tint, and the icon chip.
 */
const PERIOD_TONES: Record<TimePeriod, { chip: string; dot: string; block: string }> = {
  morning: {
    chip: "bg-success/[0.12] text-success-soft",
    dot: "bg-success-soft shadow-[0_0_10px_rgb(var(--color-success)/0.9)]",
    block: "border-success/25 bg-success/[0.07]",
  },
  afternoon: {
    chip: "bg-primary/[0.12] text-primary-bright",
    dot: "bg-primary-bright shadow-[0_0_10px_rgb(var(--color-primary)/0.9)]",
    block: "border-primary/25 bg-primary/[0.06]",
  },
  evening: {
    chip: "bg-secondary/[0.12] text-secondary-soft",
    dot: "bg-secondary-soft shadow-[0_0_10px_rgb(var(--color-secondary-deep)/0.9)]",
    block: "border-secondary/25 bg-secondary/[0.07]",
  },
};

/** In-progress block: cyan→violet wash with a soft cyan glow (Aurora "Focus"). */
const NOW_BLOCK =
  "border-primary/30 bg-[linear-gradient(135deg,rgb(var(--color-primary)/0.10),rgb(var(--color-secondary)/0.06))] shadow-[0_0_22px_rgb(var(--color-primary)/0.12)]";
const NOW_DOT = "bg-primary-bright shadow-[0_0_10px_rgb(var(--color-primary)/0.9)] animate-pulse-glow";

function RoutineRow({
  routine,
  tone,
  onEdit,
  onDelete,
}: {
  routine: RoutineEvent;
  tone: (typeof PERIOD_TONES)[TimePeriod];
  onEdit: (routine: RoutineEvent) => void;
  onDelete: (routine: RoutineEvent) => void;
}) {
  const status = eventStatus(routine);
  const dot = status === "now" ? NOW_DOT : status === "past" ? "bg-content-faint" : tone.dot;
  const block =
    status === "now" ? NOW_BLOCK : status === "past" ? "border-border bg-surface-input/40 opacity-75" : tone.block;

  return (
    <article className="group flex animate-fade-in gap-3 sm:gap-4">
      {/* Mono time label column */}
      <div className="w-14 shrink-0 pt-3.5 font-mono text-[11px] leading-tight text-content-subtle">
        <p>{routine.all_day ? "All day" : formatTime(routine.start_at)}</p>
        {routine.end_at && !routine.all_day ? (
          <p className="mt-0.5 text-content-faint">{formatTime(routine.end_at)}</p>
        ) : null}
      </div>

      {/* Rail + block */}
      <div className="relative min-w-0 flex-1 border-l border-border pb-4 pl-4 sm:pl-[18px]">
        <span aria-hidden className={cn("absolute -left-[5px] top-4 h-[9px] w-[9px] rounded-full", dot)} />
        <div className={cn("rounded-[13px] border px-3.5 py-3 transition-colors", block)}>
          <div className="flex items-start justify-between gap-2">
            <div className="flex min-w-0 flex-wrap items-center gap-2">
              <h3 className="min-w-0 max-w-full truncate text-[13.5px] font-semibold text-content">
                {routine.title}
              </h3>
              {status === "now" ? <Badge tone="success" dot>Now</Badge> : null}
              {status === "past" ? <Badge tone="neutral">Past</Badge> : null}
              <Badge tone="secondary">{repeatLabel(routine)}</Badge>
            </div>
            <div className="flex shrink-0 items-center gap-1 opacity-100 sm:opacity-0 sm:transition-opacity sm:group-hover:opacity-100">
              <button
                onClick={() => onEdit(routine)}
                className="rounded-sm p-1.5 text-content-subtle transition-colors hover:bg-surface-high hover:text-primary-bright focus-ring"
                aria-label="Edit routine"
              >
                <Pencil size={14} />
              </button>
              <button
                onClick={() => onDelete(routine)}
                className="rounded-sm p-1.5 text-content-subtle transition-colors hover:bg-danger/10 hover:text-danger focus-ring"
                aria-label="Delete routine"
              >
                <Trash2 size={14} />
              </button>
            </div>
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
            <p className="mt-2 max-w-3xl text-[12.5px] leading-relaxed text-content-muted">{routine.description}</p>
          ) : null}
        </div>
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
  const tone = PERIOD_TONES[period.key];
  return (
    <section>
      <div className="mb-3 flex flex-wrap items-center gap-2.5">
        <span className={cn("flex h-8 w-8 items-center justify-center rounded-[10px]", tone.chip)}>
          <Icon size={15} />
        </span>
        <h3 className="text-sm font-semibold text-content">{period.label}</h3>
        <span className="label-mono">{period.helper}</span>
      </div>

      {routines.length ? (
        <div>
          {routines.map((routine) => (
            <RoutineRow key={routine.id} routine={routine} tone={tone} onEdit={onEdit} onDelete={onDelete} />
          ))}
          <div className="flex gap-3 sm:gap-4">
            <div className="w-14 shrink-0" aria-hidden />
            <div className="flex flex-1 flex-wrap gap-2 border-l border-border pl-4 sm:pl-[18px]">
              <SlotAction icon={<Plus size={15} />} label="Add" onClick={onAdd} variant="add" />
              <SlotAction icon={<Sparkles size={15} />} label="Generate" onClick={onGenerate} variant="generate" />
            </div>
          </div>
        </div>
      ) : (
        <div className="flex gap-3 sm:gap-4">
          <div className="w-14 shrink-0 pt-3.5 font-mono text-[11px] text-content-faint">{period.time}</div>
          <div className="relative min-w-0 flex-1 border-l border-border pl-4 sm:pl-[18px]">
            <span
              aria-hidden
              className="absolute -left-[5px] top-4 h-[9px] w-[9px] rounded-full border border-dashed border-border-strong"
            />
            <div className="flex flex-col gap-3 rounded-[13px] border border-dashed border-border bg-surface-input/25 px-3.5 py-3.5 sm:flex-row sm:items-center sm:justify-between">
              <p className="text-[13px] text-content-muted">
                No blocks for the {period.label.toLowerCase()} yet.
              </p>
              <div className="flex flex-wrap gap-2">
                <SlotAction icon={<Plus size={15} />} label="Add" onClick={onAdd} variant="add" />
                <SlotAction icon={<Sparkles size={15} />} label="Generate" onClick={onGenerate} variant="generate" />
              </div>
            </div>
          </div>
        </div>
      )}
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
        "inline-flex h-8 items-center gap-1.5 rounded border px-3 text-[12.5px] font-medium transition-colors focus-ring",
        variant === "add"
          ? "border-border bg-surface-input/50 text-content-muted hover:border-primary/40 hover:bg-primary/[0.06] hover:text-primary-bright"
          : "border-secondary/30 bg-secondary/[0.12] text-secondary-soft hover:border-secondary/50 hover:bg-secondary/20",
      )}
    >
      {icon}
      {label}
    </button>
  );
}
