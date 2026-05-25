"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  ArrowUpRight,
  Bot,
  ListTodo,
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
import { Loading, ErrorState, EmptyState } from "@/components/ui/States";
import { financeApi, notesApi, settingsApi, tasksApi } from "@/lib/api";
import { formatCurrency, monthLabel } from "@/lib/format";
import type { FinanceSummary, Integration, Note, Task } from "@/types";

interface OverviewData {
  tasks: Task[];
  notes: Note[];
  summary: FinanceSummary;
  integrations: Integration[];
  aiConfigured: boolean;
}

function StatCard({
  icon: Icon,
  label,
  value,
  hint,
}: {
  icon: LucideIcon;
  label: string;
  value: string;
  hint?: string;
}) {
  return (
    <Card hover className="p-4">
      <div className="flex items-center justify-between">
        <span className="flex h-9 w-9 items-center justify-center rounded-lg border border-border bg-surface-input text-primary">
          <Icon size={18} />
        </span>
        {hint ? <span className="label-mono">{hint}</span> : null}
      </div>
      <p className="mt-3 text-2xl font-semibold tracking-tight text-content">{value}</p>
      <p className="text-[13px] text-content-muted">{label}</p>
    </Card>
  );
}

export default function DashboardOverview() {
  const now = new Date();
  const year = now.getFullYear();
  const month = now.getMonth() + 1;

  const [data, setData] = useState<OverviewData | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setError(null);
    setData(null);
    try {
      const [tasks, notes, summary, integrations] = await Promise.all([
        tasksApi.list(),
        notesApi.list(),
        financeApi.summary(year, month),
        settingsApi.integrations(),
      ]);
      const ollama = integrations.integrations.find((i) => i.key === "ollama");
      setData({
        tasks,
        notes,
        summary,
        integrations: integrations.integrations,
        aiConfigured: Boolean(ollama?.configured),
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load dashboard.");
    }
  };

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => {
    void load();
  }, []);

  const openTasks = data?.tasks.filter((t) => t.status !== "DONE") ?? [];

  return (
    <AppShell title="Dashboard" subtitle={monthLabel(year, month)}>
      {error ? (
        <ErrorState message={error} onRetry={load} />
      ) : !data ? (
        <Loading label="Loading your command center…" />
      ) : (
        <div className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard
              icon={ListTodo}
              label="Open tasks"
              value={String(openTasks.length)}
              hint={`${data.tasks.length} total`}
            />
            <StatCard icon={StickyNote} label="Notes" value={String(data.notes.length)} />
            <StatCard
              icon={Wallet}
              label={`Balance · ${data.summary.currency}`}
              value={formatCurrency(data.summary.balance, data.summary.currency)}
              hint={`${data.summary.transaction_count} txns`}
            />
            <StatCard
              icon={Bot}
              label="AI assistant"
              value={data.aiConfigured ? "Configured" : "Not configured"}
            />
          </div>

          <div className="grid gap-6 lg:grid-cols-3">
            <div className="space-y-6 lg:col-span-2">
              <Card>
                <CardHeader
                  title="Recent tasks"
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
                {data.tasks.length === 0 ? (
                  <EmptyState
                    title="No tasks yet"
                    description="Create your first task to start tracking work."
                  />
                ) : (
                  <ul className="divide-y divide-border">
                    {data.tasks.slice(0, 5).map((task) => (
                      <li key={task.id} className="flex items-center justify-between py-2.5">
                        <span className="truncate text-sm text-content">{task.title}</span>
                        <Badge
                          tone={
                            task.status === "DONE"
                              ? "success"
                              : task.priority === "URGENT" || task.priority === "HIGH"
                                ? "warning"
                                : "neutral"
                          }
                        >
                          {task.status === "DONE" ? "Done" : task.priority}
                        </Badge>
                      </li>
                    ))}
                  </ul>
                )}
              </Card>

              <Card>
                <CardHeader title="Monthly cashflow" icon={<TrendingUp size={18} />} />
                <div className="grid grid-cols-3 gap-4">
                  <div>
                    <p className="label-mono">Income</p>
                    <p className="mt-1 text-lg font-semibold text-success">
                      {formatCurrency(data.summary.total_income, data.summary.currency)}
                    </p>
                  </div>
                  <div>
                    <p className="label-mono">Expense</p>
                    <p className="mt-1 text-lg font-semibold text-danger">
                      {formatCurrency(data.summary.total_expense, data.summary.currency)}
                    </p>
                  </div>
                  <div>
                    <p className="label-mono">Balance</p>
                    <p className="mt-1 text-lg font-semibold text-content">
                      {formatCurrency(data.summary.balance, data.summary.currency)}
                    </p>
                  </div>
                </div>
                <p className="mt-4 text-[12px] text-content-subtle">
                  CoreOS tracks cashflow. It does not provide financial advice.
                </p>
              </Card>
            </div>

            <Card>
              <CardHeader title="Integration status" icon={<Bot size={18} />} />
              <ul className="space-y-3">
                {data.integrations.map((integration) => (
                  <li key={integration.key} className="flex items-center justify-between">
                    <span className="flex items-center gap-2.5 text-sm text-content">
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
