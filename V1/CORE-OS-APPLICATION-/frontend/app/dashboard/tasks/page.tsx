"use client";

import { useEffect, useState } from "react";
import { ListTodo, Plus, Trash2 } from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Input } from "@/components/ui/Input";
import { Textarea } from "@/components/ui/Textarea";
import { Modal } from "@/components/ui/Modal";
import { Loading, ErrorState, EmptyState } from "@/components/ui/States";
import { tasksApi, ApiException } from "@/lib/api";
import { formatDate } from "@/lib/format";
import type { Task, TaskPriority, TaskStatus } from "@/types";

const STATUSES: TaskStatus[] = ["TODO", "IN_PROGRESS", "DONE"];
const PRIORITIES: TaskPriority[] = ["LOW", "NORMAL", "HIGH", "URGENT"];

const selectClass =
  "h-9 rounded-md border border-border bg-surface-input px-2 text-[13px] text-content focus:border-primary focus:outline-none";

export default function TasksPage() {
  const [tasks, setTasks] = useState<Task[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({ title: "", description: "", priority: "NORMAL" as TaskPriority, due_at: "" });

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
    <AppShell title="Tasks" subtitle="Workspace-scoped, soft-deleted, and audited">
      <div className="mb-5 flex items-center justify-between">
        <p className="text-[13px] text-content-muted">
          {tasks ? `${tasks.length} task${tasks.length === 1 ? "" : "s"}` : "—"}
        </p>
        <Button onClick={() => setOpen(true)}>
          <Plus size={16} /> New task
        </Button>
      </div>

      {error ? (
        <ErrorState message={error} onRetry={load} />
      ) : !tasks ? (
        <Loading />
      ) : tasks.length === 0 ? (
        <EmptyState
          title="No tasks yet"
          description="Create your first task to start tracking work."
          icon={<ListTodo size={20} />}
          action={
            <Button onClick={() => setOpen(true)}>
              <Plus size={16} /> New task
            </Button>
          }
        />
      ) : (
        <div className="space-y-2.5">
          {tasks.map((task) => (
            <Card key={task.id} hover className="flex items-center justify-between gap-4 p-4">
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <p
                    className={
                      "truncate text-sm font-medium " +
                      (task.status === "DONE" ? "text-content-subtle line-through" : "text-content")
                    }
                  >
                    {task.title}
                  </p>
                  <Badge
                    tone={
                      task.priority === "URGENT"
                        ? "danger"
                        : task.priority === "HIGH"
                          ? "warning"
                          : "neutral"
                    }
                  >
                    {task.priority}
                  </Badge>
                </div>
                {task.description ? (
                  <p className="mt-1 truncate text-[13px] text-content-muted">{task.description}</p>
                ) : null}
                {task.due_at ? (
                  <p className="mt-1 label-mono">Due {formatDate(task.due_at)}</p>
                ) : null}
              </div>
              <div className="flex shrink-0 items-center gap-2">
                <select
                  className={selectClass}
                  value={task.status}
                  onChange={(e) => changeStatus(task, e.target.value as TaskStatus)}
                >
                  {STATUSES.map((status) => (
                    <option key={status} value={status}>
                      {status.replace("_", " ")}
                    </option>
                  ))}
                </select>
                <button
                  onClick={() => remove(task)}
                  className="text-content-subtle transition-colors hover:text-danger"
                  aria-label="Delete task"
                >
                  <Trash2 size={16} />
                </button>
              </div>
            </Card>
          ))}
        </div>
      )}

      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title="New task"
        footer={
          <>
            <Button variant="ghost" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button form="task-form" type="submit" disabled={saving || !form.title.trim()}>
              {saving ? "Saving…" : "Create task"}
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
            <div className="space-y-1.5">
              <label className="block text-[13px] font-medium text-content-muted">Priority</label>
              <select
                className={selectClass + " w-full"}
                value={form.priority}
                onChange={(e) => setForm({ ...form, priority: e.target.value as TaskPriority })}
              >
                {PRIORITIES.map((p) => (
                  <option key={p} value={p}>
                    {p}
                  </option>
                ))}
              </select>
            </div>
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
