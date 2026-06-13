"use client";

import { useEffect, useState } from "react";
import { Lock, Plug, Trash2, Wifi } from "lucide-react";
import { Modal } from "@/components/ui/Modal";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { ConfigStatusBadge } from "@/components/ui/meta";
import { SecretInput } from "@/components/settings/SecretInput";
import { settingsApi, ApiException } from "@/lib/api";
import type { Integration } from "@/types";

export function IntegrationConfigModal({
  integration,
  open,
  onClose,
  onChange,
}: {
  integration: Integration | null;
  open: boolean;
  onClose: () => void;
  onChange: (updated: Integration) => void;
}) {
  const [publicValues, setPublicValues] = useState<Record<string, string>>({});
  const [secretValues, setSecretValues] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState<"" | "save" | "test" | "clear">("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (integration && open) {
      setPublicValues({ ...(integration.public_config ?? {}) });
      setSecretValues({});
      setError(null);
    }
  }, [integration, open]);

  if (!integration) return null;

  const fields = integration.fields ?? [];

  const run = async (kind: "save" | "test" | "clear") => {
    setBusy(kind);
    setError(null);
    try {
      let updated: Integration;
      if (kind === "save") {
        const secrets = Object.fromEntries(
          Object.entries(secretValues).filter(([, v]) => v !== ""),
        );
        updated = await settingsApi.saveIntegration(integration.id ?? integration.key, publicValues, secrets);
        setSecretValues({}); // never keep secrets in component state after save
      } else if (kind === "test") {
        updated = await settingsApi.testIntegration(integration.id ?? integration.key);
      } else {
        updated = await settingsApi.clearIntegration(integration.id ?? integration.key);
        setPublicValues({ ...(updated.public_config ?? {}) });
        setSecretValues({});
      }
      onChange(updated);
    } catch (err) {
      setError(err instanceof ApiException ? err.message : "Action failed.");
    } finally {
      setBusy("");
    }
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={`Configure ${integration.name}`}
      description={integration.purpose}
      footer={
        <div className="flex w-full flex-wrap items-center justify-between gap-2">
          <Button variant="danger" size="sm" onClick={() => run("clear")} loading={busy === "clear"}>
            <Trash2 size={14} /> Clear
          </Button>
          <div className="flex items-center gap-2">
            <Button variant="ghost" onClick={() => run("test")} loading={busy === "test"}>
              <Wifi size={15} /> Test Connection
            </Button>
            <Button onClick={() => run("save")} loading={busy === "save"}>
              Save
            </Button>
          </div>
        </div>
      }
    >
      <div className="mb-4 flex items-center justify-between rounded-lg border border-border bg-surface-input px-3 py-2.5">
        <span className="flex items-center gap-2 text-[13px] text-content-muted">
          <Plug size={15} /> Current status
        </span>
        <ConfigStatusBadge status={integration.status} />
      </div>

      {integration.last_error && integration.status === "error" ? (
        <p className="mb-4 rounded-md border border-danger/30 bg-danger/10 px-3 py-2 text-[12.5px] text-danger">
          {integration.last_error}
        </p>
      ) : null}

      <div className="space-y-4">
        {fields.map((field) =>
          field.secret ? (
            <SecretInput
              key={field.key}
              id={`f-${field.key}`}
              label={field.label}
              placeholder={field.placeholder}
              value={secretValues[field.key] ?? ""}
              onChange={(v) => setSecretValues((s) => ({ ...s, [field.key]: v }))}
              existing={integration.secrets?.[field.key]}
            />
          ) : (
            <Input
              key={field.key}
              id={`f-${field.key}`}
              label={field.label + (field.required ? " *" : "")}
              placeholder={field.placeholder}
              value={publicValues[field.key] ?? ""}
              onChange={(e) => setPublicValues((s) => ({ ...s, [field.key]: e.target.value }))}
            />
          ),
        )}
      </div>

      {error ? <p className="mt-4 text-[12.5px] text-danger">{error}</p> : null}

      <p className="mt-4 flex items-start gap-1.5 text-[11.5px] leading-relaxed text-content-subtle">
        <Lock size={13} className="mt-0.5 shrink-0" />
        Secrets are sent to the backend and encrypted at rest (local MVP scheme). They are never
        stored in your browser and never shown again — only a masked preview. <strong className="font-medium text-content-muted">Online status requires a successful Test Connection</strong> — saving alone marks it Configured.
      </p>
    </Modal>
  );
}
