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
import { IntegrationCard } from "@/components/settings/IntegrationCard";
import { IntegrationConfigModal } from "@/components/settings/IntegrationConfigModal";
import { AiProviderCard } from "@/components/settings/AiProviderCard";
import { GoogleOAuthCard } from "@/components/settings/GoogleOAuthCard";
import { aiApi, authApi, settingsApi } from "@/lib/api";
import { getStoredUser } from "@/lib/auth";
import { initials } from "@/lib/format";
import { DEFAULT_PREFS, loadPrefs, savePrefs, type Prefs } from "@/lib/prefs";
import type { Integration, Me } from "@/types";

const INTEGRATION_ICONS: Record<string, LucideIcon> = {
  postgresql: Database,
  ollama: Cpu,
  n8n: Workflow,
  supabase: Cloud,
  google_calendar: Calendar,
  weather_api: CloudSun,
  drive_storage: HardDrive,
  google: Globe,
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
  const [providers, setProviders] = useState<AiProvider[] | null>(null);
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
                </div>
              </Card>

              <GoogleOAuthCard
                google={integrations.find((i) => i.key === "google")}
                onConfigure={() => {
                  const g = integrations.find((i) => i.key === "google");
                  if (g) setConfiguring(g);
                }}
                onChange={updateIntegration}
              />
            </div>
          ) : null}
        </>
      )}

        <p className="mt-4 text-[12px] text-content-subtle">
          Integrations are configured via backend environment variables (see <code className="font-mono">.env.example</code>).
          CoreOS never reports an integration as connected unless it can be verified, and never fakes a connection.
        </p>
      </div>
    </AppShell>
  );
}
