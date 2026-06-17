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
import type { AiProvider } from "@/types";

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
      if (clearKey) setApiKey("");
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

        <div className="mt-4 flex items-center justify-between border-t border-border pt-3">
          <div className="flex items-center gap-2">
            <Toggle checked={provider.enabled} onChange={toggle} disabled={busy === "toggle"} label="Enabled" />
            <span className="text-[12px] text-content-muted">{provider.enabled ? "Enabled" : "Disabled"}</span>
          </div>
          <div className="flex items-center gap-1.5">
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
          <div className="flex w-full items-center justify-between gap-2">
            {keyField && provider.secrets?.[keyField.key]?.configured ? (
              <Button variant="danger" size="sm" onClick={() => save(true)} loading={busy === "save"}>
                Clear key
              </Button>
            ) : (
              <span />
            )}
            <div className="flex items-center gap-2">
              <Button variant="ghost" onClick={test} loading={busy === "test"}>
                <Wifi size={15} /> Test
              </Button>
              <Button onClick={() => save(false)} loading={busy === "save"}>
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

        {error ? <p className="mt-4 text-[12.5px] text-danger">{error}</p> : null}
      </Modal>
    </>
  );
}
