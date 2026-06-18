"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  Activity,
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
  Terminal,
} from "lucide-react";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Badge } from "@/components/ui/Badge";
import { Modal } from "@/components/ui/Modal";
import { ErrorState, Loading } from "@/components/ui/States";
import { systemApi, ApiException } from "@/lib/api";
import { cn, relativeTime } from "@/lib/format";
import type {
  PortsApplyResult,
  ServiceState,
  ServiceStatus,
  SystemLogs,
  SystemPorts,
  SystemStatus,
} from "@/types";

const POLL_MS = 10_000;

// Map a service's runtime state to the Aurora dot + mono label recipe.
const STATE_DOT: Record<ServiceState, string> = {
  running: "bg-success shadow-[0_0_10px_2px] shadow-success/60",
  stopped: "bg-content-faint",
  error: "bg-danger shadow-[0_0_10px_2px] shadow-danger/50",
  unavailable: "bg-warning",
  unknown: "bg-warning",
};

const STATE_TEXT: Record<ServiceState, string> = {
  running: "text-success-soft",
  stopped: "text-content-subtle",
  error: "text-danger",
  unavailable: "text-warning",
  unknown: "text-warning",
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
  const [refreshing, setRefreshing] = useState(false);
  // Tracks the in-flight action per service, keyed as `${name}:${action}`.
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [logsFor, setLogsFor] = useState<ServiceStatus | null>(null);

  const loadStatus = useCallback(async () => {
    try {
      setStatus(await systemApi.status());
      setError(null);
    } catch (e) {
      setError(err(e, "Failed to load system status."));
    }
  }, []);

  // Initial load + 10s polling. Cleared on unmount.
  useEffect(() => {
    void loadStatus();
    const id = setInterval(() => void loadStatus(), POLL_MS);
    return () => clearInterval(id);
  }, [loadStatus]);

  const refresh = async () => {
    setRefreshing(true);
    await loadStatus();
    setRefreshing(false);
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

  if (error && !status) return <ErrorState message={error} onRetry={refresh} />;
  if (!status) return <Loading label="Loading system status…" />;

  const agentDown = !status.agent.running;
  const totalServices = status.services.length;
  const runningServices = status.services.filter((s) => s.status === "running").length;
  const stoppedServices = status.services.filter((s) => s.status === "stopped").length;
  const attentionServices = status.services.filter(
    (s) => s.status === "error" || s.status === "unavailable" || s.status === "unknown",
  ).length;

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between gap-3">
        <p className="text-[12.5px] text-content-muted">
          Auto-refreshing every 10s · last update {relativeTime(status.services[0]?.last_checked)}
        </p>
        <Button variant="ghost" size="sm" onClick={refresh} loading={refreshing}>
          <RefreshCw size={14} /> Refresh
        </Button>
      </div>

      {/* Live service metrics, derived from the real status payload. */}
      <div className="grid gap-3.5 sm:grid-cols-3">
        <div className="glass-tile p-[18px]">
          <div className="mb-2.5 flex items-center justify-between">
            <span className="label-mono">Running</span>
            <Activity size={15} className="text-primary-bright" />
          </div>
          <p className="text-[22px] font-semibold leading-none text-content">
            {runningServices}
            <span className="text-sm text-content-subtle"> / {totalServices}</span>
          </p>
          <div className="mt-3 h-[5px] rounded-full bg-white/[0.08]">
            <div
              className="h-[5px] rounded-full bg-[linear-gradient(90deg,rgb(var(--color-primary)),rgb(var(--color-secondary)))]"
              style={{ width: `${totalServices ? Math.round((runningServices / totalServices) * 100) : 0}%` }}
            />
          </div>
        </div>
        <div className="glass-tile p-[18px]">
          <div className="mb-2.5 flex items-center justify-between">
            <span className="label-mono">Stopped</span>
            <Square size={14} className="text-content-subtle" />
          </div>
          <p className="text-[22px] font-semibold leading-none text-content">{stoppedServices}</p>
          <p className={cn("mt-3 text-[11.5px]", attentionServices ? "text-warning" : "text-success-soft")}>
            {attentionServices ? `${attentionServices} need${attentionServices === 1 ? "s" : ""} attention` : "No services need attention"}
          </p>
        </div>
        <div className="glass-tile p-[18px]">
          <div className="mb-2.5 flex items-center justify-between">
            <span className="label-mono">Control agent</span>
            <Terminal size={15} className={status.agent.running ? "text-success-soft" : "text-warning"} />
          </div>
          <p className="text-[22px] font-semibold leading-none text-content">
            {status.agent.running ? "Online" : "Offline"}
          </p>
          <p className={cn("mt-3 truncate text-[11.5px]", status.agent.running ? "text-success-soft" : "text-warning")} title={status.agent.message}>
            {status.agent.running ? "Start / Stop / Restart available" : "Launcher not detected"}
          </p>
        </div>
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
            </div>
          </div>
        </Card>
      ) : null}

      {/* In-flight action error (status is already loaded). */}
      {error ? <ErrorState message={error} onRetry={refresh} /> : null}

      {/* Service control list. */}
      <Card>
        <div className="mb-2 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-[10px] bg-primary/12 text-primary-bright">
              <Terminal size={17} />
            </span>
            <div>
              <h3 className="text-[15px] font-semibold text-content">Service control</h3>
              <p className="text-[12.5px] text-content-muted">Start, stop, restart, and inspect Haven services.</p>
            </div>
          </div>
          <span
            className={cn(
              "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-medium",
              runningServices
                ? "border-success/30 bg-success/10 text-success-soft"
                : "border-border bg-surface-high/70 text-content-muted",
            )}
          >
            <span
              className={cn(
                "h-[5px] w-[5px] rounded-full",
                runningServices ? "animate-pulse-glow bg-success shadow-[0_0_8px] shadow-success" : "bg-content-faint",
              )}
            />
            {runningServices} running
          </span>
        </div>

        <ul>
          {status.services.map((svc) => {
            const controlReason = !status.control_enabled
              ? "System Control is disabled on this deployment."
              : agentDown
                ? "Start the desktop launcher to control services."
                : !svc.controllable
                  ? `${svc.label} can't be controlled from here.`
                  : undefined;

            return (
              <li
                key={svc.name}
                className="flex flex-col gap-2 border-t border-border/70 py-3 sm:flex-row sm:items-center sm:justify-between"
              >
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2.5">
                    <span
                      className={cn(
                        "h-2 w-2 shrink-0 rounded-full",
                        STATE_DOT[svc.status],
                        svc.status === "running" && "animate-pulse-glow",
                      )}
                    />
                    <span
                      className={cn(
                        "text-[13.5px] font-medium",
                        svc.status === "running" ? "text-content" : "text-content-muted",
                      )}
                      title={svc.label}
                    >
                      {svc.label}
                    </span>
                    <Badge tone="neutral">
                      {svc.kind === "docker" ? <Boxes size={10} /> : <Server size={10} />}
                      {svc.kind === "docker" ? "Docker" : "Host"}
                    </Badge>
                    <span className="font-mono text-[10.5px] text-content-subtle">:{svc.port ?? "—"}</span>
                    <span className="font-mono text-[10.5px] text-content-faint">
                      checked {relativeTime(svc.last_checked)}
                    </span>
                  </div>
                  {svc.message ? (
                    <p className="mt-1 pl-[18px] text-[12.5px] text-content-muted">{svc.message}</p>
                  ) : null}
                </div>

                <div className="flex flex-wrap items-center gap-1.5 sm:shrink-0 sm:justify-end">
                  <span className={cn("mr-1 font-mono text-[11px]", STATE_TEXT[svc.status])}>
                    {STATE_LABEL[svc.status].toLowerCase()}
                  </span>
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
                        className={cn(
                          action === "start" &&
                            "border-primary/30 bg-primary/10 font-semibold text-primary-bright hover:border-primary/50 hover:bg-primary/15 hover:text-primary-bright",
                        )}
                      >
                        <Icon size={14} /> {meta.label}
                      </Button>
                    );
                  })}
                  {svc.actions.includes("logs") ? (
                    <Button variant="subtle" size="sm" onClick={() => setLogsFor(svc)}>
                      <FileText size={14} /> Logs
                    </Button>
                  ) : null}
                </div>
              </li>
            );
          })}
        </ul>
      </Card>

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
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-[10px] bg-secondary/12 text-secondary-soft">
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
