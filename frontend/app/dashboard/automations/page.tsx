"use client";

import { useEffect, useState } from "react";
import { Info, Pencil, Plus, Trash2, Workflow, Zap } from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { PageHeader } from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { Textarea } from "@/components/ui/Textarea";
import { Select } from "@/components/ui/Select";
import { Badge } from "@/components/ui/Badge";
import { Toggle } from "@/components/ui/Toggle";
import { Modal } from "@/components/ui/Modal";
import { EmptyState, ErrorState, Loading } from "@/components/ui/States";
import { automationsApi, ApiException } from "@/lib/api";
import type { Automation } from "@/types";

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

export default function AutomationsPage() {
  const [automations, setAutomations] = useState<Automation[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [editing, setEditing] = useState<Automation | null>(null);
  const [form, setForm] = useState<AutomationForm>(emptyForm);

  const load = async () => {
    setError(null);
    try {
      setAutomations(await automationsApi.list());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load automations.");
    }
  };

  useEffect(() => {
    void load();
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
      <PageHeader
        title="Automations"
        subtitle="Draft workflow definitions for your workspace."
        actions={
          <Button onClick={openCreate}>
            <Plus size={16} /> New automation
          </Button>
        }
      />

      <Card className="mb-5 border-warning/20" padding="md">
        <div className="flex items-start gap-3">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-warning/12 text-warning">
            <Info size={18} />
          </span>
          <div>
            <p className="text-sm font-semibold text-content">Saved drafts only</p>
            <p className="mt-0.5 text-[13px] text-content-muted">
              CoreOS does not execute automations in the MVP — these are saved drafts. n8n connection
              status is shown in Settings → Connected Tools.
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
          title="No automations yet"
          description="Create a draft automation definition to plan your workflows."
          icon={<Workflow size={20} />}
          action={
            <Button onClick={openCreate}>
              <Plus size={16} /> New automation
            </Button>
          }
        />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {automations.map((a) => (
            <Card key={a.id} hover>
              <div className="flex items-start justify-between">
                <span className="flex h-10 w-10 items-center justify-center rounded-lg border border-border bg-surface-input text-primary">
                  <Zap size={18} />
                </span>
                <Toggle
                  checked={a.enabled}
                  onChange={() => toggleEnabled(a)}
                  label="Enable automation"
                />
              </div>
              <h3 className="mt-3 text-sm font-semibold text-content">{a.name}</h3>
              {a.description ? (
                <p className="mt-1 line-clamp-2 text-[12.5px] text-content-muted">{a.description}</p>
              ) : null}
              <div className="mt-3 flex flex-wrap gap-1.5">
                <Badge tone="neutral">Trigger: {a.trigger_type || "—"}</Badge>
                <Badge tone="neutral">Action: {a.action_type || "—"}</Badge>
                <Badge tone={a.enabled ? "success" : "neutral"}>
                  {a.enabled ? "Enabled" : "Disabled"}
                </Badge>
              </div>
              <div className="mt-4 flex items-center justify-end gap-1.5 border-t border-border pt-3">
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
        title={editing ? "Edit automation" : "New automation"}
        description="Define a draft automation. Nothing runs automatically in the MVP."
        size="lg"
        footer={
          <>
            <Button variant="ghost" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button form="automation-form" type="submit" loading={saving} disabled={!form.name.trim()}>
              {editing ? "Save changes" : "Create automation"}
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
            placeholder="What should this automation do?"
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
