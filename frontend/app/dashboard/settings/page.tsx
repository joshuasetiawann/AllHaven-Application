"use client";

import { useEffect, useState } from "react";
import {
  Bot,
  Box,
  Boxes,
  Calendar,
  Cloud,
  Cpu,
  Database,
  Globe,
  HardDrive,
  Languages,
  Network,
  Palette,
  Plug,
  ShieldCheck,
  Sparkles,
  SunMoon,
  Workflow,
  Zap,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card, CardHeader } from "@/components/ui/Card";
import { DesktopBridgePanel } from "@/components/settings/DesktopBridgePanel";
import { BackendBridgeCard } from "@/components/settings/BackendBridgeCard";
import { APP_VERSION } from "@/components/layout/nav";
import { SetupRequiredState } from "@/components/SetupRequiredState";
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
import {
  ACCENT_OPTIONS,
  DEFAULT_PREFS,
  LANGUAGE_OPTIONS,
  THEME_OPTIONS,
  loadPrefs,
  savePrefs,
  type Prefs,
} from "@/lib/prefs";
import type { AiProvider, EnvSync, Integration, Me } from "@/types";

const INTEGRATION_ICONS: Record<string, LucideIcon> = {
  postgresql: Database,
  ollama: Cpu,
  n8n: Workflow,
  supabase: Cloud,
  google_calendar: Calendar,
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
  cursor: Bot,
  deepseek: Boxes,
  qwen: Sparkles,
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
  // First load attempt finished (success OR degraded). The page renders its tabs once
  // this is true; backend-dependent tabs show a per-tab connect-state if their data is
  // null, so a down Backend Bridge never blanks the whole Settings page.
  const [loaded, setLoaded] = useState(false);
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
    // Each call degrades to null on its own instead of one failure rejecting the whole
    // batch — so a down Backend Bridge leaves Appearance (device-local) and the
    // reconnect card usable rather than blanking the page (Promise.all → allSettled-ish).
    const [meRes, integrationsRes, providersRes, policyRes] = await Promise.all([
      authApi.me().catch(() => null),
      settingsApi.integrations().catch(() => null),
      aiApi.listProviders().catch(() => null),
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
    setIntegrations(integrationsRes?.integrations ?? null);
    setProviders(providersRes?.providers ?? null);
    setLoaded(true);
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

  const configuredAi = providers?.filter((p) => p.configured).length ?? 0;
  const onlineAi = providers?.filter((p) => p.status === "online").length ?? 0;
  const enabledAi = providers?.filter((p) => p.enabled).length ?? 0;
  const selectableSlots = providers?.reduce(
    (count, provider) => count + (provider.model_slots ?? []).filter((slot) => slot.configured && slot.enabled).length,
    0,
  ) ?? 0;
  const directAiProviders = providers?.filter((p) => !p.id.startsWith("openrouter_")) ?? [];
  const openRouterProviders = providers?.filter((p) => p.id.startsWith("openrouter_")) ?? [];

  // For a backend-only tab whose data is null: a small inline spinner WHILE the first
  // load is still running, then an honest connect-state. Never a full-page block — so
  // Settings (and Appearance, which is device-local) open instantly even with no
  // backend / no Tailscale.
  const backendTabFallback = (feature: string, reason: string) =>
    loaded ? (
      <SetupRequiredState feature={feature} needs="backend" reason={reason} onRetry={load} />
    ) : (
      <Loading />
    );

  return (
    <AppShell>
      <PageHeader
        title="Command Center Settings"
        subtitle="Configure integrations, AI providers, and privacy — credentials are stored securely server-side."
        actions={<Badge tone="secondary">AllHaven {APP_VERSION}</Badge>}
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
        <div className="mb-4">
          <ErrorState message={error} onRetry={() => { setError(null); void load(); }} />
        </div>
      ) : null}

      <div key={tab} className="animate-fade-in">
          {tab === "tools" ? (
            <>
              <BackendBridgeCard onConnected={load} />
              <DesktopBridgePanel />
              {integrations ? (
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
              ) : (
                backendTabFallback(
                  "Connected Tools",
                  "Integrations live on the backend (secrets stay server-side). Connect via the Backend Bridge above to configure them — Appearance settings work without it.",
                )
              )}
            </>
          ) : null}

          {tab === "ai" ? (
            providers ? (
            <>
              <div className="mb-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                <Card className="py-3">
                  <p className="label-mono">Configured</p>
                  <p className="mt-1 text-2xl font-semibold text-content">{configuredAi}/{providers.length}</p>
                </Card>
                <Card className="py-3">
                  <p className="label-mono">Online</p>
                  <p className="mt-1 text-2xl font-semibold text-success">{onlineAi}</p>
                </Card>
                <Card className="py-3">
                  <p className="label-mono">Enabled</p>
                  <p className="mt-1 text-2xl font-semibold text-primary">{enabledAi}</p>
                </Card>
                <Card className="py-3">
                  <p className="label-mono">Selectable slots</p>
                  <p className="mt-1 text-2xl font-semibold text-content">{selectableSlots}</p>
                </Card>
              </div>

              <Card className="mb-5 border-primary/20">
                <div className="grid gap-5 xl:grid-cols-[minmax(0,1.25fr)_minmax(280px,0.75fr)]">
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                    <div className="flex items-start gap-3">
                      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-warning/10 text-warning">
                        <Globe size={18} />
                      </span>
                      <div>
                        <p className="text-sm font-semibold text-content">Allow external AI providers</p>
                        <p className="mt-0.5 text-[13px] text-content-muted">
                          Enable GPT, Claude, Gemini, Cursor, DeepSeek, Qwen, Grok, Blackbox, and OpenRouter.
                          Off keeps chat local-only through Ollama.
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

              <section className="mb-6">
                <div className="mb-3 flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
                  <div>
                    <p className="text-sm font-semibold text-content">Direct model agents</p>
                    <p className="text-[13px] text-content-muted">
                      GPT 1/2, Gemini 1/2, Cursor 1/2, DeepSeek, Qwen, and local Ollama are grouped here for faster setup.
                    </p>
                  </div>
                  <Badge tone="primary">{directAiProviders.length} providers</Badge>
                </div>
                <div className="grid gap-4 sm:grid-cols-2 2xl:grid-cols-3">
                  {directAiProviders.map((provider) => (
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
              </section>

              <section>
                <div className="mb-3 flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
                  <div>
                    <p className="text-sm font-semibold text-content">OpenRouter model agents</p>
                    <p className="text-[13px] text-content-muted">
                      Six independent OpenRouter agents, each with its own key and default model.
                    </p>
                  </div>
                  <Badge tone="neutral">{openRouterProviders.length} agents</Badge>
                </div>
                <div className="grid gap-4 sm:grid-cols-2 2xl:grid-cols-3">
                  {openRouterProviders.map((provider) => (
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
              </section>
            </>
            ) : (
              <>
                <BackendBridgeCard onConnected={load} />
                {backendTabFallback(
                  "AI Providers",
                  "AI-provider configuration lives on the backend. Connect via the Backend Bridge to manage providers — Appearance settings work without it.",
                )}
              </>
            )
          ) : null}

          {/* These panels self-fetch and self-degrade: each renders a per-panel
              SetupRequiredState when the backend is unreachable (and short-circuits
              instantly on mobile), so they're rendered directly and never gated on the
              page's global `loaded` flag — a down backend can't blank the Settings page. */}
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
                <CardHeader title="Appearance" subtitle="Device-local language, theme, and color preferences." />
                <div className="grid gap-3 sm:grid-cols-2">
                  <Select
                    id="app_language"
                    label="Language"
                    value={prefs.language}
                    onChange={(e) => updatePref({ language: e.target.value as Prefs["language"] })}
                  >
                    {LANGUAGE_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>{option.label}</option>
                    ))}
                  </Select>
                  <Select
                    id="app_theme"
                    label="Theme"
                    value={prefs.theme}
                    onChange={(e) => updatePref({ theme: e.target.value as Prefs["theme"] })}
                  >
                    {THEME_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>{option.label}</option>
                    ))}
                  </Select>
                </div>

                <div className="mt-4 rounded-xl border border-border bg-surface-input/45 p-3">
                  <div className="mb-2 flex items-start gap-2">
                    <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-border bg-surface text-primary">
                      <Palette size={15} />
                    </span>
                    <div>
                      <p className="text-sm font-medium text-content">Color nuance</p>
                      <p className="text-[12.5px] text-content-muted">Pick the accent mood for buttons, active states, and highlights.</p>
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                    {ACCENT_OPTIONS.map((option) => {
                      const active = prefs.accent === option.value;
                      return (
                        <button
                          key={option.value}
                          type="button"
                          onClick={() => updatePref({ accent: option.value })}
                          className={cn(
                            "flex items-center gap-2 rounded-lg border px-2.5 py-2 text-left text-[13px] transition-colors focus-ring",
                            active ? "border-primary/50 bg-primary/10 text-content" : "border-border bg-surface hover:border-border-strong text-content-muted hover:text-content",
                          )}
                        >
                          <span className="h-4 w-4 rounded-full border border-black/10" style={{ backgroundColor: option.swatch }} />
                          <span>{option.label}</span>
                        </button>
                      );
                    })}
                  </div>
                </div>

                <div className="mt-4 grid gap-2 text-[12.5px] text-content-muted sm:grid-cols-2">
                  <div className="flex items-start gap-2 rounded-lg border border-border bg-surface-input px-3 py-2">
                    <Languages size={14} className="mt-0.5 text-primary" />
                    <span>{LANGUAGE_OPTIONS.find((o) => o.value === prefs.language)?.helper}</span>
                  </div>
                  <div className="flex items-start gap-2 rounded-lg border border-border bg-surface-input px-3 py-2">
                    <SunMoon size={14} className="mt-0.5 text-primary" />
                    <span>{THEME_OPTIONS.find((o) => o.value === prefs.theme)?.helper}</span>
                  </div>
                </div>

                <ul className="mt-4 divide-y divide-border">
                  <li className="flex items-center justify-between gap-3 py-3.5">
                    <div>
                      <p className="text-sm text-content">Glassmorphism</p>
                      <p className="text-[12.5px] text-content-muted">Translucent, blurred panels.</p>
                    </div>
                    <Toggle checked={prefs.glass} onChange={(v) => updatePref({ glass: v })} label="Glassmorphism" />
                  </li>
                  <li className="flex items-center justify-between gap-3 py-3.5">
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

                    <div className="mt-4 flex flex-col gap-3 rounded-lg border border-border bg-surface-input px-3 py-3 sm:flex-row sm:items-center sm:justify-between">
                      <div className="sm:pr-3">
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
                google={integrations?.find((i) => i.key === "google")}
                onConfigure={() => {
                  const g = integrations?.find((i) => i.key === "google");
                  if (g) setConfiguring(g);
                }}
                onChange={updateIntegration}
              />
            </div>
          ) : null}

          {/* SystemControl self-fetches and self-degrades (per-panel SetupRequiredState
              when unreachable, instant short-circuit on mobile), so it's rendered
              directly and not gated on the page's global `loaded` flag. */}
          {tab === "system" ? <SystemControl /> : null}
      </div>

      <IntegrationConfigModal
        integration={configuring}
        open={Boolean(configuring)}
        onClose={() => setConfiguring(null)}
        onChange={updateIntegration}
      />
    </AppShell>
  );
}
