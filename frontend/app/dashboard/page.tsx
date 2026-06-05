"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  ArrowUpRight,
  Bot,
  ListTodo,
  ShieldCheck,
  Sparkles,
  StickyNote,
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
import { financeApi, notesApi, settingsApi, tasksApi } from "@/lib/api";
import { getStoredUser } from "@/lib/auth";
import { formatCurrency, greeting } from "@/lib/format";
import type { FinanceSummary, Integration, Note, Task, Transaction } from "@/types";

interface Data {
  tasks: Task[];
  notes: Note[];
  summary: FinanceSummary;
  transactions: Transaction[];
  integrations: Integration[];
}

function MiniStat({ icon: Icon, label, value }: { icon: LucideIcon; label: string; value: string }) {
  return (
    <div className="rounded-lg border border-border bg-surface-input/70 p-3.5">
      <div className="mb-2 flex items-center gap-1.5 text-content-subtle">
        <Icon size={13} />
        <span className="text-[10.5px] font-medium uppercase tracking-wide">{label}</span>
      </div>
      <p className="text-xl font-semibold tracking-tight text-content">{value}</p>
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

  const load = async () => {
    setError(null);
    setData(null);
    try {
      const [tasks, notes, summary, transactions, integrations] = await Promise.all([
        tasksApi.list(),
        notesApi.list(),
        financeApi.summary(year, month),
        financeApi.listTransactions(),
        settingsApi.integrations(),
      ]);
      setData({ tasks, notes, summary, transactions, integrations: integrations.integrations });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load dashboard.");
    }
  };

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const openTasks = useMemo(() => data?.tasks.filter((t) => t.status !== "DONE") ?? [], [data]);

  // Weekly expense buckets for the current month (real data, honest).
  const weeklyBars = useMemo(() => {
    const buckets = [0, 0, 0, 0, 0];
    (data?.transactions ?? []).forEach((t) => {
      const d = new Date(t.transaction_date);
      if (d.getFullYear() === year && d.getMonth() + 1 === month && t.type === "EXPENSE") {
        const week = Math.min(4, Math.floor((d.getDate() - 1) / 7));
        buckets[week] += t.amount;
      }
    });
    return buckets.map((value, i) => ({ label: `W${i + 1}`, value }));
  }, [data, month, year]);

  return (
    <AppShell>
      {/* Greeting */}
      <div className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight text-content sm:text-[28px]">
          {greeting()}, {user?.full_name?.split(" ")[0] || "Operator"}
        </h1>
        <p className="mt-1 text-[13.5px] text-content-muted">
          Your local-first command center is ready. Human approval required for write actions.
        </p>
      </div>

      {error ? (
        <ErrorState message={error} onRetry={load} />
      ) : !data ? (
        <Loading label="Loading your command center…" />
      ) : (
        <div className="grid gap-5 lg:grid-cols-3">
          {/* Left column */}
          <div className="space-y-5 lg:col-span-2">
            <Card gradient padding="lg">
              <div className="mb-4 flex items-center gap-2.5">
                <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/12 text-primary">
                  <Sparkles size={18} />
                </span>
                <div>
                  <h2 className="text-[15px] font-semibold text-content">AI Command Center</h2>
                  <p className="text-[12.5px] text-content-muted">A live snapshot of your workspace.</p>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                <MiniStat icon={ListTodo} label="Open tasks" value={String(openTasks.length)} />
                <MiniStat icon={StickyNote} label="Notes" value={String(data.notes.length)} />
                <MiniStat
                  icon={Wallet}
                  label="Txns / month"
                  value={String(data.summary.transaction_count)}
                />
              </div>
            </Card>

            <Card>
              <CardHeader title="Monthly cashflow" icon={<Wallet size={18} />} />
              <p className="font-mono text-[11px] uppercase tracking-widest text-content-subtle">
                Current balance
              </p>
              <p className="mt-1 text-3xl font-semibold tracking-tight text-content">
                {formatCurrency(data.summary.balance, data.summary.currency)}
              </p>
              <div className="mt-5">
                <BarChart data={weeklyBars} />
              </div>
              <div className="mt-4 flex flex-wrap items-center gap-x-6 gap-y-2 border-t border-border pt-3 text-[13px]">
                <span className="text-content-muted">
                  Income{" "}
                  <span className="font-medium text-success">
                    {formatCurrency(data.summary.total_income, data.summary.currency)}
                  </span>
                </span>
                <span className="text-content-muted">
                  Expense{" "}
                  <span className="font-medium text-danger">
                    {formatCurrency(data.summary.total_expense, data.summary.currency)}
                  </span>
                </span>
                <span className="ml-auto text-[12px] text-content-subtle">
                  CoreOS tracks cashflow. It does not provide financial advice.
                </span>
              </div>
            </Card>

            <Card className="border-primary/20">
              <div className="flex items-start gap-3">
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
                  <ShieldCheck size={20} />
                </span>
                <div>
                  <p className="text-sm font-semibold text-content">Human-in-the-loop AI</p>
                  <p className="mt-1 text-[13px] leading-relaxed text-content-muted">
                    AI suggestions require approval. The assistant can propose actions but never
                    creates, updates, or deletes data on its own.
                  </p>
                  <Link
                    href="/dashboard/ai"
                    className="mt-2.5 inline-flex items-center gap-1 text-[13px] text-primary hover:underline"
                  >
                    Open AI Chat <ArrowUpRight size={14} />
                  </Link>
                </div>
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
                    className="inline-flex items-center gap-1 text-[13px] text-primary hover:underline"
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
                        className="flex items-center justify-between gap-2 rounded-lg border border-border bg-surface-input/50 px-3 py-2.5"
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
              <CardHeader title="Integration status" icon={<Bot size={18} />} />
              <ul className="space-y-3">
                {data.integrations.map((integration) => (
                  <li key={integration.key} className="flex items-center justify-between gap-2">
                    <span className="flex items-center gap-2.5 text-[13px] text-content">
                      <StatusDot status={integration.status} pulse />
                      {integration.name}
                    </span>
                    <ConfigStatusBadge status={integration.status} />
                  </li>
                ))}
              </ul>
              <Link
                href="/dashboard/settings"
                className="mt-4 inline-flex items-center gap-1 text-[13px] text-primary hover:underline"
              >
                Manage integrations <ArrowUpRight size={14} />
              </Link>
            </Card>
          </div>
        </div>
      )}
    </AppShell>
  );
}
