"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowRight, AtSign, Eye, EyeOff, Fingerprint, KeyRound, ServerCog, ShieldCheck, Usb, UserRound } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { BackendBridgeCard } from "@/components/settings/BackendBridgeCard";
import { authApi, ApiException } from "@/lib/api";
import { isBackendUnreachable } from "@/lib/connection";
import { setStoredUser } from "@/lib/auth";
import { APP_VERSION } from "@/components/layout/nav";

type Mode = "login" | "register";

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<Mode>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  // When sign-in can't reach the backend (wrong URL on mobile), let the user fix
  // the connection right here instead of being stuck on a dead login form.
  const [showBackendSetup, setShowBackendSetup] = useState(false);
  const [connError, setConnError] = useState(false);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);
    setConnError(false);
    setLoading(true);
    try {
      const result =
        mode === "login"
          ? await authApi.login(email, password)
          : await authApi.register(email, password, fullName);
      // Auth itself is the HttpOnly cookie the backend just set; we cache only
      // the non-sensitive profile for instant rendering.
      setStoredUser(result.user);
      router.replace("/dashboard");
    } catch (err) {
      const unreachable = isBackendUnreachable(err);
      setConnError(unreachable);
      if (unreachable) setShowBackendSetup(true);
      setError(err instanceof ApiException || err instanceof Error ? err.message : "Something went wrong. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const fieldLabel = "block text-[11px] font-medium uppercase tracking-[0.12em] text-content-muted";
  const fieldShell =
    "h-[46px] w-full rounded-md border border-white/10 bg-white/[0.035] pl-10 text-sm text-content placeholder:text-content-subtle transition-colors focus:border-primary/70 focus:outline-none focus:ring-1 focus:ring-primary/30";
  const fieldIcon = "pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-content-subtle";

  return (
    <main className="relative flex min-h-screen items-center justify-center overflow-hidden bg-bg px-4 py-10 sm:px-6">
      {/* Login gets its own (brighter) aurora — it renders outside the app shell. */}
      <div className="aurora aurora-bright" aria-hidden>
        <i />
      </div>

      <div className="relative z-[1] w-full max-w-[440px]">
        {/* Gradient hairline frame */}
        <div className="rounded-3xl bg-[linear-gradient(160deg,rgb(var(--color-primary-bright)/0.5),rgba(255,255,255,0.06)_42%,rgb(var(--color-secondary)/0.4))] p-px shadow-[0_50px_120px_-40px_rgb(var(--color-primary)/0.28),0_40px_90px_-50px_rgba(0,0,0,0.9)]">
          <div className="rounded-[25px] bg-[linear-gradient(180deg,rgba(18,20,34,0.86),rgba(10,11,20,0.92))] px-6 pb-[30px] pt-[34px] backdrop-blur-[22px] sm:px-8">
            <div className="flex flex-col items-center text-center">
              <div className="grad-primary mb-4 flex h-[52px] w-[52px] items-center justify-center rounded-xl text-primary-fg shadow-[0_0_32px_rgb(var(--color-primary)/0.5)]">
                <ShieldCheck size={24} />
              </div>
              <h1 className="text-[22px] font-semibold tracking-[-0.01em] text-content">AllHaven Command Center</h1>
              <p className="mt-2 font-mono text-[10.5px] uppercase tracking-[0.22em] text-content-subtle">
                Your private AI workspace
              </p>
            </div>

            {/* Access / Register segmented control */}
            <div className="mt-6 flex rounded-md border border-border bg-white/[0.03] p-1">
              {(["login", "register"] as Mode[]).map((value) => (
                <button
                  key={value}
                  type="button"
                  onClick={() => {
                    setMode(value);
                    setError(null);
                  }}
                  className={
                    "flex-1 rounded-[9px] border px-3 py-2 text-[13px] transition-colors " +
                    (mode === value
                      ? "border-primary/30 bg-[linear-gradient(90deg,rgb(var(--color-primary)/0.2),rgb(var(--color-secondary)/0.14))] font-semibold text-content"
                      : "border-transparent font-medium text-content-muted hover:text-content")
                  }
                >
                  {value === "login" ? "Access" : "Register"}
                </button>
              ))}
            </div>

            <form onSubmit={submit} className="mt-[22px] space-y-[18px]">
              {mode === "register" ? (
                <div className="space-y-2">
                  <label htmlFor="full_name" className={fieldLabel}>
                    Operator name
                  </label>
                  <div className="relative">
                    <UserRound size={16} className={fieldIcon} />
                    <input
                      id="full_name"
                      value={fullName}
                      onChange={(e) => setFullName(e.target.value)}
                      placeholder="Ada Lovelace"
                      className={fieldShell + " pr-3.5"}
                    />
                  </div>
                </div>
              ) : null}

              <div className="space-y-2">
                <label htmlFor="email" className={fieldLabel}>
                  Command ID (Email)
                </label>
                <div className="relative">
                  <AtSign size={16} className={fieldIcon} />
                  <input
                    id="email"
                    type="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="identity@allhaven.ai"
                    className={fieldShell + " pr-3.5"}
                  />
                </div>
              </div>

              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <label htmlFor="password" className={fieldLabel}>
                    Access Key
                  </label>
                  <span className="text-[11px] text-content-faint">Min 8 characters</span>
                </div>
                <div className="relative">
                  <KeyRound size={16} className={fieldIcon} />
                  <input
                    id="password"
                    type={showPassword ? "text" : "password"}
                    required
                    minLength={mode === "register" ? 8 : undefined}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="••••••••••••"
                    className={fieldShell + " pr-10"}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((s) => !s)}
                    className="absolute right-3.5 top-1/2 -translate-y-1/2 text-content-subtle transition-colors hover:text-content"
                    aria-label={showPassword ? "Hide access key" : "Show access key"}
                  >
                    {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>
              </div>

              {error ? (
                <div className="rounded-md border border-danger/30 bg-danger/10 px-3.5 py-2.5 text-[13px] text-danger">
                  <p>{error}</p>
                  {connError ? (
                    <p className="mt-1 text-[12px] text-content-muted">
                      Can&apos;t reach the backend. If you&apos;re on mobile, set your desktop&apos;s Tailscale URL below.
                    </p>
                  ) : null}
                </div>
              ) : null}

              <Button type="submit" size="lg" className="h-12 w-full rounded-lg" loading={loading}>
                {mode === "login" ? "Access Command Center" : "Create Command Access"}
                {!loading ? <ArrowRight size={16} /> : null}
              </Button>
            </form>

            {/* Decorative secure bypass — honest: disabled in MVP */}
            <div className="mt-[22px]">
              <div className="mb-3.5 flex items-center gap-3">
                <span className="h-px flex-1 bg-white/[0.08]" />
                <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-content-faint">
                  Secure bypass
                </span>
                <span className="h-px flex-1 bg-white/[0.08]" />
              </div>
              <div className="grid grid-cols-2 gap-2.5">
                {[
                  { icon: Fingerprint, label: "Biometric" },
                  { icon: Usb, label: "Hardware Key" },
                ].map(({ icon: Icon, label }) => (
                  <button
                    key={label}
                    type="button"
                    disabled
                    title="Not available in this MVP"
                    className="flex h-[42px] cursor-not-allowed items-center justify-center gap-2 rounded-md border border-border bg-white/[0.02] text-[13px] text-content-faint"
                  >
                    <Icon size={15} /> {label}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Backend connection setup — reachable BEFORE login so a wrong/unset
            backend URL (the common mobile case) isn't a dead end. */}
        <div className="mt-4">
          {showBackendSetup ? (
            <BackendBridgeCard onConnected={() => { setError(null); setConnError(false); }} />
          ) : (
            <button
              type="button"
              onClick={() => setShowBackendSetup(true)}
              className="flex w-full items-center justify-center gap-2 rounded-md border border-border bg-white/[0.02] px-3 py-2.5 text-[12.5px] text-content-muted transition-colors hover:border-primary/40 hover:text-content"
            >
              <ServerCog size={14} /> Configure backend connection
            </button>
          )}
        </div>

        <div className="mt-[22px] text-center">
          <p className="inline-flex items-center gap-2 text-[12px] text-content-muted">
            <span className="h-1.5 w-1.5 rounded-full bg-primary-bright shadow-[0_0_8px_rgb(var(--color-primary-bright))]" />
            Secure by design · Risky actions require approval
          </p>
          <p className="mt-2 font-mono text-[10px] uppercase tracking-[0.18em] text-content-faint">
            AllHaven Executive Interface {APP_VERSION}
          </p>
          <Link href="/" className="mt-3 inline-block text-[12px] text-content-subtle transition-colors hover:text-content">
            ← Back to overview
          </Link>
        </div>
      </div>
    </main>
  );
}
