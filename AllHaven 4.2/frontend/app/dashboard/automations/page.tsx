"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ExternalLink, Info, Pencil, Plus, RefreshCw, Trash2, Workflow, Zap } from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { Textarea } from "@/components/ui/Textarea";
import { Select } from "@/components/ui/Select";
import { Badge } from "@/components/ui/Badge";
import { Toggle } from "@/components/ui/Toggle";
import { Modal } from "@/components/ui/Modal";
import { EmptyState, ErrorState, Loading } from "@/components/ui/States";
import { automationsApi, n8nApi, ApiException } from "@/lib/api";
import { cn } from "@/lib/format";
import type { Automation, N8nWorkflow, N8nWorkflowList } from "@/types";

const TRIGGER_TYPES = ["manual", "schedule", "webhook", "event"];
const ACTION_TYPES = ["notify", "http_request", "create_task", "create_note", "custom"];

interface AutomationForm {
  name: string;
  description: string;
  trigger_type: string;
  action_type: string;
}

const emptyForm: AutomationForm = {
  name: "",
  description: "",
  trigger_type: "manual",
  action_type: "notify",
};

function FlowStatus({ active, activeLabel = "Active", pausedLabel = "Paused" }: { active: boolean; activeLabel?: string; pausedLabel?: string }) {
  return active ? (
    <span className="inline-flex shrink-0 items-center gap-1.5 text-[12px] text-success-soft">
      <span className="h-1.5 w-1.5 rounded-full bg-success shadow-[0_0_8px_rgb(var(--color-success))]" />
      {activeLabel}
    </span>
  ) : (
    <span className="inline-flex shrink-0 items-center gap-1.5 text-[12px] text-content-subtle">
      <span className="h-1.5 w-1.5 rounded-full bg-content-faint" />
      {pausedLabel}
    </span>
  );
}

export default function AutomationsPage() {
  const [automations, setAutomations] = useState<Automation[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [editing, setEditing] = useState<Automation | null>(null);
  const [form, setForm] = useState<AutomationForm>(emptyForm);
  const [n8n, setN8n] = useState<N8nWorkflowList | null>(null);

  const load = async () => {
    setError(null);
    try {
      setAutomations(await automationsApi.list());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load automations.");
    }
  };

  const loadN8n = async () => {
    try {
      setN8n(await n8nApi.listWorkflows());
    } catch {
      setN8n({ status: "error", message: "Could not load n8n workflows.", base_url: "", workflows: [] });
    }
  };

  const toggleWorkflow = async (w: N8nWorkflow) => {
    // Optimistic; reload on failure so the UI reflects n8n's real state.
    setN8n((prev) =>
      prev ? { ...prev, workflows: prev.workflows.map((x) => (x.id === w.id ? { ...x, active: !x.active } : x)) } : prev,
    );
    try {
      await n8nApi.setActive(w.id, !w.active);
    } catch {
      await loadN8n();
    }
  };

  useEffect(() => {
    void load();
    void loadN8n();
  }, []);

  const openCreate = () => {
    setEditing(null);
    setForm(emptyForm);
    setOpen(true);
  };

  const openEdit = (a: Automation) => {
    setEditing(a);
    setForm({
      name: a.name,
      description: a.description ?? "",
      trigger_type: a.trigger_type || "manual",
      action_type: a.action_type || "notify",
    });
    setOpen(true);
  };

  const save = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!form.name.trim()) return;
    setSaving(true);
    try {
      const payload = {
        name: form.name,
        description: form.description || undefined,
        trigger_type: form.trigger_type,
        action_type: form.action_type,
      };
      if (editing) {
        await automationsApi.update(editing.id, payload);
      } else {
        await automationsApi.create(payload);
      }
      setOpen(false);
      setForm(emptyForm);
      setEditing(null);
      await load();
    } catch (err) {
      setError(err instanceof ApiException ? err.message : "Failed to save automation.");
    } finally {
      setSaving(false);
    }
  };

  const toggleEnabled = async (a: Automation) => {
    const next = !a.enabled;
    setAutomations((prev) => prev?.map((x) => (x.id === a.id ? { ...x, enabled: next } : x)) ?? prev);
    try {
      await automationsApi.update(a.id, { enabled: next });
    } catch {
      void load();
    }
  };

  const remove = async (a: Automation) => {
    setAutomations((prev) => prev?.filter((x) => x.id !== a.id) ?? prev);
    try {
      await automationsApi.remove(a.id);
    } catch {
      void load();
    }
  };

  return (
    <AppShell>
      {/* Header — Aurora spec: H1 + MVP pill + subtitle + New flow */}
      <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div className="min-w-0">
          <div className="flex items-center gap-2.5">
            <h1 className="text-2xl font-semibold tracking-[-0.02em] text-content sm:text-[30px]">Automations</h1>
            <Badge tone="warning" className="font-semibold">MVP</Badge>
          </div>
          <p className="mt-1.5 max-w-2xl text-[13.5px] leading-relaxed text-content-muted">
            Trigger-based flows. Live workflows run in n8n — drafts here never execute.
          </p>
        </div>
        <div className="flex w-full flex-wrap items-center gap-2 sm:w-auto sm:justify-end">
          <Button onClick={openCreate}>
            <Plus size={16} /> New flow
          </Button>
        </div>
      </div>

      {/* Live workflows from the connected n8n instance. */}
      <section className="mb-7">
        <div className="mb-3 flex items-center justify-between gap-2">
          <div>
            <h2 className="text-[15px] font-semibold text-content">Your n8n workflows</h2>
            <p className="mt-0.5 text-[12.5px] text-content-muted">Live from your connected n8n — toggle active state or open in n8n.</p>
          </div>
          <Button variant="ghost" size="sm" onClick={loadN8n}>
            <RefreshCw size={14} /> Refresh
          </Button>
        </div>

        {!n8n ? (
          <Loading />
        ) : n8n.status === "online" ? (
          n8n.workflows.length === 0 ? (
            <Card padding="md">
              <p className="text-[13px] text-content-muted">No workflows in n8n yet. Create one in n8n, then Refresh.</p>
            </Card>
          ) : (
            <div className="flex flex-col gap-3.5">
              {n8n.workflows.map((w) => (
                <Card
                  key={w.id}
                  padding="none"
                  hover
                  className={cn("flex flex-wrap items-center gap-4 px-5 py-[18px]", !w.active && "opacity-70")}
                >
                  <span
                    className={cn(
                      "flex h-[42px] w-[42px] shrink-0 items-center justify-center rounded-md",
                      w.active
                        ? "bg-[rgb(var(--color-primary)/0.12)] text-primary-bright"
                        : "bg-content/5 text-content-muted",
                    )}
                  >
                    <Workflow size={20} />
                  </span>
                  <div className="min-w-[200px] flex-1">
                    <p className="truncate text-sm font-semibold text-content" title={w.name}>{w.name}</p>
                    <a
                      href={`${n8n.base_url}/workflow/${w.id}`}
                      target="_blank"
                      rel="noreferrer"
                      className="mt-0.5 inline-flex items-center gap-1.5 text-[12.5px] text-primary-bright hover:underline"
                    >
                      Open in n8n <ExternalLink size={13} />
                    </a>
                  </div>
                  <FlowStatus active={w.active} pausedLabel="Inactive" />
                  <Toggle checked={w.active} onChange={() => toggleWorkflow(w)} label="Activate workflow" />
                </Card>
              ))}
            </div>
          )
        ) : (
          <Card padding="md" className={n8n.status === "not_configured" || n8n.status === "no_api_key" ? "" : "border-warning/30"}>
            <div className="flex items-start gap-3.5">
              <span className="flex h-[42px] w-[42px] shrink-0 items-center justify-center rounded-md bg-warning/12 text-warning">
                <Info size={20} />
              </span>
              <div>
                <p className="text-sm font-semibold text-content">n8n not ready</p>
                <p className="mt-0.5 text-[13px] text-content-muted">{n8n.message}</p>
                <Link href="/dashboard/settings" className="mt-1 inline-block text-[12.5px] text-primary-bright hover:underline">
                  Open Settings → Connected Tools →
                </Link>
              </div>
            </div>
          </Card>
        )}
      </section>

      <h2 className="mb-3 text-[15px] font-semibold text-content">Local drafts</h2>
      <Card className="mb-5 border-warning/20" padding="md">
        <div className="flex items-start gap-3.5">
          <span className="flex h-[42px] w-[42px] shrink-0 items-center justify-center rounded-md bg-warning/12 text-warning">
            <Info size={20} />
          </span>
          <div>
            <p className="text-sm font-semibold text-content">Local draft definitions</p>
            <p className="mt-0.5 text-[13px] text-content-muted">
              These are draft definitions stored in AllHaven — they are <span className="font-medium text-content">not executed</span>.
              Your real, runnable automations live in n8n above.
            </p>
          </div>
        </div>
      </Card>

      {error ? (
        <ErrorState message={error} onRetry={load} />
      ) : !automations ? (
        <Loading />
      ) : automations.length === 0 ? (
        <EmptyState
          title="No flows yet"
          description="Create a draft flow definition to plan your workflows."
          icon={<Workflow size={20} />}
          action={
            <Button onClick={openCreate}>
              <Plus size={16} /> New flow
            </Button>
          }
        />
      ) : (
        <div className="flex flex-col gap-3.5">
          {automations.map((a) => (
            <Card
              key={a.id}
              padding="none"
              hover
              className={cn("flex flex-wrap items-center gap-4 px-5 py-[18px]", !a.enabled && "opacity-70")}
            >
              <span
                className={cn(
                  "flex h-[42px] w-[42px] shrink-0 items-center justify-center rounded-md",
                  a.enabled
                    ? "bg-[rgb(var(--color-primary)/0.12)] text-primary-bright"
                    : "bg-content/5 text-content-muted",
                )}
              >
                <Zap size={20} />
              </span>
              <div className="min-w-[200px] flex-1">
                <p className="text-sm font-semibold text-content">{a.name}</p>
                <p className="mt-0.5 text-[12.5px] text-content-muted">
                  {a.trigger_type || "—"} → {a.action_type || "—"}
                  {a.description ? <span className="text-content-subtle"> · {a.description}</span> : null}
                </p>
              </div>
              <Badge tone="neutral">Draft</Badge>
              <FlowStatus active={a.enabled} activeLabel="Enabled" pausedLabel="Disabled" />
              <Toggle checked={a.enabled} onChange={() => toggleEnabled(a)} label="Enable automation" />
              <div className="flex shrink-0 items-center gap-1.5">
                <Button variant="ghost" size="sm" onClick={() => openEdit(a)}>
                  <Pencil size={14} /> Edit
                </Button>
                <button
                  onClick={() => remove(a)}
                  className="rounded-md p-2 text-content-subtle transition-colors hover:text-danger"
                  aria-label="Delete automation"
                >
                  <Trash2 size={15} />
                </button>
              </div>
            </Card>
          ))}
        </div>
      )}

      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title={editing ? "Edit flow" : "New flow"}
        description="Define a draft flow. Nothing runs automatically in the MVP."
        size="lg"
        footer={
          <>
            <Button variant="ghost" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button form="automation-form" type="submit" loading={saving} disabled={!form.name.trim()}>
              {editing ? "Save changes" : "Create flow"}
            </Button>
          </>
        }
      >
        <form id="automation-form" onSubmit={save} className="space-y-4">
          <Input
            id="name"
            label="Name"
            required
            placeholder="e.g. Daily digest"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
          />
          <Textarea
            id="description"
            label="Description"
            placeholder="What should this flow do?"
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
          />
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <Select
              id="trigger_type"
              label="Trigger type"
              value={form.trigger_type}
              onChange={(e) => setForm({ ...form, trigger_type: e.target.value })}
            >
              {TRIGGER_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </Select>
            <Select
              id="action_type"
              label="Action type"
              value={form.action_type}
              onChange={(e) => setForm({ ...form, action_type: e.target.value })}
            >
              {ACTION_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </Select>
          </div>
        </form>
      </Modal>
    </AppShell>
  );
}
