"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Check, Server } from "lucide-react";
import { IconButton } from "@/components/ui/IconButton";
import { pingBackend, testBackendConnection, type BackendTestResult } from "@/lib/connection";
import {
  BACKEND_CHANGED_EVENT,
  getApiBaseUrl,
  getConnectionMode,
  getRememberedTailscaleUrl,
  setConnectionMode,
  type ConnectionMode,
} from "@/lib/connectionMode";
import { cn } from "@/lib/format";

type LiveStatus = "checking" | "online" | "offline";

const MODE_LABEL: Record<ConnectionMode, string> = {
  auto: "Auto",
  localhost: "Localhost",
  tailscale: "Tailscale",
};

const MODES: { id: ConnectionMode; label: string; hint: string }[] = [
  { id: "auto", label: "Auto", hint: "Same origin as this app (env → derived → localhost)." },
  { id: "localhost", label: "Localhost", hint: "Desktop dev — the backend on this machine." },
  { id: "tailscale", label: "Tailscale", hint: "Reach your desktop backend over Tailscale." },
];

export function ConnectionModeSwitcher() {
  const [open, setOpen] = useState(false);
  const [mode, setMode] = useState<ConnectionMode>("auto");
  const [status, setStatus] = useState<LiveStatus>("checking");
  const [activeUrl, setActiveUrl] = useState("");
  // Tailscale inline editor state (only meaningful when the tailscale row is chosen).
  const [tsUrl, setTsUrl] = useState("");
  const [tsEditing, setTsEditing] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<BackendTestResult | null>(null);
  const ref = useRef<HTMLDivElement>(null);

  // Read the active mode/URL and re-check reachability. Re-runs on demand and
  // whenever the backend override changes anywhere in the app.
  const refresh = useCallback(() => {
    setMode(getConnectionMode());
    setActiveUrl(getApiBaseUrl());
    setStatus("checking");
    let cancelled = false;
    pingBackend(3500).then((ok) => {
      if (!cancelled) setStatus(ok ? "online" : "offline");
    });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    const cancel = refresh();
    const onChanged = () => refresh();
    window.addEventListener(BACKEND_CHANGED_EVENT, onChanged);
    return () => {
      cancel?.();
      window.removeEventListener(BACKEND_CHANGED_EVENT, onChanged);
    };
  }, [refresh]);

  // Close on outside click (mirrors the notifications popover in Topbar).
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  // Seed the Tailscale editor when the popover opens.
  useEffect(() => {
    if (open) {
      setTsUrl(getRememberedTailscaleUrl());
      setTsEditing(getConnectionMode() === "tailscale");
      setTestResult(null);
    }
  }, [open]);

  const choose = (next: ConnectionMode) => {
    if (next === "tailscale") {
      // Reveal the inline URL editor instead of applying immediately.
      setTsEditing(true);
      setTestResult(null);
      return;
    }
    setConnectionMode(next); // dispatches the change event → refresh() runs
    setOpen(false);
  };

  const runTest = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      setTestResult(await testBackendConnection(tsUrl));
    } finally {
      setTesting(false);
    }
  };

  const saveTailscale = () => {
    setConnectionMode("tailscale", tsUrl); // dispatches the change event → refresh() runs
    setOpen(false);
  };

  const statusLabel = status === "checking" ? "Checking" : status === "online" ? "Online" : "Offline";

  return (
    <div className="relative" ref={ref}>
      {/* Trigger: a compact pill that matches the AI status pill on lg+, and an
          icon-only button (with a status dot) on small screens. */}
      <button
        type="button"
        aria-label={`Connection: ${MODE_LABEL[mode]} · ${statusLabel}`}
        onClick={() => setOpen((o) => !o)}
        className={cn(
          "hidden max-w-[220px] items-center gap-2 truncate rounded-full border px-3 py-1.5 text-[12px] font-medium transition-all duration-200 lg:inline-flex",
          status === "online"
            ? "border-success/30 bg-success/10 text-success"
            : status === "checking"
              ? "border-border bg-surface-high/80 text-content-muted"
              : "border-warning/30 bg-warning/10 text-warning",
        )}
      >
        <Dot status={status} />
        <span className="truncate">{MODE_LABEL[mode]} · {statusLabel}</span>
      </button>
      <IconButton className="lg:hidden" aria-label={`Connection: ${MODE_LABEL[mode]}`} active={open} onClick={() => setOpen((o) => !o)}>
        <Server size={17} />
        <span
          className={cn(
            "absolute -right-0.5 -top-0.5 h-2.5 w-2.5 rounded-full border-2 border-bg",
            status === "online" ? "bg-success" : status === "checking" ? "bg-content-subtle" : "bg-warning",
          )}
        />
      </IconButton>

      {open ? (
        <div className="absolute right-0 top-11 z-40 w-[min(92vw,22rem)] animate-scale-in rounded-2xl border border-border bg-surface p-2 shadow-glow">
          <div className="flex items-center justify-between gap-3 px-2 py-1.5">
            <div className="min-w-0">
              <p className="text-[13px] font-semibold text-content">Backend connection</p>
              <p className="truncate text-[11.5px] text-content-subtle" title={activeUrl}>
                {activeUrl || "Not configured"}
              </p>
            </div>
            <span className="shrink-0 rounded-full border border-border bg-surface-input px-2 py-0.5 text-[10px] uppercase tracking-wide text-content-subtle">
              {statusLabel}
            </span>
          </div>

          <ul className="mt-1 space-y-1">
            {MODES.map((m) => {
              const selected = mode === m.id;
              return (
                <li key={m.id}>
                  <button
                    type="button"
                    onClick={() => choose(m.id)}
                    className={cn(
                      "flex w-full items-start justify-between gap-2 rounded-xl px-2.5 py-2 text-left transition-colors",
                      selected ? "bg-primary/10" : "hover:bg-surface-raised/70",
                    )}
                  >
                    <span className="min-w-0">
                      <span className={cn("block text-[13px] font-medium", selected ? "text-primary" : "text-content")}>
                        {m.label}
                      </span>
                      <span className="block text-[11px] text-content-subtle">{m.hint}</span>
                    </span>
                    {selected ? <Check size={15} className="mt-0.5 shrink-0 text-primary" /> : null}
                  </button>

                  {/* Tailscale inline editor */}
                  {m.id === "tailscale" && (tsEditing || selected) ? (
                    <div className="mx-1 mt-1 space-y-2 rounded-xl border border-border/70 bg-surface-input/45 p-2.5">
                      <input
                        type="url"
                        inputMode="url"
                        autoCapitalize="none"
                        autoCorrect="off"
                        spellCheck={false}
                        value={tsUrl}
                        onChange={(e) => {
                          setTsUrl(e.target.value);
                          setTestResult(null);
                        }}
                        placeholder="https://your-host.ts.net"
                        className="w-full rounded-lg border border-border bg-surface-input px-2.5 py-1.5 text-[12.5px] text-content placeholder:text-content-subtle focus-ring"
                      />
                      <div className="flex items-center gap-2">
                        <button
                          type="button"
                          onClick={runTest}
                          disabled={testing || !tsUrl.trim()}
                          className="rounded-lg border border-border bg-surface-input px-2.5 py-1.5 text-[12px] font-medium text-content-muted transition-colors hover:border-primary/35 hover:text-content disabled:cursor-not-allowed disabled:opacity-50"
                        >
                          {testing ? "Testing…" : "Test"}
                        </button>
                        <button
                          type="button"
                          onClick={saveTailscale}
                          disabled={!tsUrl.trim()}
                          className="rounded-lg border border-primary/40 bg-primary/10 px-2.5 py-1.5 text-[12px] font-medium text-primary transition-colors hover:bg-primary/15 disabled:cursor-not-allowed disabled:opacity-50"
                        >
                          Save
                        </button>
                      </div>
                      {testResult ? (
                        <p
                          className={cn(
                            "rounded-lg px-2 py-1.5 text-[11.5px]",
                            testResult.ok ? "bg-success/10 text-success" : "bg-warning/10 text-warning",
                          )}
                        >
                          {testResult.message}
                        </p>
                      ) : null}
                    </div>
                  ) : null}
                </li>
              );
            })}
          </ul>

          <p className="mx-1 mt-2 rounded-xl border border-border/70 bg-surface-input/45 px-3 py-2 text-[11px] leading-relaxed text-content-subtle">
            Tailscale is how the mobile app reaches your desktop backend. On desktop web a
            cross-site URL is ignored to avoid a login loop, so this stays same-origin there.
          </p>
        </div>
      ) : null}
    </div>
  );
}

function Dot({ status }: { status: LiveStatus }) {
  return (
    <span
      className={cn(
        "h-1.5 w-1.5 shrink-0 rounded-full",
        status === "online" ? "bg-success" : status === "checking" ? "bg-content-subtle" : "bg-warning",
      )}
    />
  );
}
