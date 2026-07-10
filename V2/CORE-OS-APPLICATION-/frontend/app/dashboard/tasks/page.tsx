"use client";

import { useEffect, useMemo, useState } from "react";
import { ListTodo, Plus, Sparkles, Trash2 } from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { PageHeader } from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { Textarea } from "@/components/ui/Textarea";
import { Modal } from "@/components/ui/Modal";
import { Tabs } from "@/components/ui/Tabs";
import { PriorityBadge, TaskStatusLabel } from "@/components/ui/meta";
import { ErrorState, Loading, EmptyState } from "@/components/ui/States";
import { tasksApi, ApiException } from "@/lib/api";
import { formatDate } from "@/lib/format";
import type { Task, TaskPriority, TaskStatus } from "@/types";

const PRIORITIES: TaskPriority[] = ["LOW", "NORMAL", "HIGH", "URGENT"];
const STATUSES: TaskStatus[] = ["TODO", "IN_PROGRESS", "DONE"];

const priorityDot: Record<TaskPriority, string> = {
  URGENT: "bg-danger",
  HIGH: "bg-warning",
  NORMAL: "bg-info",
  LOW: "bg-content-subtle",
};

export default function TasksPage() {
  const [tasks, setTasks] = useState<Task[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<string>("ALL");
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [aiBanner, setAiBanner] = useState(true);
  const [form, setForm] = useState({
    title: "",
    description: "",
    priority: "NORMAL" as TaskPriority,
    due_at: "",
  });

  const load = async () => {
    setError(null);
    try {
      setTasks(await tasksApi.list());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load tasks.");
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const counts = useMemo(() => {
    const all = tasks ?? [];
    return {
      ALL: all.length,
      TODO: all.filter((t) => t.status === "TODO").length,
      IN_PROGRESS: all.filter((t) => t.status === "IN_PROGRESS").length,
      DONE: all.filter((t) => t.status === "DONE").length,
    };
  }, [tasks]);

  const filtered = useMemo(() => {
    if (!tasks) return [];
    return tab === "ALL" ? tasks : tasks.filter((t) => t.status === tab);
  }, [tasks, tab]);

  const create = async (event: React.FormEvent) => {
    event.preventDefault();
    setSaving(true);
    try {
      await tasksApi.create({
        title: form.title,
        description: form.description || undefined,
        priority: form.priority,
        due_at: form.due_at ? new Date(form.due_at).toISOString() : undefined,
      });
      setOpen(false);
      setForm({ title: "", description: "", priority: "NORMAL", due_at: "" });
      await load();
    } catch (err) {
      setError(err instanceof ApiException ? err.message : "Failed to create task.");
    } finally {
      setSaving(false);
    }
  };

  const changeStatus = async (task: Task, status: TaskStatus) => {
    setTasks((prev) => prev?.map((t) => (t.id === task.id ? { ...t, status } : t)) ?? prev);
    try {
      await tasksApi.update(task.id, { status });
    } catch {
      void load();
    }
  };

  const remove = async (task: Task) => {
    setTasks((prev) => prev?.filter((t) => t.id !== task.id) ?? prev);
    try {
      await tasksApi.remove(task.id);
    } catch {
      void load();
    }
  };

  return (
    <AppShell>
      <PageHeader
        title="Active Commands"
        subtitle="Manage your high-priority operational tasks."
        actions={
          <Button onClick={() => setOpen(true)}>
            <Plus size={16} /> Create Task
          </Button>
        }
      />

      {/* Honest AI banner (no fake suggestions) */}
      {aiBanner ? (
        <Card className="mb-5 border-primary/20" padding="md">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-start gap-3">
              <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary/12 text-primary">
                <Sparkles size={18} />
              </span>
              <div>
                <p className="text-sm font-semibold text-content">AI scheduling assistant</p>
                <p className="mt-0.5 text-[13px] text-content-muted">
                  When a local model is configured, AI can propose schedules here. AI suggestions
                  require approval — nothing is applied automatically.
                </p>
              </div>
            </div>
            <Button variant="ghost" size="sm" onClick={() => setAiBanner(false)}>
              Dismiss
            </Button>
          </div>
        </Card>
      ) : null}

      <Tabs
        className="mb-4"
        value={tab}
        onChange={setTab}
        items={[
          { value: "ALL", label: "All Tasks", count: counts.ALL },
          { value: "TODO", label: "Todo", count: counts.TODO },
          { value: "IN_PROGRESS", label: "In Progress", count: counts.IN_PROGRESS },
          { value: "DONE", label: "Done", count: counts.DONE },
        ]}
      />

      {error ? (
        <ErrorState message={error} onRetry={load} />
      ) : !tasks ? (
        <Loading />
      ) : filtered.length === 0 ? (
        <EmptyState
          title={tab === "ALL" ? "No tasks yet" : "Nothing here"}
          description={tab === "ALL" ? "Create your first task to start tracking work." : "No tasks in this view."}
          icon={<ListTodo size={20} />}
          action={
            tab === "ALL" ? (
              <Button onClick={() => setOpen(true)}>
                <Plus size={16} /> Create Task
              </Button>
            ) : undefined
          }
        />
      ) : (
        <Card padding="none" className="overflow-hidden">
          {/* Desktop table */}
          <table className="hidden w-full md:table">
            <thead>
              <tr className="border-b border-border text-left">
                {["Task Name", "Priority", "Due Date", "Status", ""].map((h) => (
                  <th key={h} className="px-5 py-3 text-[11px] font-medium uppercase tracking-wide text-content-subtle">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.map((task) => (
                <tr key={task.id} className="border-b border-border/60 last:border-0 hover:bg-surface-raised/40">
                  <td className="px-5 py-3.5">
                    <div className="flex items-center gap-2.5">
                      <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${priorityDot[task.priority]}`} />
                      <span className={task.status === "DONE" ? "text-content-subtle line-through" : "text-content"}>
                        {task.title}
                      </span>
                    </div>
                  </td>
                  <td className="px-5 py-3.5">
                    <PriorityBadge priority={task.priority} />
                  </td>
                  <td className="px-5 py-3.5 text-[13px] text-content-muted">{formatDate(task.due_at)}</td>
                  <td className="px-5 py-3.5">
                    <select
                      value={task.status}
                      onChange={(e) => changeStatus(task, e.target.value as TaskStatus)}
                      className="cursor-pointer rounded-md border border-transparent bg-transparent text-[13px] text-content hover:border-border focus:border-primary/60 focus:outline-none"
                    >
                      {STATUSES.map((s) => (
                        <option key={s} value={s}>
                          {s.replace("_", " ")}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td className="px-5 py-3.5 text-right">
                    <button
                      onClick={() => remove(task)}
                      className="text-content-subtle transition-colors hover:text-danger"
                      aria-label="Delete task"
                    >
                      <Trash2 size={16} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {/* Mobile cards */}
          <ul className="divide-y divide-border md:hidden">
            {filtered.map((task) => (
              <li key={task.id} className="p-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className={task.status === "DONE" ? "text-content-subtle line-through" : "text-content"}>
                      {task.title}
                    </p>
                    <div className="mt-1.5 flex items-center gap-2">
                      <PriorityBadge priority={task.priority} />
                      <span className="text-[12px] text-content-subtle">{formatDate(task.due_at)}</span>
                    </div>
                  </div>
                  <button
                    onClick={() => remove(task)}
                    className="text-content-subtle hover:text-danger"
                    aria-label="Delete task"
                  >
                    <Trash2 size={15} />
                  </button>
                </div>
                <div className="mt-3">
                  <Select value={task.status} onChange={(e) => changeStatus(task, e.target.value as TaskStatus)}>
                    {STATUSES.map((s) => (
                      <option key={s} value={s}>
                        {s.replace("_", " ")}
                      </option>
                    ))}
                  </Select>
                </div>
              </li>
            ))}
          </ul>
        </Card>
      )}

      {/* Stat tiles (real counts) */}
      {tasks && tasks.length > 0 ? (
        <div className="mt-5 grid grid-cols-3 gap-4">
          <Card padding="sm">
            <p className="label-mono">Total</p>
            <p className="mt-1 text-2xl font-semibold text-content">{counts.ALL}</p>
          </Card>
          <Card padding="sm">
            <p className="label-mono">In progress</p>
            <p className="mt-1 text-2xl font-semibold text-info">{counts.IN_PROGRESS}</p>
          </Card>
          <Card padding="sm">
            <p className="label-mono">Completed</p>
            <p className="mt-1 text-2xl font-semibold text-success">{counts.DONE}</p>
          </Card>
        </div>
      ) : null}

      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title="Create task"
        description="Add a new operational task to your workspace."
        footer={
          <>
            <Button variant="ghost" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button form="task-form" type="submit" loading={saving} disabled={!form.title.trim()}>
              Create task
            </Button>
          </>
        }
      >
        <form id="task-form" onSubmit={create} className="space-y-4">
          <Input
            id="title"
            label="Title"
            required
            placeholder="What needs to be done?"
            value={form.title}
            onChange={(e) => setForm({ ...form, title: e.target.value })}
          />
          <Textarea
            id="description"
            label="Description"
            placeholder="Optional details"
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
          />
          <div className="grid grid-cols-2 gap-3">
            <Select
              id="priority"
              label="Priority"
              value={form.priority}
              onChange={(e) => setForm({ ...form, priority: e.target.value as TaskPriority })}
            >
              {PRIORITIES.map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </Select>
            <Input
              id="due_at"
              label="Due date"
              type="date"
              value={form.due_at}
              onChange={(e) => setForm({ ...form, due_at: e.target.value })}
            />
          </div>
        </form>
      </Modal>
    </AppShell>
  );
}
