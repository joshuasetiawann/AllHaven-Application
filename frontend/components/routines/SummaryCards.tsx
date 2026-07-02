import { CalendarCheck, CloudOff, Database, RefreshCw, Repeat2, Sparkles, TriangleAlert } from "lucide-react";
import { cn } from "@/lib/format";
import type { RoutineSyncInfo } from "@/types";

function StatCard({
  label,
  value,
  hint,
  icon,
  tone,
  title,
}: {
  label: string;
  value: string;
  hint?: string;
  icon: React.ReactNode;
  tone: "primary" | "info" | "secondary" | "success" | "muted" | "warning";
  title?: string;
}) {
  const toneRing: Record<string, string> = {
    primary: "bg-primary/[0.12] text-primary-bright",
    info: "bg-info/[0.12] text-info",
    secondary: "bg-secondary/[0.12] text-secondary-soft",
    success: "bg-success/[0.12] text-success-soft",
    warning: "bg-warning/[0.12] text-warning",
    muted: "border border-border bg-surface-input/60 text-content-muted",
  };
  return (
    <div className="panel panel-hover flex items-center gap-3 p-4" title={title}>
      <span
        className={cn(
          "flex h-10 w-10 shrink-0 items-center justify-center rounded-[11px]",
          toneRing[tone],
        )}
      >
        {icon}
      </span>
      <div className="min-w-0">
        <p className="label-mono">{label}</p>
        <p className="truncate text-lg font-semibold leading-tight text-content">{value}</p>
        {hint ? <p className="truncate text-[11px] text-content-subtle">{hint}</p> : null}
      </div>
    </div>
  );
}

function syncView(sync: RoutineSyncInfo): {
  value: string;
  hint: string;
  icon: React.ReactNode;
  tone: "success" | "muted" | "warning";
  title: string;
} {
  if (sync.status === "active") {
    return {
      value: "Supabase Active",
      hint: "Mirroring in background",
      icon: <RefreshCw size={18} />,
      tone: "success",
      title: "Supabase mirroring is configured and active.",
    };
  }
  if (sync.status === "error") {
    return {
      value: "Sync Error",
      hint: "Tap to check settings",
      icon: <TriangleAlert size={18} />,
      tone: "warning",
      title: "The sync status could not be read. Your data is safe in the local database.",
    };
  }
  return {
    value: "Local-first",
    hint: "Stored in local database",
    icon: <Database size={18} />,
    tone: "muted",
    title: "Supabase is not configured. Data lives in the local database.",
  };
}

/** Four compact summary cards: Today, Upcoming, Repeating, Sync. */
export function SummaryCards({
  today,
  upcoming,
  repeating,
  sync,
}: {
  today: number;
  upcoming: number;
  repeating: number;
  sync: RoutineSyncInfo;
}) {
  const s = syncView(sync);
  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      <StatCard
        label="Today"
        value={String(today)}
        hint={today === 1 ? "routine" : "routines"}
        icon={<CalendarCheck size={18} />}
        tone="primary"
      />
      <StatCard
        label="Upcoming"
        value={String(upcoming)}
        hint="not yet past"
        icon={<Sparkles size={18} />}
        tone="info"
      />
      <StatCard
        label="Repeating"
        value={String(repeating)}
        hint="recurring rules"
        icon={<Repeat2 size={18} />}
        tone="secondary"
      />
      <StatCard
        label="Sync"
        value={s.value}
        hint={s.hint}
        icon={sync.status === "local_first" ? <CloudOff size={18} /> : s.icon}
        tone={s.tone}
        title={s.title}
      />
    </div>
  );
}
