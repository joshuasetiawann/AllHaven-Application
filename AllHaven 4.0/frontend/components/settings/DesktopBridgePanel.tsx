"use client";

import { useEffect, useState } from "react";
import { Cpu, Workflow, Globe, ShieldCheck, ShieldAlert, Smartphone } from "lucide-react";
import { Card, CardHeader } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { API_BASE_URL } from "@/lib/api";

const PROFILE_LABEL: Record<string, string> = {
  private: "Private / Personal",
  client_portal: "Client Portal / Hosted",
  public_demo: "Public Demo",
};

// Services that live on the desktop and need the bridge to be reached from mobile.
const NEEDS_BRIDGE = [
  { icon: Cpu, name: "Ollama (local AI)", detail: "GET /api/tags on the resolved endpoint" },
  { icon: Workflow, name: "n8n (automation)", detail: "reachable n8n server in your tailnet" },
];
// Services that work without the bridge (cloud/API or Supabase-direct).
const NO_BRIDGE = [
  "API AI providers (OpenAI, Claude, Gemini, Grok, DeepSeek, Qwen, OpenRouter…)",
  "Supabase data (Tasks, Notes, Finance, Routines, Approvals, Memory)",
  "Auth / register / login",
];

export function DesktopBridgePanel() {
  const [profile, setProfile] = useState<string>("private");

  useEffect(() => {
    // Best-effort: /health is public and returns the deployment profile.
    fetch(`${API_BASE_URL}/health`)
      .then((r) => (r.ok ? r.json() : null))
      .then((j) => {
        const p = j?.data?.deployment_profile;
        if (p) setProfile(p);
      })
      .catch(() => {});
  }, []);

  return (
    <Card className="mb-5" padding="lg">
      <CardHeader
        title="Desktop Bridge & Deployment"
        subtitle="How mobile reaches desktop-local services (Ollama, n8n). API providers and Supabase data don't need it."
      />
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <span className="text-[12.5px] text-content-muted">Deployment mode:</span>
        <Badge tone="primary">{PROFILE_LABEL[profile] ?? profile}</Badge>
      </div>

      <div className="mt-4 grid gap-4 sm:grid-cols-2">
        <div className="rounded-xl border border-warning/35 bg-warning/5 p-3.5">
          <p className="flex items-center gap-1.5 text-[13px] font-semibold text-content">
            <ShieldAlert size={15} className="text-warning" /> Needs Desktop Bridge on mobile
          </p>
          <ul className="mt-2 space-y-2">
            {NEEDS_BRIDGE.map((s) => (
              <li key={s.name} className="flex items-start gap-2 text-[12.5px] text-content-muted">
                <s.icon size={14} className="mt-0.5 shrink-0 text-content-subtle" />
                <span><span className="text-content">{s.name}</span> — online only when the resolved endpoint responds ({s.detail}).</span>
              </li>
            ))}
          </ul>
          <p className="mt-2 text-[11.5px] text-content-subtle">
            On the desktop itself, Local mode (localhost) works directly.
          </p>
        </div>

        <div className="rounded-xl border border-success/30 bg-success/5 p-3.5">
          <p className="flex items-center gap-1.5 text-[13px] font-semibold text-content">
            <ShieldCheck size={15} className="text-success" /> Works without the bridge
          </p>
          <ul className="mt-2 space-y-1.5">
            {NO_BRIDGE.map((s) => (
              <li key={s} className="text-[12.5px] text-content-muted">• {s}</li>
            ))}
          </ul>
        </div>
      </div>

      <div className="mt-4 rounded-xl border border-border bg-surface-input/40 p-3.5">
        <p className="flex items-center gap-1.5 text-[13px] font-semibold text-content">
          <Smartphone size={15} className="text-primary" /> Connect from mobile (Private mode)
        </p>
        <ol className="mt-2 list-decimal space-y-1 pl-5 text-[12.5px] text-content-muted">
          <li>Install Tailscale on the desktop and the phone; sign both into the same tailnet.</li>
          <li>Find the desktop&apos;s Tailscale IP (100.x.y.z) or MagicDNS host.</li>
          <li>In the Ollama / n8n cards below, set <span className="text-content">Connection mode → Tailscale Private</span> and paste that URL.</li>
          <li>Tap <span className="text-content">Test Connection</span> — it&apos;s online only if the endpoint actually responds.</li>
        </ol>
        <p className="mt-2.5 flex items-start gap-1.5 text-[11.5px] text-content-subtle">
          <Globe size={13} className="mt-0.5 shrink-0 text-danger" />
          Tailscale Funnel (public internet) is <strong className="text-danger">off by default</strong>. Enable it
          only for a temporary demo, only through the authenticated AllHaven app — never expose raw Ollama/n8n.
        </p>
      </div>
    </Card>
  );
}
