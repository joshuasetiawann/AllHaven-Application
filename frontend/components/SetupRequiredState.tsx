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
    <div className="panel-gradient mx-auto max-w-md px-5 py-8 text-center">
      <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-xl bg-[linear-gradient(135deg,#7FF7F2,#A78BFA)] text-primary-fg shadow-glow-primary">
        <PlugZap size={22} />
      </div>
      <p className="label-mono mt-4">Connection required</p>
      <h2 className="mt-1.5 text-lg font-semibold tracking-tight text-content">
        {feature} needs a connection
      </h2>
      <p className="mt-1.5 text-[13.5px] leading-relaxed text-content-muted">
        {reason ||
          (isBridge
            ? `${feature} runs on a desktop-local service. Connect the Desktop Bridge (Tailscale) to use it from this device.`
            : `${feature} needs the AllHaven backend. Connect to it to continue — your data and keys stay server-side.`)}
      </p>

      <div className="glass-tile mt-4 p-3 text-left text-[12.5px] text-content-muted">
        <p className="flex items-center gap-1.5 font-medium text-content">
          <ShieldCheck size={14} className="text-success-soft" /> What you need
        </p>
        <ul className="mt-1.5 list-disc space-y-1 pl-5">
          {isBridge ? (
            <>
              <li>Tailscale on this device + the desktop (same tailnet).</li>
              <li>Set the service&apos;s Connection mode to <span className="text-content">Tailscale Private</span> and Test it.</li>
            </>
          ) : (
            <>
              <li>The backend reachable (locally, or over Tailscale from mobile).</li>
              <li>Then this feature works the same as on desktop.</li>
            </>
          )}
        </ul>
      </div>

      <div className="mt-5 flex flex-col gap-2 sm:flex-row sm:justify-center">
        <Link href="/dashboard/settings?tab=tools">
          <Button className="w-full sm:w-auto">
            Open Settings → Desktop Bridge <ArrowRight size={15} />
          </Button>
        </Link>
        {onRetry ? (
          <Button variant="ghost" onClick={onRetry} className="w-full sm:w-auto">
            <RefreshCw size={15} /> Retry
          </Button>
        ) : null}
      </div>
    </div>
  );
}
