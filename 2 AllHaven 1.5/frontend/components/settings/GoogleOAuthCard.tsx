"use client";

import { useEffect, useState } from "react";
import { AlertTriangle, Chrome, Settings2, ShieldCheck } from "lucide-react";
import { Card, CardHeader } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { ConfigStatusBadge } from "@/components/ui/meta";
import { googleApi, ApiException } from "@/lib/api";
import type { Integration } from "@/types";
import type { GoogleScopes } from "@/types/api";

export function GoogleOAuthCard({
  google,
  onConfigure,
  onChange,
}: {
  google?: Integration;
  onConfigure: () => void;
  onChange: (updated: Integration) => void;
}) {
  const [scopes, setScopes] = useState<GoogleScopes | null>(null);
  const [extra, setExtra] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    googleApi.scopes().then(setScopes).catch(() => setScopes(null));
  }, []);

  const configured = google?.configured;
  const status = google?.status ?? "not_configured";

  const connect = async () => {
    setBusy(true);
    setError(null);
    try {
      const { authorization_url } = await googleApi.loginUrl(extra);
      window.open(authorization_url, "_blank", "noopener");
    } catch (err) {
      setError(err instanceof ApiException ? err.message : "Could not start Google sign-in.");
    } finally {
      setBusy(false);
    }
  };

  const disconnect = async () => {
    setBusy(true);
    try {
      onChange(await googleApi.disconnect());
    } finally {
      setBusy(false);
    }
  };

  const toggleScope = (id: string) =>
    setExtra((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));

  return (
    <Card className="lg:col-span-3">
      <CardHeader
        title="Google OAuth"
        subtitle="One Google login authenticates you; each Google API needs its own scope + consent."
        icon={<Chrome size={18} />}
        action={<ConfigStatusBadge status={status} />}
      />

      <div className="grid gap-4 lg:grid-cols-2">
        <div>
          <p className="mb-2 font-mono text-[11px] uppercase tracking-wide text-content-subtle">
            Requested scopes
          </p>
          <ul className="space-y-2">
            {(scopes?.catalog ?? []).map((group) => {
              const isDefault = group.default;
              const selected = isDefault || extra.includes(group.id);
              return (
                <li key={group.id} className="flex items-start gap-2.5">
                  <input
                    type="checkbox"
                    checked={selected}
                    disabled={isDefault}
                    onChange={() => toggleScope(group.id)}
                    className="mt-1 h-4 w-4 rounded border-border bg-surface-input accent-primary disabled:opacity-60"
                  />
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-[13px] text-content">{group.label}</span>
                      {isDefault ? <Badge tone="success">default</Badge> : null}
                      {group.sensitive ? <Badge tone="warning">sensitive</Badge> : null}
                    </div>
                    <p className="text-[12px] text-content-muted">{group.note}</p>
                  </div>
                </li>
              );
            })}
          </ul>
        </div>

        <div className="space-y-3">
          <div className="rounded-lg border border-border bg-surface-input p-3">
            <p className="flex items-center gap-2 text-[13px] text-content">
              <ShieldCheck size={15} className="text-primary" /> Minimal by default
            </p>
            <p className="mt-1 text-[12px] text-content-muted">
              Default scopes: {(scopes?.default_scopes ?? ["openid", "email", "profile"]).join(", ")}. Gmail is
              never requested by default.
            </p>
          </div>
          {scopes?.notes?.some((n) => n.toLowerCase().includes("verification")) ? (
            <p className="flex items-start gap-2 rounded-lg border border-warning/30 bg-warning/10 px-3 py-2 text-[12px] text-warning">
              <AlertTriangle size={14} className="mt-0.5 shrink-0" />
              Sensitive/restricted scopes may require Google app verification before production use.
            </p>
          ) : null}

          <div className="flex flex-wrap items-center gap-2">
            <Button onClick={connect} disabled={!configured || busy} loading={busy}>
              <Chrome size={15} /> Connect with Google
            </Button>
            <Button variant="subtle" size="md" onClick={onConfigure}>
              <Settings2 size={14} /> Configure client
            </Button>
            {configured ? (
              <Button variant="ghost" size="md" onClick={disconnect} disabled={busy}>
                Disconnect
              </Button>
            ) : null}
          </div>
          {!configured ? (
            <p className="text-[12px] text-content-subtle">
              Add your Google client ID, redirect URI, and client secret first (Configure client).
            </p>
          ) : null}
          {error ? <p className="text-[12px] text-danger">{error}</p> : null}
        </div>
      </div>
    </Card>
  );
}
