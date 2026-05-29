"use client";

import { useEffect, useState } from "react";
import { Plug, RefreshCw } from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { Card, CardHeader } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { StatusDot } from "@/components/ui/StatusDot";
import { Button } from "@/components/ui/Button";
import { Loading, ErrorState } from "@/components/ui/States";
import { settingsApi } from "@/lib/api";
import type { Integration } from "@/types";

function statusTone(integration: Integration) {
  switch (integration.status) {
    case "connected":
      return "success" as const;
    case "configured":
      return "primary" as const;
    case "error":
      return "danger" as const;
    default:
      return "neutral" as const;
  }
}

export default function SettingsPage() {
  const [integrations, setIntegrations] = useState<Integration[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setError(null);
    try {
      const result = await settingsApi.integrations();
      setIntegrations(result.integrations);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load integrations.");
    }
  };

  useEffect(() => {
    void load();
  }, []);

  return (
    <AppShell title="Settings" subtitle="Integration status — honest, never faked">
      <div className="mx-auto max-w-3xl space-y-6">
        <Card>
          <CardHeader
            title="Integrations"
            subtitle="Status is derived from environment configuration. Secret values are never exposed."
            icon={<Plug size={18} />}
            action={
              <Button variant="ghost" size="sm" onClick={load}>
                <RefreshCw size={14} /> Refresh
              </Button>
            }
          />

          {error ? (
            <ErrorState message={error} onRetry={load} />
          ) : !integrations ? (
            <Loading />
          ) : (
            <ul className="divide-y divide-border">
              {integrations.map((integration) => (
                <li key={integration.key} className="flex items-center justify-between gap-4 py-3.5">
                  <div className="flex items-center gap-3">
                    <StatusDot status={integration.status} pulse />
                    <div>
                      <p className="text-sm font-medium text-content">{integration.name}</p>
                      <p className="text-[12px] text-content-muted">{integration.detail}</p>
                    </div>
                  </div>
                  <Badge tone={statusTone(integration)}>
                    {integration.configured ? integration.status : "Not configured"}
                  </Badge>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card>
          <CardHeader title="How to configure" subtitle="Local MVP setup" />
          <div className="space-y-2 text-[13px] leading-relaxed text-content-muted">
            <p>
              Integrations are enabled by setting the matching environment variables in your backend{" "}
              <code className="rounded bg-surface-input px-1.5 py-0.5 font-mono text-[12px] text-content">
                .env
              </code>{" "}
              file (see{" "}
              <code className="rounded bg-surface-input px-1.5 py-0.5 font-mono text-[12px] text-content">
                .env.example
              </code>
              ). For example, set{" "}
              <code className="rounded bg-surface-input px-1.5 py-0.5 font-mono text-[12px] text-content">
                OLLAMA_BASE_URL
              </code>{" "}
              to enable local AI.
            </p>
            <p className="text-content-subtle">
              CoreOS never reports an integration as connected unless it can be verified, and it
              never fakes a successful connection.
            </p>
          </div>
        </Card>
      </div>
    </AppShell>
  );
}
