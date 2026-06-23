"use client";

import Link from "next/link";
import { PlugZap, ArrowRight, RefreshCw, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/Button";

/**
 * Setup-required state for features that need the backend or the Desktop Bridge.
 * Shown instead of a raw error or a "use the desktop app" message: it says what's
 * unavailable, why, what connection is needed, and links to the fix — on mobile too.
 */
export function SetupRequiredState({
  feature,
  needs = "backend",
  reason,
  onRetry,
}: {
  feature: string;
  needs?: "backend" | "bridge";
  reason?: string;
  onRetry?: () => void;
}) {
  const isBridge = needs === "bridge";
  return (
    <div className="mx-auto max-w-md rounded-2xl border border-border bg-surface/60 px-5 py-8 text-center">
      <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-xl border border-primary/25 bg-primary/10 text-primary">
        <PlugZap size={22} />
      </div>
      <h2 className="mt-4 text-lg font-semibold tracking-tight text-content">
        {feature} needs a connection
      </h2>
      <p className="mt-1.5 text-[13.5px] leading-relaxed text-content-muted">
        {reason ||
          (isBridge
            ? `${feature} runs on a desktop-local service. Connect the Desktop Bridge (Tailscale) to use it from this device.`
            : `${feature} needs the AllHaven backend. Connect to it to continue — your data and keys stay server-side.`)}
      </p>

      <div className="mt-4 rounded-xl border border-border bg-surface-input/40 p-3 text-left text-[12.5px] text-content-muted">
        <p className="flex items-center gap-1.5 font-medium text-content">
          <ShieldCheck size={14} className="text-success" /> How to connect
        </p>
        <ul className="mt-1.5 list-disc space-y-1 pl-5">
          <li>Turn Tailscale on (this device + the desktop, same tailnet).</li>
          <li>
            Top bar → the <span className="text-content">Connection</span> control (server icon) →
            choose <span className="text-content">Tailscale</span> and paste your desktop URL
            (e.g. <span className="font-mono text-[11.5px]">https://your-host.ts.net</span>), then Test.
          </li>
          <li>First time: link this device once on the desktop app (Settings → Connect to Supabase), so the backend trusts your login.</li>
        </ul>
      </div>

      <div className="mt-5 flex flex-col gap-2 sm:flex-row sm:justify-center">
        {onRetry ? (
          <Button onClick={onRetry} className="w-full sm:w-auto">
            <RefreshCw size={15} /> Retry connection
          </Button>
        ) : null}
        <Link href="/dashboard/settings?tab=privacy">
          <Button variant="ghost" className="w-full sm:w-auto">
            Open profile & appearance <ArrowRight size={15} />
          </Button>
        </Link>
      </div>
    </div>
  );
}
