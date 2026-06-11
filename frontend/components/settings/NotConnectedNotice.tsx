"use client";

import { PlugZap, RefreshCw } from "lucide-react";

/**
 * Slim, NON-blocking "not connected to the backend" banner. Unlike a full-screen
 * SetupRequiredState, this sits at the top of a settings panel and lets the rest of the
 * panel render below it — so every settings section stays OPEN (with or without
 * Tailscale) and the user can still see/configure what's there.
 */
export function NotConnectedNotice({
  what,
  onRetry,
}: {
  what?: string;
  onRetry?: () => void;
}) {
  return (
    <div className="flex items-start gap-2.5 rounded-xl border border-warning/30 bg-warning/10 px-3 py-2.5 text-[12.5px] text-warning">
      <PlugZap size={15} className="mt-0.5 shrink-0" />
      <div className="min-w-0 flex-1">
        <p className="font-medium">Not connected to your backend</p>
        <p className="mt-0.5 text-warning/90">
          {what ? `${what} ` : ""}Pick <span className="font-medium">Connection</span> (server icon) in
          the top bar → choose <span className="font-medium">Tailscale Private</span> and connect.
          Settings below stay visible either way.
        </p>
      </div>
      {onRetry ? (
        <button
          type="button"
          onClick={onRetry}
          className="shrink-0 inline-flex items-center gap-1 rounded-lg border border-warning/40 px-2 py-1 text-[11.5px] font-medium transition-colors hover:bg-warning/15"
        >
          <RefreshCw size={12} /> Retry
        </button>
      ) : null}
    </div>
  );
}
