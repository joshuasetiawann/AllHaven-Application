"use client";

import { useCallback, useEffect, useState } from "react";
import { AlertTriangle } from "lucide-react";
import { Card, CardHeader } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { Toggle } from "@/components/ui/Toggle";
import { ErrorState, Loading } from "@/components/ui/States";
import { NotConnectedNotice } from "@/components/settings/NotConnectedNotice";
import { aiApi, ApiException } from "@/lib/api";
import { needsBackendConnection } from "@/lib/connection";
import { BACKEND_CHANGED_EVENT } from "@/lib/connectionMode";
import type { AiChatSettings } from "@/types";

// Shown when the backend isn't connected, so the controls are still visible/configurable
// (changes save once you connect). Mirrors the backend defaults.
const DEFAULT_CHAT_SETTINGS: AiChatSettings = {
  default_mode: "single",
  polish_level: "standard",
  max_active_agents: 3,
  show_debate_flow: true,
  require_approval: true,
  show_tool_activity: true,
};

export function AiChatBehaviorPanel() {
  const [settings, setSettings] = useState<AiChatSettings | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  // Backend unreachable → render an honest connect-state instead of an endless spinner.
  const [needsBackend, setNeedsBackend] = useState(false);
  const [backendIssue, setBackendIssue] = useState<"unreachable" | "auth">("unreachable");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  // Local text state so the number field saves on commit, not per keystroke.
  const [maxAgents, setMaxAgents] = useState("");

  const load = useCallback(async () => {
    setLoadError(null);
    setNeedsBackend(false);
    setBackendIssue("unreachable");
    try {
      const data = await aiApi.getChatSettings();
      setSettings(data);
      setMaxAgents(String(data.max_active_agents));
    } catch (err) {
      if (needsBackendConnection(err)) {
        setBackendIssue(err instanceof ApiException && (err.statusCode === 401 || err.statusCode === 403) ? "auth" : "unreachable");
        setNeedsBackend(true);
        setSettings(DEFAULT_CHAT_SETTINGS);
        setMaxAgents(String(DEFAULT_CHAT_SETTINGS.max_active_agents));
        return;
      }
      setLoadError(err instanceof ApiException ? err.message : "Failed to load chat settings.");
    }
  }, []);

  useEffect(() => {
    void load();
    const onBackendChanged = () => void load();
    window.addEventListener(BACKEND_CHANGED_EVENT, onBackendChanged);
    return () => window.removeEventListener(BACKEND_CHANGED_EVENT, onBackendChanged);
  }, [load]);

  // Per-control optimistic save: apply immediately, sync with the response, revert on failure.
  const save = async (patch: Partial<AiChatSettings>) => {
    if (!settings) return;
    const previous = settings;
    setSettings({ ...settings, ...patch });
    setSaving(true);
    setError(null);
    try {
      const updated = await aiApi.setChatSettings(patch);
      setSettings(updated);
      setMaxAgents(String(updated.max_active_agents));
    } catch (err) {
      setSettings(previous);
      setMaxAgents(String(previous.max_active_agents));
      setError(err instanceof ApiException ? err.message : "Failed to save chat settings.");
    } finally {
      setSaving(false);
    }
  };

  const commitMaxAgents = () => {
    if (!settings) return;
    const raw = maxAgents.trim();
    const num = Number(raw);
    if (!/^\d+$/.test(raw) || num < 1 || num > 10) {
      setError("Max active agents must be a whole number between 1 and 10.");
      return;
    }
    setError(null);
    if (num === settings.max_active_agents) return;
    void save({ max_active_agents: num });
  };

  if (loadError && !needsBackend) return <ErrorState message={loadError} onRetry={load} />;
  if (!settings) return <Loading label="Loading chat settings…" />;

  return (
    <div className="space-y-4">
      {needsBackend ? (
        <NotConnectedNotice kind={backendIssue} what="Desktop-only chat defaults need the Desktop Bridge." onRetry={load} />
      ) : null}
      {error ? <p className="text-[12.5px] text-danger">{error}</p> : null}

      <div className="grid gap-5 lg:grid-cols-2">
        <Card>
          <CardHeader title="Chat defaults" subtitle="Applied when you open a new AI chat." />
          <div className="space-y-4">
            <Select
              label="Default mode"
              value={settings.default_mode}
              disabled={saving}
              onChange={(e) => void save({ default_mode: e.target.value as AiChatSettings["default_mode"] })}
            >
              <option value="single">Single</option>
              <option value="parallel">Parallel</option>
              <option value="debate">Debate</option>
              <option value="reasoning">Reasoning</option>
            </Select>
            <Select
              label="Polish level"
              value={settings.polish_level}
              disabled={saving}
              onChange={(e) => void save({ polish_level: e.target.value as AiChatSettings["polish_level"] })}
            >
              <option value="standard">Standard</option>
              <option value="high">High</option>
            </Select>
            <Input
              id="max_active_agents"
              label="Max active agents"
              type="number"
              inputMode="numeric"
              min={1}
              max={10}
              disabled={saving}
              value={maxAgents}
              onChange={(e) => setMaxAgents(e.target.value)}
              onBlur={commitMaxAgents}
              onKeyDown={(e) => {
                if (e.key === "Enter") commitMaxAgents();
              }}
              hint="Between 1 and 10. Saved when you leave the field."
            />
          </div>
        </Card>

        <Card>
          <CardHeader title="Behavior" subtitle="How the assistant acts during a chat." />
          <ul className="divide-y divide-border">
            <li className="flex items-center justify-between gap-3 py-3.5">
              <div>
                <p className="text-sm text-content">Show debate flow</p>
                <p className="text-[12.5px] text-content-muted">
                  Display the back-and-forth between agents in debate mode.
                </p>
              </div>
              <Toggle
                checked={settings.show_debate_flow}
                onChange={(v) => void save({ show_debate_flow: v })}
                disabled={saving}
                label="Show debate flow"
              />
            </li>
            <li className="flex items-center justify-between gap-3 py-3.5">
              <div>
                <p className="text-sm text-content">Require approval for write actions</p>
                <p className="text-[12.5px] text-content-muted">
                  Every write action waits for your approval before it runs.
                </p>
                {!settings.require_approval ? (
                  <p className="mt-1.5 flex items-start gap-1.5 text-[12px] text-warning">
                    <AlertTriangle size={13} className="mt-0.5 shrink-0" />
                    HIGH-risk actions still require approval.
                  </p>
                ) : null}
              </div>
              <Toggle
                checked={settings.require_approval}
                onChange={(v) => void save({ require_approval: v })}
                disabled={saving}
                label="Require approval for write actions"
              />
            </li>
            <li className="flex items-center justify-between gap-3 py-3.5">
              <div>
                <p className="text-sm text-content">Show tool activity</p>
                <p className="text-[12.5px] text-content-muted">
                  Show which tools the AI calls while it works.
                </p>
              </div>
              <Toggle
                checked={settings.show_tool_activity}
                onChange={(v) => void save({ show_tool_activity: v })}
                disabled={saving}
                label="Show tool activity"
              />
            </li>
          </ul>
        </Card>
      </div>
    </div>
  );
}
