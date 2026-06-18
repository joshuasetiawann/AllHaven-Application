"use client";

import { useEffect, useState } from "react";
import {
  Bot,
  Box,
  Boxes,
  Calendar,
  Cloud,
  CloudSun,
  Cpu,
  Database,
  Globe,
  HardDrive,
  Network,
  Plug,
  ShieldCheck,
  Sparkles,
  Workflow,
  Zap,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card, CardHeader } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Avatar } from "@/components/ui/Avatar";
import { Toggle } from "@/components/ui/Toggle";
import { Tabs } from "@/components/ui/Tabs";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { Loading, ErrorState } from "@/components/ui/States";
import { IntegrationCard } from "@/components/settings/IntegrationCard";
import { IntegrationConfigModal } from "@/components/settings/IntegrationConfigModal";
import { AiProviderCard } from "@/components/settings/AiProviderCard";
import { AiToolsPanel } from "@/components/settings/AiToolsPanel";
import { AiChatBehaviorPanel } from "@/components/settings/AiChatBehaviorPanel";
import { GoogleOAuthCard } from "@/components/settings/GoogleOAuthCard";
import SystemControl from "@/components/settings/SystemControl";
import { aiApi, authApi, settingsApi } from "@/lib/api";
import { getStoredUser, setStoredUser } from "@/lib/auth";
import { cn, initials } from "@/lib/format";
import { DEFAULT_PREFS, loadPrefs, savePrefs, type Prefs } from "@/lib/prefs";
import type { AiProvider, EnvSync, Integration, Me } from "@/types";

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

const AI_ICONS: Record<string, LucideIcon> = {
  ollama: Cpu,
  openai: Sparkles,
  anthropic: Bot,
  gemini: Sparkles,
  grok: Zap,
  blackbox: Box,
  openrouter_1: Network,
  openrouter_2: Network,
  openrouter_3: Network,
  openrouter_4: Network,
  openrouter_5: Network,
  openrouter_6: Network,
};

export default function SettingsPage() {
  const user = getStoredUser();
  const [me, setMe] = useState<Me | null>(null);
  const [integrations, setIntegrations] = useState<Integration[] | null>(null);
  const [providers, setProviders] = useState<AiProvider[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState("tools");
  const [prefs, setPrefs] = useState<Prefs>(DEFAULT_PREFS);
  const [configuring, setConfiguring] = useState<Integration | null>(null);
  const [allowExternal, setAllowExternal] = useState(false);
  const [defaultProvider, setDefaultProvider] = useState("ollama");
  const [savingPolicy, setSavingPolicy] = useState(false);
  const [profileForm, setProfileForm] = useState({ full_name: "", workspace_name: "" });
  const [savingProfile, setSavingProfile] = useState(false);
  const [envSync, setEnvSync] = useState<EnvSync | null>(null);

  useEffect(() => setPrefs(loadPrefs()), []);

  // Surface the .env mirror result for a few seconds after any save.
  const flashEnvSync = (sync?: EnvSync | null) => {
    if (!sync) return;
    setEnvSync(sync);
    window.setTimeout(() => setEnvSync(null), 6000);
  };

  const toggleExternal = async (next: boolean) => {
    setAllowExternal(next);
    setSavingPolicy(true);
    try {
      const res = await aiApi.setPolicy({ allow_external: next });
      setAllowExternal(res.allow_external);
      flashEnvSync(res.env_sync);
    } catch {
      setAllowExternal(!next);
    } finally {
      setSavingPolicy(false);
    }
  };

  const changeDefaultProvider = async (id: string) => {
    setDefaultProvider(id);
    try {
      const res = await aiApi.setPolicy({ default_provider: id });
      setDefaultProvider(res.default_provider);
      flashEnvSync(res.env_sync);
    } catch {
      /* keep optimistic */
    }
  };

  const saveProfile = async () => {
    setSavingProfile(true);
    try {
      const updated = await authApi.updateMe({
        full_name: profileForm.full_name,
        workspace_name: profileForm.workspace_name,
      });
      setMe(updated);
      setStoredUser(updated.user);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save profile.");
    } finally {
      setSavingProfile(false);
    }
  };

  const load = async () => {
    setError(null);
    try {
      const [meRes, integrationsRes, providersRes, policyRes] = await Promise.all([
        authApi.me().catch(() => null),
        settingsApi.integrations(),
        aiApi.listProviders(),
        aiApi.getPolicy().catch(() => null),
      ]);
      if (policyRes) {
        setAllowExternal(policyRes.allow_external);
        setDefaultProvider(policyRes.default_provider);
      }
      if (meRes) {
        setProfileForm({
          full_name: meRes.user.full_name ?? "",
          workspace_name: meRes.workspace.name ?? "",
        });
      }
      setMe(meRes);
      setIntegrations(integrationsRes.integrations);
      setProviders(providersRes.providers);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load settings.");
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const updateIntegration = (updated: Integration) => {
    setIntegrations((prev) => prev?.map((i) => (i.key === updated.key ? updated : i)) ?? prev);
    setConfiguring((c) => (c && c.key === updated.key ? updated : c));
    flashEnvSync(updated.env_sync);
  };
  const updateProvider = (updated: AiProvider) => {
    setProviders((prev) => prev?.map((p) => (p.id === updated.id ? updated : p)) ?? prev);
    flashEnvSync(updated.env_sync);
  };

  const updatePref = (patch: Partial<Prefs>) => {
    const next = { ...prefs, ...patch };
    setPrefs(next);
    savePrefs(next);
  };

  return (
    <AppShell>
      <PageHeader
        title="Command Center Settings"
        subtitle="Configure integrations, AI providers, and privacy — credentials are stored securely server-side."
      />

      <Tabs
        className="mb-5"
        value={tab}
        onChange={setTab}
        items={[
          { value: "tools", label: "Connected Tools", count: integrations?.length },
          { value: "ai", label: "AI Providers", count: providers?.length },
          { value: "ai-tools", label: "AI Tools" },
          { value: "ai-chat", label: "AI Chat" },
          { value: "privacy", label: "Privacy & Safety" },
          { value: "system", label: "System Control" },
        ]}
      />

      {envSync ? (
        <div
          className={cn(
            "mb-4 flex items-start gap-2 rounded-lg border px-3 py-2.5 text-[13px]",
            envSync.status === "success"
              ? "border-success/30 bg-success/10 text-success"
              : envSync.status === "failed"
                ? "border-danger/30 bg-danger/10 text-danger"
                : "border-border bg-surface-high text-content-muted",
          )}
        >
          <Plug size={15} className="mt-0.5 shrink-0" />
          <div>
            <p>{envSync.message}</p>
            {envSync.keys.length ? (
              <p className="mt-0.5 font-mono text-[11px] opacity-80">
                .env keys: {envSync.keys.join(", ")}
                {envSync.backup ? ` · backup: ${envSync.backup}` : ""}
              </p>
            ) : null}
          </div>
        </div>
      ) : null}

      {error ? (
        <ErrorState message={error} onRetry={load} />
      ) : !integrations || !providers ? (
        <Loading />
      ) : (
        <>
          {tab === "tools" ? (
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
              {integrations.map((integration) => (
                <IntegrationCard
                  key={integration.key}
                  integration={integration}
                  icon={(() => {
                    const Icon = INTEGRATION_ICONS[integration.key] ?? Plug;
                    return <Icon size={18} />;
                  })()}
                  onConfigure={() => setConfiguring(integration)}
                  onChange={updateIntegration}
                />
              ))}
            </div>
          ) : null}

          {tab === "ai" ? (
            <>
              <Card className="mb-4 border-primary/20">
                <div className="grid gap-4 lg:grid-cols-2">
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex items-start gap-3">
                      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-warning/10 text-warning">
                        <Globe size={18} />
                      </span>
                      <div>
                        <p className="text-sm font-semibold text-content">Allow external AI providers</p>
                        <p className="mt-0.5 text-[13px] text-content-muted">
                          Enable to chat with GPT, Claude, Gemini, Grok, Blackbox, OpenRouter. Off =
                          local-only (Ollama).
                        </p>
                      </div>
                    </div>
                    <Toggle
                      checked={allowExternal}
                      onChange={toggleExternal}
                      disabled={savingPolicy}
                      label="Allow external AI providers"
                    />
                  </div>
                  <div className="sm:max-w-xs">
                    <Select
                      label="Default AI provider"
                      value={defaultProvider}
                      onChange={(e) => changeDefaultProvider(e.target.value)}
                    >
                      {providers.map((p) => (
                        <option key={p.id} value={p.id}>
                          {p.name}
                          {p.external ? " · external" : " · local"}
                        </option>
                      ))}
                    </Select>
                    <p className="mt-1.5 text-[12px] text-content-subtle">
                      Used in AI Chat when no provider is selected.
                    </p>
                  </div>
                </div>
              </Card>
              <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
                {providers.map((provider) => (
                  <AiProviderCard
                    key={provider.id}
                    provider={provider}
                    icon={(() => {
                      const Icon = AI_ICONS[provider.id] ?? Bot;
                      return <Icon size={18} />;
                    })()}
                    onChange={updateProvider}
                  />
                ))}
              </div>
            </>
          ) : null}

          {tab === "ai-tools" ? <AiToolsPanel /> : null}

          {tab === "ai-chat" ? <AiChatBehaviorPanel /> : null}

          {tab === "privacy" ? (
            <div className="grid gap-5 lg:grid-cols-3">
              <Card className="lg:col-span-1">
                <CardHeader title="Profile" subtitle="Edit your name and workspace." />
                <div className="mb-4 flex items-center gap-3">
                  <Avatar initials={initials(profileForm.full_name || me?.user.full_name || user?.email)} />
                  <Badge tone="primary">Owner Access</Badge>
                </div>
                <div className="space-y-3">
                  <Input
                    id="full_name"
                    label="Full name"
                    placeholder="Your name"
                    value={profileForm.full_name}
                    onChange={(e) => setProfileForm({ ...profileForm, full_name: e.target.value })}
                  />
                  <Input
                    id="workspace_name"
                    label="Workspace name"
                    placeholder="My Workspace"
                    value={profileForm.workspace_name}
                    onChange={(e) => setProfileForm({ ...profileForm, workspace_name: e.target.value })}
                  />
                  <div>
                    <p className="label-mono">Primary email</p>
                    <p className="mt-1 truncate text-[13px] text-content-muted">
                      {me?.user.email || user?.email || "—"}
                    </p>
                  </div>
                  <Button onClick={saveProfile} loading={savingProfile} className="w-full">
                    Save profile
                  </Button>
                </div>
              </Card>

              <Card className="lg:col-span-2">
                <CardHeader title="Appearance" subtitle="Device-local UI preferences." />
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
                </ul>
              </Card>

              <Card className="lg:col-span-3 border-primary/15">
                <div className="flex items-start gap-3">
                  <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
                    <ShieldCheck size={20} />
                  </span>
                  <div>
                    <p className="text-sm font-semibold text-content">AI privacy &amp; safety</p>
                    <ul className="mt-2 space-y-1.5 text-[13px] text-content-muted">
                      <li className="flex items-center gap-2"><Cpu size={14} className="text-success" /> Default privacy mode: <span className="text-content">Local Private</span></li>
                      <li className="flex items-center gap-2"><Boxes size={14} className="text-primary" /> AI suggestions require approval. Human approval required for write actions.</li>
                      <li className="flex items-center gap-2"><Globe size={14} className="text-warning" /> Confidential data is never sent to external providers unless you allow external mode.</li>
                    </ul>

                    <div className="mt-4 flex items-center justify-between rounded-lg border border-border bg-surface-input px-3 py-3">
                      <div className="pr-3">
                        <p className="text-sm text-content">Allow external AI providers</p>
                        <p className="text-[12.5px] text-content-muted">
                          Lets you chat with GPT, Claude, Gemini, Grok, Blackbox, and OpenRouter.
                          Keep off for local-only (Ollama) privacy.
                        </p>
                      </div>
                      <Toggle
                        checked={allowExternal}
                        onChange={toggleExternal}
                        disabled={savingPolicy}
                        label="Allow external AI providers"
                      />
                    </div>
                    {allowExternal ? (
                      <p className="mt-2 flex items-start gap-1.5 text-[12px] text-warning">
                        <Globe size={13} className="mt-0.5 shrink-0" />
                        External AI is ON. Avoid sending confidential data to external providers.
                      </p>
                    ) : null}
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

          {tab === "system" ? <SystemControl /> : null}
        </>
      )}

      <IntegrationConfigModal
        integration={configuring}
        open={Boolean(configuring)}
        onClose={() => setConfiguring(null)}
        onChange={updateIntegration}
      />
    </AppShell>
  );
}
