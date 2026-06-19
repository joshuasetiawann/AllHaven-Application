"use client";

import { useCallback, useEffect, useState } from "react";
import {
  CheckCircle2,
  Globe,
  Link2,
  Loader2,
  RotateCcw,
  Server,
  ShieldAlert,
  XCircle,
} from "lucide-react";
import { Card, CardHeader } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import {
  getApiBaseUrl,
  getApiBaseUrlSource,
  getBackendOverride,
  type BackendUrlSource,
} from "@/lib/backendUrl";
import { testBackendConnection, type BackendTestResult } from "@/lib/connection";
import { BACKEND_CHANGED_EVENT, getConnectionMode, setConnectionMode } from "@/lib/connectionMode";

// Honest status model (see CLAUDE.md status_truth_model). "online" is set ONLY by
// a real /health success — never inferred from a non-empty URL. Saving a URL makes
// it "configured" (active), and the immediate follow-up test reflects reality.
type Status = "unknown" | "configured" | "online" | "ignored" | "error" | "unavailable" | "not_configured";

const STATUS_BADGE: Record<Status, { tone: "neutral" | "primary" | "success" | "warning" | "danger"; label: string }> = {
  unknown: { tone: "neutral", label: "Not tested" },
  configured: { tone: "primary", label: "Configured" },
  online: { tone: "success", label: "Online" },
  ignored: { tone: "warning", label: "Saved, not active here" },
  error: { tone: "danger", label: "Error" },
  unavailable: { tone: "warning", label: "Unreachable" },
  not_configured: { tone: "neutral", label: "Not configured" },
};

const SOURCE_LABEL: Record<BackendUrlSource, string> = {
  override: "Saved on this device",
  env: "Built-in default (from the app build)",
  derived: "Same host as this page :8000",
  fallback: "localhost fallback",
};

/**
 * Backend Bridge configuration card. Lets the user point the app at the desktop
 * backend over Tailscale (the only way to reach it from mobile, where localhost
 * is the phone). Real Test Connection against GET /api/v1/health; honest status;
 * the previous working URL is kept if a new one fails. Renders fully client-side,
 * so it stays usable even when the backend is unreachable.
 */
export function BackendBridgeCard({ onConnected }: { onConnected?: () => void }) {
  const [activeUrl, setActiveUrl] = useState("");
  const [source, setSource] = useState<BackendUrlSource>("fallback");
  const [draft, setDraft] = useState("");
  const [hasOverride, setHasOverride] = useState(false);
  const [status, setStatus] = useState<Status>("unknown");
  const [result, setResult] = useState<BackendTestResult | null>(null);
  const [testing, setTesting] = useState(false);
  const [saving, setSaving] = useState(false);
  const [lastCheckedAt, setLastCheckedAt] = useState<string | null>(null);

  const overrideIgnoredHere = () => Boolean(getBackendOverride()) && getApiBaseUrlSource() !== "override";

  const syncActiveState = useCallback((clearTransient = false) => {
    const override = getBackendOverride();
    const activeSource = getApiBaseUrlSource();
    setActiveUrl(getApiBaseUrl());
    setSource(activeSource);
    setHasOverride(Boolean(override));
    setDraft(override);
    setStatus(override ? (activeSource === "override" ? "configured" : "ignored") : "unknown");
    if (clearTransient) {
      setResult(null);
      setLastCheckedAt(null);
    }
  }, []);

  // Read the current resolution on mount and whenever the topbar switcher changes it.
  useEffect(() => {
    syncActiveState();
    const onBackendChanged = () => syncActiveState(true);
    window.addEventListener(BACKEND_CHANGED_EVENT, onBackendChanged);
    return () => window.removeEventListener(BACKEND_CHANGED_EVENT, onBackendChanged);
  }, [syncActiveState]);

  const refreshActive = () => syncActiveState();

  const applyResult = (r: BackendTestResult) => {
    setResult(r);
    setStatus(overrideIgnoredHere() ? "ignored" : r.status);
    setLastCheckedAt(new Date().toLocaleTimeString());
    if (r.ok && !overrideIgnoredHere()) onConnected?.();
  };

  // Test WITHOUT saving — probe exactly what's typed (or the active URL if blank).
  const handleTest = async () => {
    setTesting(true);
    try {
      const r = await testBackendConnection(draft.trim() ? draft : undefined);
      applyResult(r);
    } finally {
      setTesting(false);
    }
  };

  // Save the typed URL as the active backend, then immediately test it for an
  // honest status. If the test fails we keep the saved value (the user asked for
  // it) but the status badge tells the truth.
  const handleSave = async () => {
    setSaving(true);
    try {
      const targetMode = getConnectionMode() === "funnel" ? "funnel" : "private";
      setConnectionMode(targetMode, draft);
      const normalized = getBackendOverride();
      refreshActive();
      setStatus(normalized ? (overrideIgnoredHere() ? "ignored" : "configured") : "unknown");
      if (normalized) {
        const r = await testBackendConnection(normalized);
        applyResult(r);
      } else {
        setResult(null);
      }
    } finally {
      setSaving(false);
    }
  };

  // Drop the override → fall back to the built-in/derived default.
  const handleReset = () => {
    setConnectionMode("local");
    setDraft("");
    refreshActive();
    setStatus("unknown");
    setResult(null);
    setLastCheckedAt(null);
  };

  const badge = STATUS_BADGE[status];
  const busy = testing || saving;

  return (
    <Card className="mb-5" padding="lg">
      <CardHeader
        title={
          <span className="flex items-center gap-2">
            <Server size={16} className="text-primary" /> Backend Bridge
          </span>
        }
        subtitle="Where this device reaches the AllHaven backend. On mobile, localhost is the phone — point this at your desktop over Tailscale."
      />

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <Badge tone={badge.tone} dot>
          {badge.label}
        </Badge>
        <span className="text-[12px] text-content-subtle">{SOURCE_LABEL[source]}</span>
        {lastCheckedAt ? (
          <span className="text-[12px] text-content-subtle">· checked {lastCheckedAt}</span>
        ) : null}
      </div>

      {hasOverride && source !== "override" ? (
        <div className="mt-3 rounded-xl border border-warning/30 bg-warning/10 px-3 py-2 text-[12.5px] leading-relaxed text-warning">
          The saved Tailscale URL is not the active backend in this desktop browser. Desktop web uses a same-site backend for cookie login; the mobile APK will use the saved URL.
        </div>
      ) : null}

      <div className="mt-2 flex items-center gap-1.5 rounded-lg border border-border bg-surface-input/50 px-3 py-2 text-[12.5px]">
        <Link2 size={13} className="shrink-0 text-content-subtle" />
        <span className="truncate font-mono text-content-muted" title={activeUrl}>
          {activeUrl || "—"}
        </span>
      </div>

      <div className="mt-4 space-y-3">
        <Input
          id="backend_bridge_url"
          label="Backend URL"
          inputMode="url"
          autoCapitalize="none"
          autoCorrect="off"
          spellCheck={false}
          placeholder="http://100.x.y.z:8000  or  https://desktop.tailnet.ts.net"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          hint="Use a Tailscale IP, MagicDNS name, or Tailscale Serve URL. We add /api/v1 for you. Plain http://localhost only works on the desktop itself."
        />

        <div className="flex flex-col gap-2 sm:flex-row">
          <Button onClick={handleTest} loading={testing} disabled={busy} variant="ghost" className="sm:w-auto">
            {!testing ? <CheckCircle2 size={15} /> : null} Test Connection
          </Button>
          <Button onClick={handleSave} loading={saving} disabled={busy || !draft.trim()} className="sm:w-auto">
            Save &amp; Use
          </Button>
          {hasOverride ? (
            <Button onClick={handleReset} disabled={busy} variant="subtle" className="sm:w-auto">
              <RotateCcw size={15} /> Reset to default
            </Button>
          ) : null}
        </div>

        {result ? (
          <div
            className={
              "flex items-start gap-2 rounded-lg border px-3 py-2.5 text-[12.5px] " +
              (result.ok
                ? "border-success/30 bg-success/10 text-success"
                : result.status === "unavailable"
                  ? "border-warning/30 bg-warning/10 text-warning"
                  : "border-danger/30 bg-danger/10 text-danger")
            }
          >
            {result.ok ? (
              <CheckCircle2 size={15} className="mt-0.5 shrink-0" />
            ) : (
              <XCircle size={15} className="mt-0.5 shrink-0" />
            )}
            <div className="min-w-0">
              <p>{result.message}</p>
              {result.ok && result.appVersion ? (
                <p className="mt-0.5 font-mono text-[11px] opacity-80">
                  AllHaven {result.appVersion}
                  {result.deploymentProfile ? ` · ${result.deploymentProfile}` : ""}
                </p>
              ) : null}
            </div>
          </div>
        ) : null}
      </div>

      <div className="mt-4 rounded-xl border border-border bg-surface-input/40 p-3 text-[12px] text-content-muted">
        <p className="flex items-center gap-1.5 font-medium text-content">
          <Globe size={13} className="text-primary" /> Connect from mobile
        </p>
        <ol className="mt-1.5 list-decimal space-y-0.5 pl-5">
          <li>Install Tailscale on the desktop and this phone (same tailnet).</li>
          <li>
            On the desktop, run the backend with <span className="font-mono text-content">--host 0.0.0.0 --port 8000</span>.
          </li>
          <li>Find the desktop&apos;s Tailscale IP (100.x.y.z) or MagicDNS host, paste it above, then Test.</li>
        </ol>
        <p className="mt-2 flex items-start gap-1.5 text-[11.5px] text-content-subtle">
          <ShieldAlert size={13} className="mt-0.5 shrink-0 text-warning" />
          The URL is stored locally on this device (no secrets). Prefer Tailscale Serve (HTTPS) so traffic is
          encrypted; never expose the backend with public Funnel by default.
        </p>
      </div>
    </Card>
  );
}
