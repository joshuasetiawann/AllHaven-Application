"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  ArrowUpRight,
  Bot,
  CalendarDays,
  ClipboardCheck,
  ListTodo,
  ShieldCheck,
  Sparkles,
  StickyNote,
  TrendingUp,
  Wallet,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { Card, CardHeader } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { ConfigStatusBadge, PriorityBadge } from "@/components/ui/meta";
import { StatusDot } from "@/components/ui/StatusDot";
import { BarChart } from "@/components/ui/BarChart";
import { ErrorState, Loading } from "@/components/ui/States";
import { APP_VERSION } from "@/components/layout/nav";
import { financeApi, notesApi, settingsApi, tasksApi } from "@/lib/api";
import { getStoredUser } from "@/lib/auth";
import { cn, formatCurrency, greeting } from "@/lib/format";
import type { FinanceSummary, Integration, Note, Task, Transaction } from "@/types";

interface Data {
  tasks: Task[];
  notes: Note[];
  summary: FinanceSummary | null;
  transactions: Transaction[];
  integrations: Integration[];
}

function MiniStat({
  icon: Icon,
  label,
  value,
  tone = "cyan",
}: {
  icon: LucideIcon;
  label: string;
  value: string;
  tone?: "cyan" | "violet";
}) {
  return (
    <div className="glass-tile p-4">
      <div className="mb-3 flex items-center gap-2">
        <span
          className={cn(
            "flex h-[26px] w-[26px] items-center justify-center rounded-[9px]",
            tone === "violet"
              ? "bg-secondary/15 text-secondary-soft"
              : "bg-primary/15 text-primary-bright",
          )}
        >
          <Icon size={14} />
        </span>
        <span className="text-[10.5px] font-medium uppercase tracking-wide text-content-subtle">{label}</span>
      </div>
      <p className="text-[28px] font-semibold leading-none tracking-tight text-content">{value}</p>
    </div>
  );
}

export default function DashboardOverview() {
  const now = new Date();
  const year = now.getFullYear();
  const month = now.getMonth() + 1;
  const user = getStoredUser();

  const [data, setData] = useState<Data | null>(null);
  const [error, setError] = useState<string | null>(null);
  // Sections that failed to load while others succeeded (shown as a banner, not
  // a full-screen error) — one slow/failing call no longer blanks the dashboard.
  const [failures, setFailures] = useState<string[]>([]);

  const load = async () => {
    setError(null);
    setData(null);
    setFailures([]);
    // Core data is Supabase-backed on mobile (fast). `settingsApi.integrations()`
    // is a REST call that may point at an unreachable backend, so it must NOT
    // block the dashboard — it's fetched separately below and fills in later.
    const [tasksR, notesR, summaryR, txR] = await Promise.allSettled([
      tasksApi.list(),
      notesApi.list(),
      financeApi.summary(year, month),
      financeApi.listTransactions({ year, month }),
    ]);
    const all = [tasksR, notesR, summaryR, txR];
    // Everything failed → almost certainly a connectivity problem; show one
    // clear, retryable error rather than an empty dashboard.
    if (all.every((r) => r.status === "rejected")) {
      const reason = (all.find((r) => r.status === "rejected") as PromiseRejectedResult | undefined)?.reason;
      setError(reason instanceof Error ? reason.message : "Failed to load dashboard.");
      return;
    }
    const failed: string[] = [];
    if (tasksR.status === "rejected") failed.push("tasks");
    if (notesR.status === "rejected") failed.push("notes");
    if (summaryR.status === "rejected") failed.push("cashflow");
    if (txR.status === "rejected") failed.push("transactions");
    setData({
      tasks: tasksR.status === "fulfilled" ? tasksR.value : [],
      notes: notesR.status === "fulfilled" ? notesR.value : [],
      summary: summaryR.status === "fulfilled" ? summaryR.value : null,
      transactions: txR.status === "fulfilled" ? txR.value : [],
      integrations: [],
    });
    setFailures(failed);
    // Non-blocking: the integrations panel fills in if/when this resolves; a slow
    // or unreachable backend no longer holds up the whole dashboard.
    settingsApi
      .integrations()
      .then((res) => setData((cur) => (cur ? { ...cur, integrations: res.integrations } : cur)))
      .catch(() => setFailures((cur) => (cur.includes("integrations") ? cur : [...cur, "integrations"])));
  };

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const openTasks = useMemo(() => data?.tasks.filter((t) => t.status !== "DONE") ?? [], [data]);

  // Display-only: share of this month's income kept as balance (no MoM data exists).
  const summary = data?.summary ?? null;
  const netPct =
    summary && summary.total_income > 0 ? Math.round((summary.balance / summary.total_income) * 100) : null;

  // Weekly expense buckets for the current month (real data, honest).
  const weeklyBars = useMemo(() => {
    const buckets = [0, 0, 0, 0, 0];
    (data?.transactions ?? []).forEach((t) => {
      // Parse "YYYY-MM-DD" as a LOCAL date. `new Date(string)` treats it as UTC
      // midnight, which rolls back a day in negative-offset timezones and drops
      // transactions into the wrong week/month.
      const [yy, mm, dd] = (t.transaction_date || "").split("-").map(Number);
      const d = new Date(yy, (mm || 1) - 1, dd || 1);
      if (d.getFullYear() === year && d.getMonth() + 1 === month && t.type === "EXPENSE") {
        const week = Math.min(4, Math.floor((d.getDate() - 1) / 7));
        buckets[week] += t.amount;
      }
    });
    return buckets.map((value, i) => ({ label: `W${i + 1}`, value }));
  }, [data, month, year]);

  return (
    <AppShell>
      <div className="mb-6 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div className="min-w-0">
          <div className="mb-3.5 flex flex-wrap items-center gap-2">
            <Badge tone="primary" dot className="shadow-[0_0_16px_rgb(var(--color-primary)/0.2)]">
              {APP_VERSION}
            </Badge>
            <Badge tone="neutral">Local-first</Badge>
          </div>
          <h1 className="text-2xl font-semibold tracking-tight text-content sm:text-[34px]">
            {greeting()},{" "}
            <span className="text-grad">{user?.full_name?.split(" ")[0] || "Operator"}</span>
          </h1>
          <p className="mt-2 max-w-xl text-sm leading-relaxed text-content-muted">
            Your command center is ready: routines, tasks, finance, notes, approvals, and AI context in one focused workspace.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2 lg:shrink-0">
          <Link
            href="/dashboard/routines"
            className="inline-flex h-[42px] items-center gap-2 rounded-md border border-border bg-surface-input/50 px-[15px] text-[13px] font-medium text-content transition-all duration-200 hover:border-primary/40 hover:bg-surface-raised/60 hover:text-primary-bright"
          >
            <CalendarDays size={15} /> Routine
          </Link>
          <Link
            href="/dashboard/approvals"
            className="inline-flex h-[42px] items-center gap-2 rounded-md border border-border bg-surface-input/50 px-[15px] text-[13px] font-medium text-content transition-all duration-200 hover:border-primary/40 hover:bg-surface-raised/60 hover:text-primary-bright"
          >
            <ClipboardCheck size={15} /> Approvals
          </Link>
          <Link
            href="/dashboard/ai"
            className="grad-primary inline-flex h-[42px] items-center gap-2 rounded-md px-4 text-[13px] font-semibold text-primary-fg shadow-btn-primary transition-all duration-200 hover:brightness-[1.06]"
          >
            <Bot size={15} /> AI Chat
          </Link>
        </div>
      </div>

      {error ? (
        <ErrorState message={error} onRetry={load} />
      ) : !data ? (
        <Loading label="Loading your command center…" />
      ) : (
        <>
          {failures.length > 0 ? (
            <div className="mb-5 flex flex-wrap items-center gap-2 rounded-md border border-warning/30 bg-warning/10 px-3.5 py-2.5 text-[13px]">
              <span className="text-content-muted">
                Couldn&apos;t load: {failures.join(", ")}.
              </span>
              <button onClick={load} className="font-medium text-primary-bright hover:underline">
                Retry
              </button>
            </div>
          ) : null}
          <div className="grid gap-5 xl:grid-cols-3">
          {/* Left column */}
          <div className="space-y-5 xl:col-span-2">
            <Card padding="lg">
              <div className="mb-5 flex items-center gap-3">
                <span className="grad-primary flex h-[42px] w-[42px] shrink-0 items-center justify-center rounded-[13px] text-primary-fg shadow-glow-primary">
                  <Sparkles size={18} />
                </span>
                <div>
                  <h2 className="text-[15px] font-semibold text-content">Workspace Snapshot</h2>
                  <p className="mt-0.5 text-[12.5px] text-content-muted">A live snapshot of your workspace.</p>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3.5 sm:grid-cols-3">
                <MiniStat icon={ListTodo} label="Open tasks" value={String(openTasks.length)} />
                <MiniStat icon={StickyNote} label="Notes" value={String(data.notes.length)} tone="violet" />
                <MiniStat
                  icon={Wallet}
                  label="Txns / month"
                  value={data.summary ? String(data.summary.transaction_count) : "—"}
                />
              </div>
            </Card>

            <Card padding="lg">
              <CardHeader
                title="Monthly cashflow"
                icon={<Wallet size={18} />}
                action={
                  netPct !== null ? (
                    <Badge tone={netPct >= 0 ? "success" : "danger"}>
                      <TrendingUp size={12} />
                      {netPct >= 0 ? "+" : ""}
                      {netPct}% net
                    </Badge>
                  ) : null
                }
              />
              {data.summary ? (
                <>
                  <p className="label-mono">Current balance</p>
                  <p className="glow-text mt-1.5 text-[28px] font-semibold tracking-[-0.025em] text-content sm:text-4xl">
                    {formatCurrency(data.summary.balance, data.summary.currency)}
                  </p>
                </>
              ) : (
                <p className="py-2 text-[13px] text-content-muted">
                  Cashflow couldn&apos;t be loaded.{" "}
                  <button onClick={load} className="font-medium text-primary-bright hover:underline">
                    Retry
                  </button>
                </p>
              )}
              <div className="mt-5">
                <BarChart data={weeklyBars} height={150} />
              </div>
              {data.summary ? (
                <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-border/80 pt-3.5 text-[12.5px]">
                  <span className="inline-flex items-center gap-1.5 rounded border border-success/25 bg-success/10 px-[11px] py-1.5 text-content-muted">
                    Income{" "}
                    <span className="font-semibold text-success-soft">
                      {formatCurrency(data.summary.total_income, data.summary.currency)}
                    </span>
                  </span>
                  <span className="inline-flex items-center gap-1.5 rounded border border-danger/25 bg-danger/10 px-[11px] py-1.5 text-content-muted">
                    Expense{" "}
                    <span className="font-semibold text-danger">
                      {formatCurrency(data.summary.total_expense, data.summary.currency)}
                    </span>
                  </span>
                  <span className="text-[11.5px] text-content-faint sm:ml-auto">
                    Tracks cashflow. Not financial advice.
                  </span>
                </div>
              ) : null}
            </Card>

            <Card gradient className="flex items-start gap-3.5">
              <span className="grad-primary flex h-11 w-11 shrink-0 items-center justify-center rounded-md text-primary-fg shadow-glow-primary">
                <ShieldCheck size={21} />
              </span>
              <div>
                <p className="text-sm font-semibold text-content">Human-in-the-loop where it matters</p>
                <p className="mt-1 text-[13px] leading-relaxed text-content-muted">
                  Reads and low-risk memory updates can run quickly. Risky writes stay pending
                  until you approve, edit, or reject them.
                </p>
                <Link
                  href="/dashboard/ai"
                  className="mt-2.5 inline-flex items-center gap-1 text-[13px] font-medium text-primary-bright hover:underline"
                >
                  Open AI Chat <ArrowUpRight size={14} />
                </Link>
              </div>
            </Card>
          </div>

          {/* Right column */}
          <div className="space-y-5">
            <Card>
              <CardHeader
                title="Pending tasks"
                icon={<ListTodo size={18} />}
                action={
                  <Link
                    href="/dashboard/tasks"
                    className="inline-flex items-center gap-1 text-[13px] font-medium text-primary-bright hover:underline"
                  >
                    View all <ArrowUpRight size={14} />
                  </Link>
                }
              />
              {openTasks.length === 0 ? (
                <p className="py-4 text-[13px] text-content-muted">No open tasks. You&apos;re all caught up.</p>
              ) : (
                <ul className="space-y-2.5">
                  {openTasks.slice(0, 5).map((task) => {
                    const items = task.checklist_items ?? [];
                    const doneCount = items.filter((i) => i.is_done).length;
                    return (
                      <li
                        key={task.id}
                        className="flex items-center justify-between gap-2 rounded-lg border border-border/80 bg-white/[0.025] px-[13px] py-[11px]"
                      >
                        <span className="min-w-0">
                          <span className="block truncate text-[13px] text-content">{task.title}</span>
                          {items.length > 0 ? (
                            <span className="font-mono text-[10px] uppercase tracking-wide text-content-subtle">
                              checklist {doneCount}/{items.length}
                            </span>
                          ) : null}
                        </span>
                        <PriorityBadge priority={task.priority} />
                      </li>
                    );
                  })}
                </ul>
              )}
            </Card>

            <Card>
              <div className="mb-[18px] flex items-center gap-2.5">
                <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-secondary/20 bg-secondary/12 text-secondary-soft">
                  <Bot size={16} />
                </span>
                <h3 className="text-[15px] font-semibold text-content">Integration status</h3>
              </div>
              <ul className="space-y-3.5">
                {data.integrations.map((integration) => (
                  <li key={integration.key} className="flex flex-wrap items-center justify-between gap-2">
                    <span className="flex min-w-0 items-center gap-2.5 text-[13px] text-content">
                      <StatusDot status={integration.status} pulse />
                      <span className="truncate">{integration.name}</span>
                    </span>
                    <ConfigStatusBadge status={integration.status} />
                  </li>
                ))}
              </ul>
              <Link
                href="/dashboard/settings"
                className="mt-[18px] inline-flex items-center gap-1 text-[13px] font-medium text-primary-bright hover:underline"
              >
                Manage integrations <ArrowUpRight size={14} />
              </Link>
            </Card>
          </div>
        </div>
        </>
      )}
    </AppShell>
  );
}
