"use client";

import { useEffect, useState } from "react";
import { AlertTriangle, Check, KeyRound, Loader2, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { SecretInput } from "@/components/settings/SecretInput";
import { cn } from "@/lib/format";
import {
  clearProviderKey,
  configuredProviders,
  directProviderIds,
  setProviderKey,
} from "@/lib/aiDirect";

const LABELS: Record<string, string> = {
  openai: "OpenAI",
  anthropic: "Anthropic",
  gemini: "Google Gemini",
  grok: "Grok (xAI)",
  deepseek: "DeepSeek",
  openrouter: "OpenRouter",
  qwen: "Qwen",
  blackbox: "Blackbox",
};

/**
 * API keys kept on THIS device, used only when the desktop backend can't be
 * reached. Stored in Android Keystore via credentialStorage — never sent to
 * Supabase, never synced to another device, and never seen by the backend.
 */
export function OnDeviceKeysCard() {
  const [configured, setConfigured] = useState<string[]>([]);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = () =>
    configuredProviders()
      .then(setConfigured)
      .catch(() => setConfigured([]))
      .finally(() => setLoading(false));

  useEffect(() => {
    void refresh();
  }, []);

  const save = async (id: string) => {
    const key = (drafts[id] ?? "").trim();
    if (!key) return;
    setBusy(id);
    setError(null);
    try {
      await setProviderKey(id, key);
      setDrafts((d) => ({ ...d, [id]: "" }));
      await refresh();
    } catch (err) {
      // A failed secure write must not silently leave the key half-saved.
      setError(err instanceof Error ? err.message : `Could not save the ${id} key on this device.`);
    } finally {
      setBusy(null);
    }
  };

  const remove = async (id: string) => {
    setBusy(id);
    setError(null);
    try {
      await clearProviderKey(id);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : `Could not remove the ${id} key.`);
    } finally {
      setBusy(null);
    }
  };

  return (
    <section className="panel p-5">
      <div className="mb-1 flex items-center gap-2">
        <span className="flex h-8 w-8 items-center justify-center rounded-lg border border-border bg-surface-input text-primary">
          <KeyRound size={16} />
        </span>
        <h2 className="text-[15px] font-semibold text-content">On-device AI keys</h2>
      </div>
      <p className="mb-3 text-[13px] leading-relaxed text-content-muted">
        Used only when this device can&apos;t reach the AllHaven backend. Keys are stored in the
        device&apos;s encrypted keystore — they are never sent to Supabase, never synced to another
        device, and the backend never sees them.
      </p>

      <p className="mb-4 flex items-start gap-1.5 rounded-md border border-warning/30 bg-warning/10 px-3 py-2 text-[11.5px] leading-relaxed text-warning">
        <AlertTriangle size={12} className="mt-0.5 shrink-0" />
        <span>
          A key on a phone can be read by anyone who controls that phone. Direct calls also skip
          tools, approvals, memory, AI Knowledge, and the audit trail — you get plain text back.
          Prefer the backend whenever it&apos;s reachable, and use keys scoped to what the phone needs.
        </span>
      </p>

      {error ? <p className="mb-3 text-[12px] text-danger">{error}</p> : null}

      {loading ? (
        <p className="flex items-center gap-2 text-[13px] text-content-muted">
          <Loader2 size={14} className="animate-spin" /> Checking this device…
        </p>
      ) : (
        <div className="space-y-2.5">
          {directProviderIds.map((id) => {
            const saved = configured.includes(id);
            const working = busy === id;
            return (
              <div key={id} className="flex flex-wrap items-center gap-2 rounded-lg border border-border bg-surface-input/40 p-2.5">
                <span className="flex min-w-[110px] items-center gap-1.5 text-[13px] font-medium text-content">
                  {LABELS[id] ?? id}
                  {saved ? <Check size={13} className="text-success" /> : null}
                </span>
                <div className="min-w-[180px] flex-1">
                  <SecretInput
                    id={`ondevice-key-${id}`}
                    label={`${LABELS[id] ?? id} API key`}
                    value={drafts[id] ?? ""}
                    onChange={(v) => setDrafts((d) => ({ ...d, [id]: v }))}
                    placeholder={saved ? "Saved on this device — type to replace" : "Paste API key"}
                  />
                </div>
                <Button
                  size="sm"
                  onClick={() => void save(id)}
                  disabled={working || !(drafts[id] ?? "").trim()}
                  loading={working}
                >
                  Save
                </Button>
                {saved ? (
                  <button
                    type="button"
                    onClick={() => void remove(id)}
                    disabled={working}
                    aria-label={`Remove ${LABELS[id] ?? id} key from this device`}
                    className={cn(
                      "flex h-8 w-8 items-center justify-center rounded-md border border-border text-content-subtle transition-colors",
                      "hover:border-danger/40 hover:text-danger disabled:opacity-50",
                    )}
                  >
                    <Trash2 size={14} />
                  </button>
                ) : null}
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}
