"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  AlertTriangle,
  Boxes,
  Check,
  Copy,
  FileText,
  Info,
  Play,
  RefreshCw,
  RotateCw,
  Server,
  Square,
} from "lucide-react";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Badge } from "@/components/ui/Badge";
import { Modal } from "@/components/ui/Modal";
import { ErrorState, Loading } from "@/components/ui/States";
import { SetupRequiredState } from "@/components/SetupRequiredState";
import { systemApi, ApiException } from "@/lib/api";
import { isBackendUnreachable } from "@/lib/connection";
import { BEARER_MODE } from "@/lib/mobileAuth";
import { getApiBaseUrlSource } from "@/lib/backendUrl";
import { relativeTime } from "@/lib/format";
import type {
  PortsApplyResult,
  ServiceState,
  ServiceStatus,
  SystemLogs,
  SystemPorts,
  SystemStatus,
} from "@/types";

const POLL_MS = 10_000;

// Map a service's runtime state to a Badge tone.
const STATE_TONE: Record<ServiceState, "success" | "neutral" | "danger" | "warning"> = {
  running: "success",
  stopped: "neutral",
  error: "danger",
  unavailable: "warning",
  unknown: "warning",
};

const STATE_LABEL: Record<ServiceState, string> = {
  running: "Running",
  stopped: "Stopped",
  error: "Error",
  unavailable: "Unavailable",
  unknown: "Unknown",
};

// A control action and the icon/label that represents it.
const ACTION_META: Record<string, { label: string; icon: typeof Play }> = {
  start: { label: "Start", icon: Play },
  stop: { label: "Stop", icon: Square },
  restart: { label: "Restart", icon: RotateCw },
};

function err(e: unknown, fallback: string): string {
  return e instanceof ApiException ? e.message : e instanceof Error ? e.message : fallback;
}

export default function SystemControl() {
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  // Backend unreachable → render an honest connect-state instead of an endless spinner.
  const [needsBackend, setNeedsBackend] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  // Tracks the in-flight action per service, keyed as `${name}:${action}`.
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [startingAgent, setStartingAgent] = useState(false);
  const [logsFor, setLogsFor] = useState<ServiceStatus | null>(null);

  // Returns true when the status load SUCCEEDED — the caller uses this to decide
  // whether to start the 10s poll (don't hammer an unreachable backend).
  const loadStatus = useCallback(async (): Promise<boolean> => {
    // Mobile (bearer build) with no usable backend override: short-circuit to the
    // connect-state without firing a doomed request. Desktop/web never enters here.
    if (BEARER_MODE && getApiBaseUrlSource() === "fallback") {
      setNeedsBackend(true);
      return false;
    }
    try {
      setStatus(await systemApi.status());
      setError(null);
      setNeedsBackend(false);
      return true;
    } catch (e) {
      if (isBackendUnreachable(e)) {
        setNeedsBackend(true);
        return false;
      }
      setError(err(e, "Failed to load system status."));
      return false;
    }
  }, []);

  // Initial load, then start the 10s poll ONLY if that first load succeeded — a
  // down/unreachable backend gets no interval. Cleared on unmount.
  useEffect(() => {
    let id: ReturnType<typeof setInterval> | null = null;
    void loadStatus().then((ok) => {
      if (ok) id = setInterval(() => void loadStatus(), POLL_MS);
    });
    return () => {
      if (id) clearInterval(id);
    };
  }, [loadStatus]);

  const refresh = async () => {
    setRefreshing(true);
    await loadStatus();
    setRefreshing(false);
  };

  const startAgent = async () => {
    setStartingAgent(true);
    setError(null);
    try {
      await systemApi.startAgent();
      await loadStatus();
    } catch (e) {
      setError(err(e, "Failed to start the control agent."));
    } finally {
      setStartingAgent(false);
    }
  };

  const runAction = async (svc: ServiceStatus, action: string) => {
    setBusyAction(`${svc.name}:${action}`);
    setError(null);
    try {
      const updated = await systemApi.action(svc.name, action);
      // Reflect the immediate result, then re-sync the full status.
      setStatus((prev) =>
        prev ? { ...prev, services: prev.services.map((s) => (s.name === updated.name ? updated : s)) } : prev,
      );
      await loadStatus();
    } catch (e) {
      setError(err(e, `Failed to ${action} ${svc.label}.`));
    } finally {
      setBusyAction(null);
    }
  };

  if (needsBackend) {
    return (
      <SetupRequiredState
        feature="System Control"
        needs="backend"
        reason="System Control manages services on your desktop computer through the AllHaven backend. Connect to it (locally, or over Tailscale from mobile) to view and control services."
        onRetry={refresh}
      />
    );
  }
  if (error && !status) return <ErrorState message={error} onRetry={refresh} />;
  if (!status) return <Loading label="Loading system status…" />;

  const agentDown = !status.agent.running;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-3">
        <p className="text-[12.5px] text-content-muted">
          Auto-refreshing every 10s · last update {relativeTime(status.services[0]?.last_checked)}
        </p>
        <Button variant="ghost" size="sm" onClick={refresh} loading={refreshing}>
          <RefreshCw size={14} /> Refresh
        </Button>
      </div>

      {/* Honest deployment-state banners. */}
      {!status.control_enabled ? (
        <Card padding="md" className="border-info/30">
          <div className="flex items-start gap-3">
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-info/12 text-info">
              <Info size={18} />
            </span>
            <div>
              <p className="text-sm font-semibold text-content">System Control is disabled on this deployment.</p>
              <p className="mt-0.5 text-[13px] text-content-muted">
                Service controls are turned off here. Status and logs may still be available below.
              </p>
            </div>
          </div>
        </Card>
      ) : null}

      {agentDown ? (
        <Card padding="md" className="border-warning/30">
          <div className="flex items-start gap-3">
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-warning/12 text-warning">
              <AlertTriangle size={18} />
            </span>
            <div>
              <p className="text-sm font-semibold text-content">Control agent not running</p>
              <p className="mt-0.5 text-[13px] text-content-muted">{status.agent.message}</p>
              <p className="mt-1 text-[12.5px] text-content-subtle">
                Start / Stop / Restart need the desktop launcher running. Status and logs still work without it.
              </p>
              {/* The agent is a desktop-local process. Offer to start it only on desktop
                  (and only when control is enabled). On mobile, explain instead of teasing
                  a button that controls a machine the phone can't reach. */}
              {BEARER_MODE ? (
                <p className="mt-2 text-[12.5px] text-content-subtle">
                  System Control mengatur proses di komputer desktop — hanya tersedia di aplikasi desktop.
                </p>
              ) : status.control_enabled ? (
                <Button
                  variant="ghost"
                  size="sm"
                  className="mt-3"
                  loading={startingAgent}
                  onClick={startAgent}
                >
                  <Play size={14} /> Start control agent
                </Button>
              ) : null}
            </div>
          </div>
        </Card>
      ) : null}

      {/* In-flight action error (status is already loaded). */}
      {error ? <ErrorState message={error} onRetry={refresh} /> : null}

      {/* Service cards. */}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {status.services.map((svc) => {
          const controlReason = !status.control_enabled
            ? "System Control is disabled on this deployment."
            : agentDown
              ? "Start the desktop launcher to control services."
              : !svc.controllable
                ? `${svc.label} can't be controlled from here.`
                : undefined;

          return (
            <Card key={svc.name} hover className="flex h-full flex-col">
              <div className="flex items-start justify-between gap-2">
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-border bg-surface-input text-primary">
                  {svc.kind === "docker" ? <Boxes size={18} /> : <Server size={18} />}
                </span>
                <Badge tone={STATE_TONE[svc.status]} dot>
                  {STATE_LABEL[svc.status]}
                </Badge>
              </div>

              <div className="mt-3 flex items-center gap-2">
                <h3 className="truncate text-sm font-semibold text-content" title={svc.label}>
                  {svc.label}
                </h3>
                <Badge tone="neutral">{svc.kind === "docker" ? "Docker" : "Host"}</Badge>
              </div>

              <div className="mt-2 flex items-center gap-2 text-[11.5px] text-content-subtle">
                <span className="font-mono">Port {svc.port ?? "—"}</span>
                <span>·</span>
                <span>checked {relativeTime(svc.last_checked)}</span>
              </div>

              {svc.message ? (
                <p className="mt-2 text-[12.5px] text-content-muted">{svc.message}</p>
              ) : null}

              <div className="mt-auto flex flex-wrap items-center gap-1.5 border-t border-border pt-3">
                {(["start", "stop", "restart"] as const).map((action) => {
                  if (!svc.actions.includes(action)) return null;
                  const meta = ACTION_META[action];
                  const Icon = meta.icon;
                  const disabled = !svc.controllable || !!busyAction;
                  return (
                    <Button
                      key={action}
                      variant="ghost"
                      size="sm"
                      disabled={disabled}
                      loading={busyAction === `${svc.name}:${action}`}
                      title={!svc.controllable ? controlReason : undefined}
                      onClick={() => runAction(svc, action)}
                    >
                      <Icon size={14} /> {meta.label}
                    </Button>
                  );
                })}
                {svc.actions.includes("logs") ? (
                  <Button variant="subtle" size="sm" className="ml-auto" onClick={() => setLogsFor(svc)}>
                    <FileText size={14} /> Logs
                  </Button>
                ) : null}
              </div>
            </Card>
          );
        })}
      </div>

      <PortsEditor />

      {logsFor ? <LogsModal service={logsFor} onClose={() => setLogsFor(null)} /> : null}
    </div>
  );
}

// --- Ports editor ---------------------------------------------------------

function PortsEditor() {
  const [ports, setPorts] = useState<SystemPorts | null>(null);
  const [values, setValues] = useState<Record<string, string>>({});
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saving, setSaving] = useState<"" | "save" | "restart">("");
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<PortsApplyResult | null>(null);

  const load = useCallback(async () => {
    setLoadError(null);
    try {
      const data = await systemApi.getPorts();
      setPorts(data);
      setValues(Object.fromEntries(Object.entries(data.ports).map(([k, v]) => [k, String(v)])));
    } catch (e) {
      setLoadError(err(e, "Failed to load ports."));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  // Validate every field: integer 1–65535, no duplicates. Returns parsed map or an error string.
  const validate = (): { parsed: Record<string, number> } | { message: string } => {
    const parsed: Record<string, number> = {};
    const seen = new Map<number, string>();
    for (const key of Object.keys(values)) {
      const raw = values[key].trim();
      if (!/^\d+$/.test(raw)) return { message: `${key}: enter a whole number.` };
      const num = Number(raw);
      if (num < 1 || num > 65535) return { message: `${key}: port must be between 1 and 65535.` };
      const dupe = seen.get(num);
      if (dupe) return { message: `Duplicate port ${num} for ${dupe} and ${key}.` };
      seen.set(num, key);
      parsed[key] = num;
    }
    return { parsed };
  };

  const save = async (restart: boolean) => {
    const check = validate();
    if ("message" in check) {
      setError(check.message);
      setResult(null);
      return;
    }
    setSaving(restart ? "restart" : "save");
    setError(null);
    setResult(null);
    try {
      const res = await systemApi.savePorts(check.parsed, restart);
      setResult(res);
      setValues(Object.fromEntries(Object.entries(res.ports).map(([k, v]) => [k, String(v)])));
      setPorts((prev) => (prev ? { ...prev, ports: res.ports } : prev));
    } catch (e) {
      setError(err(e, "Failed to save ports."));
    } finally {
      setSaving("");
    }
  };

  if (loadError) {
    return (
      <Card padding="md">
        <ErrorState message={loadError} onRetry={load} />
      </Card>
    );
  }
  if (!ports) {
    return (
      <Card padding="md">
        <Loading label="Loading ports…" />
      </Card>
    );
  }

  const keys = Object.keys(ports.ports);
  const busy = saving !== "";

  return (
    <Card padding="md">
      <div className="mb-1 flex items-center gap-2.5">
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-border bg-surface-input text-primary">
          <Server size={16} />
        </span>
        <div>
          <h3 className="text-[14px] font-semibold text-content">Service ports</h3>
          <p className="text-[12.5px] text-content-muted">Configure the ports Haven services bind to.</p>
        </div>
      </div>

      <p className="mb-4 flex items-start gap-2 rounded-lg border border-warning/30 bg-warning/10 px-3 py-2.5 text-[12.5px] text-warning">
        <AlertTriangle size={15} className="mt-0.5 shrink-0" />
        Port changes require a service restart.
      </p>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {keys.map((key) => (
          <Input
            key={key}
            id={`port-${key}`}
            label={key}
            type="number"
            inputMode="numeric"
            min={1}
            max={65535}
            disabled={!ports.editable || busy}
            placeholder={ports.defaults[key] != null ? String(ports.defaults[key]) : undefined}
            value={values[key] ?? ""}
            onChange={(e) => setValues((prev) => ({ ...prev, [key]: e.target.value }))}
          />
        ))}
      </div>

      {!ports.editable ? (
        <p className="mt-4 text-[12.5px] text-content-subtle">Ports are read-only on this deployment.</p>
      ) : null}

      {error ? <p className="mt-4 text-[12.5px] text-danger">{error}</p> : null}
      {result ? (
        <p
          className={`mt-4 text-[12.5px] ${result.applied ? "text-success" : "text-content-muted"}`}
        >
          {result.message}
          {result.restart_required && !result.applied ? " A service restart is required to apply changes." : ""}
        </p>
      ) : null}

      <div className="mt-4 flex flex-wrap items-center justify-end gap-2 border-t border-border pt-4">
        <Button
          variant="ghost"
          disabled={!ports.editable || busy}
          loading={saving === "save"}
          onClick={() => save(false)}
        >
          <Check size={15} /> Save
        </Button>
        <Button
          disabled={!ports.editable || busy}
          loading={saving === "restart"}
          onClick={() => save(true)}
        >
          <RotateCw size={15} /> Save &amp; Restart Services
        </Button>
      </div>
    </Card>
  );
}

// --- Logs modal -----------------------------------------------------------

function LogsModal({ service, onClose }: { service: ServiceStatus; onClose: () => void }) {
  const [logs, setLogs] = useState<SystemLogs | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState(false);
  const copyTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setLogs(await systemApi.logs(service.name));
    } catch (e) {
      setError(err(e, "Failed to load logs."));
    } finally {
      setLoading(false);
    }
  }, [service.name]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    return () => {
      if (copyTimer.current) clearTimeout(copyTimer.current);
    };
  }, []);

  const copy = async () => {
    if (!logs?.content) return;
    try {
      await navigator.clipboard.writeText(logs.content);
      setCopied(true);
      if (copyTimer.current) clearTimeout(copyTimer.current);
      copyTimer.current = setTimeout(() => setCopied(false), 1500);
    } catch {
      /* Clipboard can be blocked (e.g. insecure context); ignore. */
    }
  };

  return (
    <Modal
      open
      onClose={onClose}
      title={`${service.label} logs`}
      description={service.kind === "docker" ? "Docker container output" : "Host process output"}
      size="lg"
      footer={
        <div className="flex w-full items-center justify-between gap-2">
          <span className="text-[11.5px] text-content-subtle">Secrets are masked.</span>
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="sm" onClick={load} loading={loading}>
              <RefreshCw size={14} /> Refresh
            </Button>
            <Button variant="subtle" size="sm" onClick={copy} disabled={!logs?.content}>
              {copied ? <Check size={14} /> : <Copy size={14} />} {copied ? "Copied" : "Copy"}
            </Button>
          </div>
        </div>
      }
    >
      {error ? (
        <ErrorState message={error} onRetry={load} />
      ) : !logs ? (
        <Loading label="Loading logs…" />
      ) : (
        <>
          {logs.message ? <p className="mb-2 text-[12.5px] text-content-muted">{logs.message}</p> : null}
          {logs.truncated ? (
            <p className="mb-2 text-[11.5px] text-content-subtle">Output truncated to the most recent lines.</p>
          ) : null}
          <pre className="custom-scrollbar max-h-[55vh] overflow-auto rounded-lg border border-border bg-surface-input p-3 font-mono text-[11.5px] leading-relaxed text-content-muted">
            {logs.content || "No log output."}
          </pre>
        </>
      )}
    </Modal>
  );
}
