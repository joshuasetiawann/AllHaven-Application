"use client";

import { useEffect, useState } from "react";
import {
  Bot,
  Calendar,
  CloudSun,
  Database,
  Plug,
  RefreshCw,
  Workflow,
  Cloud,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card, CardHeader } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Avatar } from "@/components/ui/Avatar";
import { Toggle } from "@/components/ui/Toggle";
import { Button } from "@/components/ui/Button";
import { StatusDot } from "@/components/ui/StatusDot";
import { Loading, ErrorState } from "@/components/ui/States";
import { authApi, settingsApi } from "@/lib/api";
import { getStoredUser } from "@/lib/auth";
import { initials } from "@/lib/format";
import { DEFAULT_PREFS, loadPrefs, savePrefs, type Prefs } from "@/lib/prefs";
import type { Integration, Me } from "@/types";

const TOOL_META: Record<string, { icon: LucideIcon; desc: string; envHint: string }> = {
  postgresql: { icon: Database, desc: "Primary relational database", envHint: "DATABASE_URL" },
  ollama: { icon: Bot, desc: "Local LLM orchestration & inference", envHint: "OLLAMA_BASE_URL" },
  n8n: { icon: Workflow, desc: "Workflow automation & webhooks", envHint: "N8N_BASE_URL" },
  supabase: { icon: Cloud, desc: "Authentication & real-time sync", envHint: "SUPABASE_URL" },
  google_calendar: { icon: Calendar, desc: "Task & event synchronization", envHint: "GOOGLE_CALENDAR_CLIENT_ID" },
  weather: { icon: CloudSun, desc: "Local weather data feed", envHint: "WEATHER_API_KEY" },
};

function toolBadge(integration: Integration) {
  if (integration.status === "connected") return <Badge tone="success" dot>Connected</Badge>;
  if (integration.configured) return <Badge tone="primary" dot>Configured</Badge>;
  return <Badge tone="neutral" dot>Not configured</Badge>;
}

export default function SettingsPage() {
  const user = getStoredUser();
  const [me, setMe] = useState<Me | null>(null);
  const [integrations, setIntegrations] = useState<Integration[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [prefs, setPrefs] = useState<Prefs>(DEFAULT_PREFS);

  useEffect(() => {
    setPrefs(loadPrefs());
  }, []);

  const load = async () => {
    setError(null);
    try {
      const [meRes, integrationsRes] = await Promise.all([
        authApi.me().catch(() => null),
        settingsApi.integrations(),
      ]);
      setMe(meRes);
      setIntegrations(integrationsRes.integrations);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load settings.");
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const updatePref = (patch: Partial<Prefs>) => {
    const next = { ...prefs, ...patch };
    setPrefs(next);
    savePrefs(next);
  };

  return (
    <AppShell>
      <PageHeader
        title="Command Center Settings"
        subtitle="Manage your workspace, preferences, and third-party node integrations."
        actions={
          <Button variant="ghost" size="sm" onClick={load}>
            <RefreshCw size={14} /> Refresh
          </Button>
        }
      />

      <div className="grid gap-5 lg:grid-cols-3">
        {/* Profile */}
        <Card className="lg:col-span-1">
          <CardHeader title="Profile" />
          <div className="flex items-center gap-3">
            <Avatar initials={initials(me?.user.full_name || user?.full_name || user?.email)} />
            <div className="min-w-0">
              <p className="truncate text-sm font-medium text-content">
                {me?.user.full_name || user?.full_name || "Operator"}
              </p>
              <Badge tone="primary" className="mt-1">Owner Access</Badge>
            </div>
          </div>
          <dl className="mt-5 space-y-3 text-[13px]">
            <div>
              <dt className="label-mono">Workspace</dt>
              <dd className="mt-1 truncate text-content">{me?.workspace.name ?? "—"}</dd>
            </div>
            <div>
              <dt className="label-mono">Primary email</dt>
              <dd className="mt-1 truncate text-content">{me?.user.email || user?.email || "—"}</dd>
            </div>
          </dl>
        </Card>

        {/* Preferences */}
        <Card className="lg:col-span-2">
          <CardHeader title="Preferences" subtitle="Device-local UI preferences." />
          <ul className="divide-y divide-border">
            <li className="flex items-center justify-between py-3.5">
              <div>
                <p className="text-sm text-content">Glassmorphism</p>
                <p className="text-[12.5px] text-content-muted">Translucent, blurred panels.</p>
              </div>
              <Toggle checked={prefs.glass} onChange={(v) => updatePref({ glass: v })} label="Glassmorphism" />
            </li>
            <li className="flex items-center justify-between py-3.5">
              <div>
                <p className="text-sm text-content">Compact density</p>
                <p className="text-[12.5px] text-content-muted">Tighter spacing for more on screen.</p>
              </div>
              <Toggle checked={prefs.compact} onChange={(v) => updatePref({ compact: v })} label="Compact density" />
            </li>
            <li className="flex items-center justify-between py-3.5 opacity-70">
              <div>
                <p className="text-sm text-content">Automatic cloud backups</p>
                <p className="text-[12.5px] text-content-muted">Not available in the local MVP.</p>
              </div>
              <Toggle checked={false} onChange={() => {}} disabled label="Automatic backups" />
            </li>
          </ul>
        </Card>
      </div>

      {/* Connected tools */}
      <div className="mt-6">
        <div className="mb-4 flex items-center gap-2">
          <Plug size={18} className="text-primary" />
          <h2 className="text-[15px] font-semibold text-content">Connected Tools</h2>
        </div>

        {error ? (
          <ErrorState message={error} onRetry={load} />
        ) : !integrations ? (
          <Loading />
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {integrations.map((integration) => {
              const meta = TOOL_META[integration.key] ?? { icon: Plug, desc: "", envHint: "" };
              const Icon = meta.icon;
              return (
                <Card key={integration.key} hover className="flex flex-col">
                  <div className="flex items-start justify-between">
                    <span className="flex h-10 w-10 items-center justify-center rounded-lg border border-border bg-surface-input text-primary">
                      <Icon size={18} />
                    </span>
                    {toolBadge(integration)}
                  </div>
                  <h3 className="mt-3 text-sm font-semibold text-content">{integration.name}</h3>
                  <p className="mt-0.5 text-[12.5px] text-content-muted">{meta.desc}</p>
                  <div className="mt-4 flex items-center justify-between border-t border-border pt-3">
                    <span className="flex items-center gap-2 text-[12px] text-content-subtle">
                      <StatusDot status={integration.status} pulse /> {integration.detail}
                    </span>
                    {!integration.configured && meta.envHint ? (
                      <code className="rounded bg-surface-input px-1.5 py-0.5 font-mono text-[11px] text-content-muted">
                        {meta.envHint}
                      </code>
                    ) : null}
                  </div>
                </Card>
              );
            })}
          </div>
        )}

        <p className="mt-4 text-[12px] text-content-subtle">
          Integrations are configured via backend environment variables (see <code className="font-mono">.env.example</code>).
          CoreOS never reports an integration as connected unless it can be verified, and never fakes a connection.
        </p>
      </div>
    </AppShell>
  );
}
