"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Check,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  ListTodo,
  Plus,
  RotateCcw,
  Sparkles,
  Trash2,
  X,
} from "lucide-react";
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
import { TaskChecklist } from "@/components/tasks/TaskChecklist";
import { tasksApi, ApiException } from "@/lib/api";
import { cn, formatDate } from "@/lib/format";
import type { Task, TaskPriority } from "@/types";

const PRIORITIES: TaskPriority[] = ["LOW", "NORMAL", "HIGH", "URGENT"];
const MAX_ITEMS = 5;

export default function TasksPage() {
  const [tasks, setTasks] = useState<Task[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState("ALL");
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [aiBanner, setAiBanner] = useState(true);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [form, setForm] = useState({
    title: "",
    description: "",
    priority: "NORMAL" as TaskPriority,
    due_at: "",
    checklist: [""] as string[],
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

  const filtered = useMemo(
    () => (!tasks ? [] : tab === "ALL" ? tasks : tasks.filter((t) => t.status === tab)),
    [tasks, tab],
  );

  const patchTask = (updated: Task) =>
    setTasks((prev) => prev?.map((t) => (t.id === updated.id ? updated : t)) ?? prev);

  const create = async (event: React.FormEvent) => {
    event.preventDefault();
    setSaving(true);
    try {
      await tasksApi.create({
        title: form.title,
        description: form.description || undefined,
        priority: form.priority,
        due_at: form.due_at ? new Date(form.due_at).toISOString() : undefined,
        checklist: form.checklist.map((c) => c.trim()).filter(Boolean),
      });
      setOpen(false);
      setForm({ title: "", description: "", priority: "NORMAL", due_at: "", checklist: [""] });
      await load();
    } catch (err) {
      setError(err instanceof ApiException ? err.message : "Failed to create task.");
    } finally {
      setSaving(false);
    }
  };

  const toggleDone = async (task: Task) => {
    const done = task.status !== "DONE";
    patchTask({ ...task, status: done ? "DONE" : "TODO" });
    try {
      patchTask(done ? await tasksApi.complete(task.id) : await tasksApi.reopen(task.id));
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

  const setChecklistField = (idx: number, value: string) =>
    setForm((f) => ({ ...f, checklist: f.checklist.map((c, i) => (i === idx ? value : c)) }));
  const addChecklistField = () =>
    setForm((f) => (f.checklist.length >= MAX_ITEMS ? f : { ...f, checklist: [...f.checklist, ""] }));
  const removeChecklistField = (idx: number) =>
    setForm((f) => ({ ...f, checklist: f.checklist.filter((_, i) => i !== idx) }));

  return (
    <AppShell>
      <PageHeader
        title="Active Commands"
        subtitle="Manage your operational tasks and command checklists."
        actions={
          <Button onClick={() => setOpen(true)}>
            <Plus size={16} /> Create Task
          </Button>
        }
      />

      {aiBanner ? (
        <Card gradient padding="none" className="mb-[18px] px-[18px] py-[15px]">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
            <div className="flex flex-1 items-center gap-[13px]">
              <span className="grad-primary flex h-[38px] w-[38px] shrink-0 items-center justify-center rounded-md text-primary-fg shadow-glow-primary">
                <Sparkles size={18} />
              </span>
              <div className="min-w-0">
                <p className="text-[13.5px] font-semibold text-content">Command checklists</p>
                <p className="mt-0.5 text-[12.5px] text-content-muted">
                  Break a command into up to {MAX_ITEMS} checklist steps, track progress, and mark it
                  done. AI suggestions require approval — nothing runs automatically.
                </p>
              </div>
            </div>
            <button
              onClick={() => setAiBanner(false)}
              className="self-start text-[12.5px] text-content-subtle transition-colors hover:text-content sm:self-center"
            >
              Dismiss
            </button>
          </div>
        </Card>
      ) : null}

      <Tabs
        className="mb-[18px]"
        value={tab}
        onChange={setTab}
        items={[
          { value: "ALL", label: "All", count: counts.ALL },
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
          title={tab === "ALL" ? "No commands yet" : "Nothing here"}
          description={tab === "ALL" ? "Create your first command to start tracking work." : "No tasks in this view."}
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
        <div className="space-y-3">
          {filtered.map((task) => {
            const items = task.checklist_items ?? [];
            const done = items.filter((i) => i.is_done).length;
            const isOpen = expanded[task.id];
            const isDone = task.status === "DONE";
            return (
              <Card
                key={task.id}
                padding="none"
                className={cn("px-[18px] py-4", isDone && "opacity-70")}
                hover={!isDone}
              >
                <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                  <div className="flex min-w-0 items-start gap-[13px]">
                    <button
                      onClick={() => toggleDone(task)}
                      className={cn(
                        "mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-[7px] border-[1.5px] transition-colors",
                        isDone
                          ? "border-success bg-success text-bg"
                          : "border-border-strong hover:border-primary hover:shadow-[0_0_10px_rgb(var(--color-primary)/0.3)]",
                      )}
                      aria-label={isDone ? "Reopen task" : "Mark task done"}
                    >
                      {isDone ? <Check size={13} strokeWidth={3} /> : null}
                    </button>
                    <div className="min-w-0">
                      <p className={cn("text-sm font-medium", isDone ? "text-content-subtle line-through" : "text-content")}>
                        {task.title}
                      </p>
                      <div className="mt-2 flex flex-wrap items-center gap-2">
                        {!isDone ? (
                          <span className="hidden sm:inline-flex">
                            <PriorityBadge priority={task.priority} />
                          </span>
                        ) : null}
                        <TaskStatusLabel status={task.status} />
                        {task.due_at ? (
                          <span className={cn("text-[12px]", isDone ? "text-content-faint" : "text-content-subtle")}>
                            · {isDone ? "" : "Due "}
                            {formatDate(task.due_at)}
                          </span>
                        ) : null}
                        {items.length > 0 ? (
                          <button
                            onClick={() => setExpanded((e) => ({ ...e, [task.id]: !e[task.id] }))}
                            className="inline-flex items-center gap-1 text-[12px] text-primary-bright transition-colors hover:text-primary"
                          >
                            {isOpen ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
                            Checklist {done}/{items.length}
                          </button>
                        ) : (
                          <button
                            onClick={() => setExpanded((e) => ({ ...e, [task.id]: !e[task.id] }))}
                            className="inline-flex items-center gap-1 text-[12px] text-content-subtle transition-colors hover:text-primary-bright"
                          >
                            <Plus size={12} /> Add checklist
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                  <div className="flex shrink-0 flex-wrap items-center justify-end gap-2">
                    <Button variant="ghost" size="sm" onClick={() => toggleDone(task)} className="flex-1 sm:flex-none">
                      {isDone ? (
                        <>
                          <RotateCcw size={14} /> Reopen
                        </>
                      ) : (
                        <>
                          <CheckCircle2 size={14} /> Done
                        </>
                      )}
                    </Button>
                    <button
                      onClick={() => remove(task)}
                      className="flex h-8 w-8 items-center justify-center rounded-sm text-content-subtle transition-colors hover:bg-danger/10 hover:text-danger"
                      aria-label="Delete task"
                    >
                      <Trash2 size={15} />
                    </button>
                  </div>
                </div>
                {isOpen ? <TaskChecklist task={task} onChange={patchTask} /> : null}
              </Card>
            );
          })}
        </div>
      )}

      {tasks && tasks.length > 0 ? (
        <div className="mt-5 grid gap-4 sm:grid-cols-3">
          <div className="glass-tile p-[18px]">
            <p className="label-mono">Total</p>
            <p className="mt-2 text-[26px] font-semibold leading-none text-content">{counts.ALL}</p>
          </div>
          <div className="glass-tile p-[18px]">
            <p className="label-mono">In progress</p>
            <p className="mt-2 text-[26px] font-semibold leading-none text-primary-bright">{counts.IN_PROGRESS}</p>
          </div>
          <div className="glass-tile p-[18px]">
            <p className="label-mono">Completed</p>
            <p className="mt-2 text-[26px] font-semibold leading-none text-success-soft">{counts.DONE}</p>
          </div>
        </div>
      ) : null}

      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title="Create command"
        description="Add a task with an optional checklist (max 5 steps)."
        footer={
          <>
            <Button variant="ghost" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button form="task-form" type="submit" loading={saving} disabled={!form.title.trim()}>
              Create command
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
          <div className="grid gap-3 sm:grid-cols-2">
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

          <div>
            <div className="mb-1.5 flex items-center justify-between">
              <label className="block text-[12px] font-medium uppercase tracking-wide text-content-muted">
                Checklist
              </label>
              <span className="text-[11px] text-content-subtle">
                {form.checklist.filter((c) => c.trim()).length}/{MAX_ITEMS}
              </span>
            </div>
            <div className="space-y-2">
              {form.checklist.map((value, idx) => (
                <div key={idx} className="flex items-center gap-2">
                  <span className="flex h-4 w-4 shrink-0 rounded-[5px] border-[1.5px] border-border-strong" />
                  <input
                    value={value}
                    onChange={(e) => setChecklistField(idx, e.target.value)}
                    placeholder={`Step ${idx + 1}`}
                    className="h-9 min-w-0 flex-1 rounded-md border border-border bg-surface-input px-2.5 text-[13px] text-content placeholder:text-content-subtle focus:border-primary/70 focus:outline-none"
                  />
                  {form.checklist.length > 1 ? (
                    <button
                      type="button"
                      onClick={() => removeChecklistField(idx)}
                      className="text-content-subtle hover:text-danger"
                      aria-label="Remove step"
                    >
                      <X size={14} />
                    </button>
                  ) : null}
                </div>
              ))}
            </div>
            {form.checklist.length < MAX_ITEMS ? (
              <button
                type="button"
                onClick={addChecklistField}
                className="mt-2 inline-flex items-center gap-1 text-[12px] text-primary hover:underline"
              >
                <Plus size={13} /> Add step
              </button>
            ) : null}
          </div>
        </form>
      </Modal>
    </AppShell>
  );
}
