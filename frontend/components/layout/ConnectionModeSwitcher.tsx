"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Check, Download, Globe, Lock, Server } from "lucide-react";
import { IconButton } from "@/components/ui/IconButton";
import { pingBackend, testBackendConnection, type BackendTestResult } from "@/lib/connection";
import {
  BACKEND_CHANGED_EVENT,
  getApiBaseUrl,
  getApiBaseUrlSource,
  getConnectionMode,
  getRememberedUrl,
  setConnectionMode,
  TAILSCALE_DOWNLOAD_URL,
  type ConnectionMode,
} from "@/lib/connectionMode";
import { BEARER_MODE } from "@/lib/mobileAuth";
import { cn } from "@/lib/format";
import type { BackendUrlSource } from "@/lib/backendUrl";

type LiveStatus = "checking" | "online" | "offline";

const MODE_LABEL: Record<ConnectionMode, string> = {
  local: "Local",
  private: "Private",
  funnel: "Tunnel",
};

const MODES: { id: ConnectionMode; label: string; hint: string; icon: typeof Lock; needsUrl: boolean }[] = [
  { id: "private", label: "Tailscale Private", hint: "Private tunnel over your tailnet (recommended, secure).", icon: Lock, needsUrl: true },
  { id: "funnel", label: "Tailscale Tunnel (Funnel)", hint: "Public tunnel — reachable over the internet if you enabled Funnel.", icon: Globe, needsUrl: true },
  { id: "local", label: "Local", hint: "The backend on this computer (desktop only).", icon: Server, needsUrl: false },
];

export function ConnectionModeSwitcher() {
  const [open, setOpen] = useState(false);
  const [mode, setMode] = useState<ConnectionMode>("private");
  const [status, setStatus] = useState<LiveStatus>("checking");
  const [activeUrl, setActiveUrl] = useState("");
  const [source, setSource] = useState<BackendUrlSource>("none");
  // Inline URL editor — which mode's URL we're editing, and its current text.
  const [editMode, setEditMode] = useState<ConnectionMode | null>(null);
  const [url, setUrl] = useState("");
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<BackendTestResult | null>(null);
  const ref = useRef<HTMLDivElement>(null);

  // Read the active mode/URL and re-check reachability. Re-runs on demand and
  // whenever the backend override changes anywhere in the app.
  const refresh = useCallback(() => {
    setMode(getConnectionMode());
    setActiveUrl(getApiBaseUrl());
    setSource(getApiBaseUrlSource());
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

  // When the popover opens, default the editor to the active Tailscale mode.
  useEffect(() => {
    if (open) {
      const m = getConnectionMode();
      if (m !== "local") {
        setEditMode(m);
        setUrl(getRememberedUrl(m));
      } else {
        setEditMode(null);
      }
      setTestResult(null);
    }
  }, [open]);

  const choose = (next: ConnectionMode) => {
    if (next === "local") {
      setConnectionMode("local"); // dispatches the change event → refresh() runs
      setEditMode(null);
      setOpen(false);
      return;
    }
    // Reveal the inline URL editor for this Tailscale mode (don't apply until Save).
    setEditMode(next);
    setUrl(getRememberedUrl(next));
    setTestResult(null);
  };

  const runTest = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      setTestResult(await testBackendConnection(url));
    } finally {
      setTesting(false);
    }
  };

  const saveCurrent = () => {
    if (!editMode) return;
    setConnectionMode(editMode, url); // dispatches the change event → refresh() runs
    setOpen(false);
  };

  const desktopNotUsingSelectedTailscale = !BEARER_MODE && mode !== "local" && source !== "override";
  const hasSavedSelectedUrl = mode !== "local" && Boolean(getRememberedUrl(mode));
  const displayMode: ConnectionMode = desktopNotUsingSelectedTailscale ? "local" : mode;
  const statusLabel = status === "checking" ? "Checking" : status === "online" ? "Online" : "Offline";

  return (
    <div className="relative" ref={ref}>
      {/* Trigger: a compact pill on lg+, an icon-only button (with status dot) on phones. */}
      <button
        type="button"
        aria-label={`Connection: ${MODE_LABEL[displayMode]} · ${statusLabel}`}
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
        <span className="truncate">{MODE_LABEL[displayMode]} · {statusLabel}</span>
      </button>
      <IconButton className="relative lg:hidden" aria-label={`Connection: ${MODE_LABEL[displayMode]}`} active={open} onClick={() => setOpen((o) => !o)}>
        <Server size={17} />
        <span
          className={cn(
            "absolute -right-0.5 -top-0.5 h-2.5 w-2.5 rounded-full border-2 border-bg",
            status === "online" ? "bg-success" : status === "checking" ? "bg-content-subtle" : "bg-warning",
          )}
        />
      </IconButton>

      {open ? (
        // Centered on phones (fixed, viewport-centered so it never sits off to one side);
        // drops from the button on lg+. This fixes the "menu too far left / off-centre".
        <div className="fixed left-1/2 top-16 z-50 w-[min(94vw,23rem)] -translate-x-1/2 animate-scale-in rounded-2xl border border-border bg-surface p-2 shadow-glow lg:absolute lg:left-auto lg:right-0 lg:top-11 lg:translate-x-0">
          <div className="flex items-center justify-between gap-3 px-2 py-1.5">
            <div className="min-w-0">
              <p className="text-[13px] font-semibold text-content">Backend connection</p>
              <p className="truncate text-[11.5px] text-content-subtle" title={activeUrl}>
                {activeUrl || "Not set"}
              </p>
            </div>
            <span
              className={cn(
                "shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide",
                status === "online"
                  ? "border-success/30 bg-success/10 text-success"
                  : status === "checking"
                    ? "border-border bg-surface-input text-content-subtle"
                    : "border-warning/30 bg-warning/10 text-warning",
              )}
            >
              {statusLabel}
            </span>
          </div>

          {desktopNotUsingSelectedTailscale && hasSavedSelectedUrl ? (
            <div className="mx-1 mt-1 rounded-xl border border-warning/30 bg-warning/10 px-3 py-2 text-[11.5px] leading-relaxed text-warning">
              This desktop browser is using the same-site backend above. Your saved Tailscale URL is kept for the mobile APK, but it is ignored here to avoid cookie login loops.
            </div>
          ) : null}

          <ul className="mt-1 space-y-1">
            {MODES.map((m) => {
              const selected = mode === m.id;
              const editing = editMode === m.id;
              const Icon = m.icon;
              return (
                <li key={m.id}>
                  <button
                    type="button"
                    onClick={() => choose(m.id)}
                    className={cn(
                      "flex w-full items-start gap-2.5 rounded-xl px-2.5 py-2 text-left transition-colors",
                      selected || editing ? "bg-primary/10" : "hover:bg-surface-raised/70",
                    )}
                  >
                    <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg border border-border bg-surface-input/60 text-content-subtle">
                      <Icon size={15} />
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className={cn("block text-[13px] font-medium", selected ? "text-primary" : "text-content")}>
                        {m.label}
                      </span>
                      <span className="block text-[11.5px] leading-snug text-content-subtle">{m.hint}</span>
                    </span>
                    {selected ? <Check size={15} className="mt-1 shrink-0 text-primary" /> : null}
                  </button>

                  {/* Inline URL editor for the chosen Tailscale mode */}
                  {m.needsUrl && editing ? (
                    <div className="mx-1 mt-1 space-y-2 rounded-xl border border-border/70 bg-surface-input/45 p-2.5">
                      <input
                        type="url"
                        inputMode="url"
                        autoCapitalize="none"
                        autoCorrect="off"
                        spellCheck={false}
                        value={url}
                        onChange={(e) => {
                          setUrl(e.target.value);
                          setTestResult(null);
                        }}
                        placeholder={m.id === "funnel" ? "https://your-host.funnel.ts.net" : "https://your-host.ts.net"}
                        className="w-full rounded-lg border border-border bg-surface-input px-2.5 py-2 text-[12.5px] text-content placeholder:text-content-subtle focus-ring"
                      />
                      <div className="flex items-center gap-2">
                        <button
                          type="button"
                          onClick={runTest}
                          disabled={testing || !url.trim()}
                          className="rounded-lg border border-border bg-surface-input px-2.5 py-1.5 text-[12px] font-medium text-content-muted transition-colors hover:border-primary/35 hover:text-content disabled:cursor-not-allowed disabled:opacity-50"
                        >
                          {testing ? "Testing…" : "Test"}
                        </button>
                        <button
                          type="button"
                          onClick={saveCurrent}
                          disabled={!url.trim()}
                          className="rounded-lg border border-primary/40 bg-primary/10 px-3 py-1.5 text-[12px] font-medium text-primary transition-colors hover:bg-primary/15 disabled:cursor-not-allowed disabled:opacity-50"
                        >
                          Connect
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

          <a
            href={TAILSCALE_DOWNLOAD_URL}
            target="_blank"
            rel="noreferrer"
            className="mx-1 mt-2 flex items-center gap-2 rounded-xl border border-border bg-surface-input/55 px-3 py-2 text-[12.5px] font-medium text-content transition-colors hover:border-primary/40 hover:text-primary"
          >
            <Download size={15} className="shrink-0" /> Download Tailscale
          </a>
          <p className="mx-1 mt-2 px-1 text-[11px] leading-relaxed text-content-subtle">
            Private &amp; Tunnel reach your desktop backend through Tailscale. On desktop web a
            cross-site URL is ignored (login-loop guard); the phone honours it.
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
