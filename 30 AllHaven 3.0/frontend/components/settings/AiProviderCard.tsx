"use client";

import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { AlertTriangle, Cpu, Globe, Settings2, Wifi } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { Toggle } from "@/components/ui/Toggle";
import { Modal } from "@/components/ui/Modal";
import { Badge } from "@/components/ui/Badge";
import { ConfigStatusBadge } from "@/components/ui/meta";
import { StatusDot } from "@/components/ui/StatusDot";
import { SecretInput } from "@/components/settings/SecretInput";
import { aiApi, ApiException } from "@/lib/api";
import type { AiProvider, ModelSlot } from "@/types";

export function AiProviderCard({
  provider,
  icon,
  onChange,
}: {
  provider: AiProvider;
  icon: ReactNode;
  onChange: (updated: AiProvider) => void;
}) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState<"" | "save" | "test" | "toggle">("");
  const [error, setError] = useState<string | null>(null);

  const [apiKey, setApiKey] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [model, setModel] = useState("");
  const [privacy, setPrivacy] = useState(provider.privacy_mode);

  const hasBaseUrl = provider.fields.some((f) => f.key === "base_url");
  const keyField = provider.fields.find((f) => f.secret);

  useEffect(() => {
    if (open) {
      setApiKey("");
      setBaseUrl(provider.public_config?.base_url ?? "");
      setModel(provider.default_model ?? "");
      setPrivacy(provider.privacy_mode);
      setError(null);
    }
  }, [open, provider]);

  const toggle = async (enabled: boolean) => {
    setBusy("toggle");
    try {
      onChange(enabled ? await aiApi.enableProvider(provider.id) : await aiApi.disableProvider(provider.id));
    } finally {
      setBusy("");
    }
  };

  const save = async (clearKey = false) => {
    setBusy("save");
    setError(null);
    try {
      const secrets: Record<string, string> = {};
      if (keyField) {
        if (clearKey) secrets[keyField.key] = "";
        else if (apiKey) secrets[keyField.key] = apiKey;
      }
      const updated = await aiApi.saveProvider(provider.id, {
        public_config: hasBaseUrl ? { base_url: baseUrl } : {},
        secrets,
        default_model: model || null,
        privacy_mode: privacy,
      });
      onChange(updated);
      setApiKey(""); // never keep the key in component state after saving
    } catch (err) {
      setError(err instanceof ApiException ? err.message : "Save failed.");
    } finally {
      setBusy("");
    }
  };

  const test = async () => {
    setBusy("test");
    setError(null);
    try {
      onChange(await aiApi.testProvider(provider.id));
    } catch (err) {
      setError(err instanceof ApiException ? err.message : "Test failed.");
    } finally {
      setBusy("");
    }
  };

  return (
    <>
      <Card hover className="flex h-full flex-col">
        <div className="flex items-start justify-between">
          <span className="flex h-10 w-10 items-center justify-center rounded-lg border border-border bg-surface-input text-primary">
            {icon}
          </span>
          <ConfigStatusBadge status={provider.status} />
        </div>

        <div className="mt-3 flex items-center gap-2">
          <h3 className="text-sm font-semibold text-content">{provider.name}</h3>
          <Badge tone={provider.external ? "warning" : "success"}>
            {provider.external ? (
              <>
                <Globe size={10} /> External
              </>
            ) : (
              <>
                <Cpu size={10} /> Local
              </>
            )}
          </Badge>
        </div>
        <p className="mt-0.5 text-[12.5px] text-content-muted">{provider.purpose}</p>

        <div className="mt-2 flex items-center gap-2 text-[11.5px] text-content-subtle">
          <StatusDot status={provider.status} pulse />
          {provider.detail}
          {provider.default_model ? <span className="font-mono">· {provider.default_model}</span> : null}
        </div>

        <div className="mt-4 flex flex-col gap-3 border-t border-border pt-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-2">
            <Toggle checked={provider.enabled} onChange={toggle} disabled={busy === "toggle"} label="Enabled" />
            <span className="text-[12px] text-content-muted">{provider.enabled ? "Enabled" : "Disabled"}</span>
          </div>
          <div className="flex flex-wrap items-center gap-1.5 sm:justify-end">
            {provider.configured ? (
              <Button variant="ghost" size="sm" onClick={test} loading={busy === "test"}>
                <Wifi size={14} /> Test
              </Button>
            ) : null}
            <Button variant="subtle" size="sm" onClick={() => setOpen(true)}>
              <Settings2 size={14} /> Configure
            </Button>
          </div>
        </div>
      </Card>

      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title={`Configure ${provider.name}`}
        description={provider.purpose}
        footer={
          <div className="flex w-full flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            {keyField && provider.secrets?.[keyField.key]?.configured ? (
              <Button variant="danger" size="sm" onClick={() => save(true)} loading={busy === "save"}>
                Clear key
              </Button>
            ) : (
              <span />
            )}
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
              <Button variant="ghost" onClick={test} loading={busy === "test"} className="w-full sm:w-auto">
                <Wifi size={15} /> Test
              </Button>
              <Button onClick={() => save(false)} loading={busy === "save"} className="w-full sm:w-auto">
                Save
              </Button>
            </div>
          </div>
        }
      >
        {provider.external ? (
          <p className="mb-4 flex items-start gap-2 rounded-lg border border-warning/30 bg-warning/10 px-3 py-2.5 text-[12.5px] text-warning">
            <AlertTriangle size={15} className="mt-0.5 shrink-0" />
            External AI may process your prompt. Do not send confidential data unless external mode is
            allowed. External providers are disabled globally until AI_ALLOW_EXTERNAL_PROVIDERS=true.
          </p>
        ) : (
          <p className="mb-4 flex items-start gap-2 rounded-lg border border-success/30 bg-success/10 px-3 py-2.5 text-[12.5px] text-success">
            <Cpu size={15} className="mt-0.5 shrink-0" />
            Local AI mode — processing runs on your machine when configured.
          </p>
        )}

        <div className="space-y-4">
          {hasBaseUrl ? (
            <Input
              id="base_url"
              label="Base URL"
              placeholder={provider.fields.find((f) => f.key === "base_url")?.placeholder}
              value={baseUrl}
              onChange={(e) => setBaseUrl(e.target.value)}
            />
          ) : null}
          {keyField ? (
            <SecretInput
              id="api_key"
              label={keyField.label}
              placeholder={keyField.placeholder}
              value={apiKey}
              onChange={setApiKey}
              existing={provider.secrets?.[keyField.key]}
            />
          ) : null}
          <Input
            id="default_model"
            label="Default model"
            placeholder={provider.fields.find((f) => f.key === "default_model")?.placeholder || "model name"}
            value={model}
            onChange={(e) => setModel(e.target.value)}
          />
          <Select label="Privacy mode" value={privacy} onChange={(e) => setPrivacy(e.target.value)}>
            <option value="local_private">Local Private</option>
            <option value="external_allowed">External Allowed</option>
            <option value="manual_provider">Manual Provider</option>
          </Select>
        </div>

        <ModelSlotsSection provider={provider} onChange={onChange} />

        <p className="mt-4 text-[11.5px] leading-relaxed text-content-subtle">
          Keys are encrypted server-side and never returned. <strong className="font-medium text-content-muted">Online status
          requires a successful Test Connection</strong> — a random or unverified key stays Configured or
          becomes Error, never Online.
        </p>
        {error ? <p className="mt-2 text-[12.5px] text-danger">{error}</p> : null}
      </Modal>
    </>
  );
}

// --- Model slots editor ----------------------------------------------------

// Slot 1 follows the provider's default model and only its role is editable here.
// Slot 2 (absent on OpenRouter agents — they are single-slot) gets its own model,
// role, and enabled toggle.
function ModelSlotsSection({
  provider,
  onChange,
}: {
  provider: AiProvider;
  onChange: (updated: AiProvider) => void;
}) {
  const slots = provider.model_slots ?? [];
  const slot1 = slots.find((s) => s.slot === 1);
  const slot2 = slots.find((s) => s.slot === 2);

  const [slot1Role, setSlot1Role] = useState(slot1?.role ?? "");
  const [slot2Model, setSlot2Model] = useState(slot2?.model ?? "");
  const [slot2Role, setSlot2Role] = useState(slot2?.role ?? "");
  const [slot2Enabled, setSlot2Enabled] = useState(slot2?.enabled ?? false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Re-sync the form whenever the provider is updated (e.g. after a save).
  useEffect(() => {
    setSlot1Role(slot1?.role ?? "");
    setSlot2Model(slot2?.model ?? "");
    setSlot2Role(slot2?.role ?? "");
    setSlot2Enabled(slot2?.enabled ?? false);
    setError(null);
  }, [slot1, slot2]);

  if (!slot1) return null;

  const save = async () => {
    setBusy(true);
    setError(null);
    try {
      const payload: Partial<ModelSlot>[] = [{ slot: 1, role: slot1Role }];
      if (slot2) payload.push({ slot: 2, model: slot2Model, role: slot2Role, enabled: slot2Enabled });
      onChange(await aiApi.saveModelSlots(provider.provider_id, payload));
    } catch (err) {
      setError(err instanceof ApiException ? err.message : "Save failed.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mt-5 border-t border-border pt-4">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h4 className="text-[13px] font-semibold text-content">Model slots</h4>
          <p className="mt-0.5 text-[12px] text-content-muted">
            Name the role each model plays in multi-agent chat.
          </p>
        </div>
        <Button variant="ghost" size="sm" onClick={save} loading={busy}>
          Save slots
        </Button>
      </div>

      <div className="mt-3 space-y-3">
        <div className="rounded-lg border border-border bg-surface-input px-3 py-3">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <span className="label-mono">Slot 1</span>
            <span className="font-mono text-[11px] text-content-subtle">
              {slot1.model || provider.default_model || "no model set"}
            </span>
          </div>
          <div className="mt-2.5">
            <Input
              id={`${provider.id}-slot1-role`}
              label="Role"
              placeholder="Main Assistant"
              value={slot1Role}
              onChange={(e) => setSlot1Role(e.target.value)}
            />
          </div>
          <p className="mt-1.5 text-[11.5px] text-content-subtle">
            Slot 1 uses the default model field above.
          </p>
        </div>

        {slot2 ? (
          <div className="rounded-lg border border-border bg-surface-input px-3 py-3">
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex items-center gap-2">
                <span className="label-mono">Slot 2</span>
                <Badge tone={slot2.configured ? "success" : "neutral"}>
                  {slot2.configured ? "Configured" : "Not configured"}
                </Badge>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-[12px] text-content-muted">{slot2Enabled ? "Enabled" : "Disabled"}</span>
                <Toggle checked={slot2Enabled} onChange={setSlot2Enabled} label="Slot 2 enabled" />
              </div>
            </div>
            <div className="mt-2.5 space-y-3">
              <Input
                id={`${provider.id}-slot2-model`}
                label="Model"
                placeholder="model name"
                value={slot2Model}
                onChange={(e) => setSlot2Model(e.target.value)}
              />
              <Input
                id={`${provider.id}-slot2-role`}
                label="Role"
                placeholder="Research / Analysis"
                value={slot2Role}
                onChange={(e) => setSlot2Role(e.target.value)}
              />
            </div>
          </div>
        ) : null}
      </div>

      {slot2 ? (
        <p className="mt-2 text-[11.5px] leading-relaxed text-content-subtle">
          Slot 2 lets one provider run two models — select it in AI Chat as
          “{provider.name} · Slot 2”.
        </p>
      ) : null}
      {error ? <p className="mt-2 text-[12.5px] text-danger">{error}</p> : null}
    </div>
  );
}
