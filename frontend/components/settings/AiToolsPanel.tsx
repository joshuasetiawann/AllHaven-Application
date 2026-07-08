"use client";

import { useCallback, useEffect, useState } from "react";
import { ShieldCheck, Wrench } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Toggle } from "@/components/ui/Toggle";
import { EmptyState, ErrorState, Loading } from "@/components/ui/States";
import { NotConnectedNotice } from "@/components/settings/NotConnectedNotice";
import { aiApi, ApiException } from "@/lib/api";
import { needsBackendConnection } from "@/lib/connection";
import { BACKEND_CHANGED_EVENT } from "@/lib/connectionMode";
import type { AiTool } from "@/types";

// Known module display order; anything new from the backend registry is appended after.
const MODULE_ORDER = ["time", "tasks", "calendar", "notes", "finance", "files", "automation", "system"];
const MODULE_LABELS: Record<string, string> = {
  calendar: "routine",
};

// Map a tool's risk level to a Badge tone.
const RISK_TONE: Record<AiTool["risk"], "neutral" | "warning" | "danger"> = {
  LOW: "neutral",
  MEDIUM: "warning",
  HIGH: "danger",
};

export function AiToolsPanel() {
  const [tools, setTools] = useState<AiTool[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  // Backend unreachable → render an honest connect-state instead of an endless spinner.
  const [needsBackend, setNeedsBackend] = useState(false);
  const [backendIssue, setBackendIssue] = useState<"unreachable" | "auth">("unreachable");
  const [error, setError] = useState<string | null>(null);
  // Name of the tool whose toggle is being saved.
  const [busyTool, setBusyTool] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoadError(null);
    setNeedsBackend(false);
    setBackendIssue("unreachable");
    try {
      setTools(await aiApi.listTools());
    } catch (err) {
      if (needsBackendConnection(err)) {
        setBackendIssue(err instanceof ApiException && (err.statusCode === 401 || err.statusCode === 403) ? "auth" : "unreachable");
        setNeedsBackend(true);
        return;
      }
      setLoadError(err instanceof ApiException ? err.message : "Failed to load AI tools.");
    }
  }, []);

  useEffect(() => {
    void load();
    const onBackendChanged = () => void load();
    window.addEventListener(BACKEND_CHANGED_EVENT, onBackendChanged);
    return () => window.removeEventListener(BACKEND_CHANGED_EVENT, onBackendChanged);
  }, [load]);

  // Optimistic toggle: flip immediately, sync with the response, revert on failure.
  const toggleTool = async (tool: AiTool, enabled: boolean) => {
    setBusyTool(tool.name);
    setError(null);
    setTools((prev) => prev?.map((t) => (t.name === tool.name ? { ...t, enabled } : t)) ?? prev);
    try {
      const updated = await aiApi.setToolEnabled(tool.name, enabled);
      setTools((prev) => prev?.map((t) => (t.name === updated.name ? updated : t)) ?? prev);
    } catch (err) {
      setTools((prev) => prev?.map((t) => (t.name === tool.name ? { ...t, enabled: !enabled } : t)) ?? prev);
      setError(err instanceof ApiException ? err.message : `Failed to update ${tool.name}.`);
    } finally {
      setBusyTool(null);
    }
  };

  // Only a hard spinner/error when we're actually mid-load on a reachable backend.
  if (loadError && !needsBackend) return <ErrorState message={loadError} onRetry={load} />;
  if (!tools && !needsBackend) return <Loading label="Loading AI tools…" />;

  const list = tools ?? [];
  const modules = [
    ...MODULE_ORDER.filter((m) => list.some((t) => t.module === m)),
    ...Array.from(new Set(list.map((t) => t.module))).filter((m) => !MODULE_ORDER.includes(m)),
  ];

  return (
    <div className="space-y-4">
      {/* Stay OPEN with or without the backend — show the registry + a slim notice. */}
      {needsBackend ? (
        <NotConnectedNotice kind={backendIssue} what="Backend-only AI tools load from your Desktop Bridge." onRetry={load} />
      ) : null}

      <Card padding="md" className="border-primary/15">
        <div className="flex items-start gap-3">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <ShieldCheck size={18} />
          </span>
          <div>
            <p className="text-sm font-semibold text-content">AI tool registry</p>
            <p className="mt-0.5 text-[13px] text-content-muted">
              Write actions always create a pending approval — the AI never executes them silently.
              HIGH-risk tools require approval even if approvals are relaxed.
            </p>
          </div>
        </div>
      </Card>

      {error ? <p className="text-[12.5px] text-danger">{error}</p> : null}

      {list.length === 0 ? (
        <EmptyState
          title={needsBackend ? "Tools load when you connect" : "No AI tools registered"}
          description={
            needsBackend
              ? "Connect the Desktop Bridge from the server icon in the top bar to load backend-only tools."
              : "The backend Tool Registry has not published any tools yet."
          }
          icon={<Wrench size={20} />}
        />
      ) : (
      <Card>
        <div className="space-y-5">
          {modules.map((module) => (
            <section key={module}>
              <p className="label-mono">{MODULE_LABELS[module] ?? module}</p>
              <ul className="mt-1 divide-y divide-border">
                {list
                  .filter((t) => t.module === module)
                  .map((tool) => (
                    <li key={tool.name} className="flex items-center justify-between gap-3 py-3">
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-1.5">
                          <p className="font-mono text-[13px] text-content">{tool.name}</p>
                          <Badge tone={tool.access === "write" ? "primary" : "neutral"}>{tool.access}</Badge>
                          <Badge tone={RISK_TONE[tool.risk]}>{tool.risk}</Badge>
                          {tool.access === "write" || tool.approval_required ? (
                            <Badge tone="info">Approval required</Badge>
                          ) : null}
                        </div>
                        <p className="mt-0.5 text-[12.5px] text-content-muted">{tool.description}</p>
                      </div>
                      <Toggle
                        checked={tool.enabled}
                        onChange={(enabled) => toggleTool(tool, enabled)}
                        disabled={busyTool === tool.name}
                        label={`Enable ${tool.name}`}
                      />
                    </li>
                  ))}
              </ul>
            </section>
          ))}
        </div>
      </Card>
      )}
    </div>
  );
}
