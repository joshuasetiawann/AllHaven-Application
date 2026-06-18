"use client";

import { useState } from "react";
import type { ReactNode } from "react";
import { Settings2, Wifi } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Toggle } from "@/components/ui/Toggle";
import { ConfigStatusBadge } from "@/components/ui/meta";
import { StatusDot } from "@/components/ui/StatusDot";
import { settingsApi } from "@/lib/api";
import { relativeTime } from "@/lib/format";
import type { Integration } from "@/types";

export function IntegrationCard({
  integration,
  icon,
  onConfigure,
  onChange,
}: {
  integration: Integration;
  icon: ReactNode;
  onConfigure: () => void;
  onChange: (updated: Integration) => void;
}) {
  const [busy, setBusy] = useState(false);
  const id = integration.id ?? integration.key;

  const toggle = async (enabled: boolean) => {
    setBusy(true);
    try {
      onChange(enabled ? await settingsApi.enableIntegration(id) : await settingsApi.disableIntegration(id));
    } finally {
      setBusy(false);
    }
  };

  const test = async () => {
    setBusy(true);
    try {
      onChange(await settingsApi.testIntegration(id));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card hover className="flex h-full flex-col">
      <div className="flex items-start justify-between">
        <span className="flex h-10 w-10 items-center justify-center rounded-lg border border-border bg-surface-input text-primary">
          {icon}
        </span>
        <ConfigStatusBadge status={integration.status} />
      </div>

      <h3 className="mt-3 text-sm font-semibold text-content">{integration.name}</h3>
      <p className="mt-0.5 text-[12.5px] text-content-muted">{integration.purpose}</p>

      <div className="mt-3 flex items-center gap-2 text-[11.5px] text-content-subtle">
        <StatusDot status={integration.status} pulse />
        {integration.detail}
        {integration.last_verified_at ? <span>· verified {relativeTime(integration.last_verified_at)}</span> : null}
      </div>

      <div className="mt-4 flex flex-col gap-3 border-t border-border pt-3 sm:flex-row sm:items-center sm:justify-between">
        {integration.editable === false ? (
          <span className="text-[12px] text-content-subtle">Managed by system</span>
        ) : (
          <div className="flex items-center gap-2">
            <Toggle checked={Boolean(integration.enabled)} onChange={toggle} disabled={busy} label="Enabled" />
            <span className="text-[12px] text-content-muted">{integration.enabled ? "Enabled" : "Disabled"}</span>
          </div>
        )}
        <div className="flex flex-wrap items-center gap-1.5 sm:justify-end">
          {integration.configured ? (
            <Button variant="ghost" size="sm" onClick={test} loading={busy}>
              <Wifi size={14} /> Test
            </Button>
          ) : null}
          {integration.editable === false ? null : (
            <Button variant="subtle" size="sm" onClick={onConfigure}>
              <Settings2 size={14} /> Configure
            </Button>
          )}
        </div>
      </div>
    </Card>
  );
}
