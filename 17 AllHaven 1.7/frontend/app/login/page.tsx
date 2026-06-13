"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowRight, AtSign, Eye, EyeOff, Fingerprint, KeyRound, ShieldCheck, Usb } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { authApi, ApiException } from "@/lib/api";
import { setStoredUser, setToken } from "@/lib/auth";
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

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const result =
        mode === "login"
          ? await authApi.login(email, password)
          : await authApi.register(email, password, fullName);
      setToken(result.access_token);
      setStoredUser(result.user);
      router.replace("/dashboard");
    } catch (err) {
      setError(err instanceof ApiException ? err.message : "Something went wrong. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const fieldLabel = "block text-[11px] font-medium uppercase tracking-[0.12em] text-content-muted";

  return (
    <main className="relative flex min-h-screen items-center justify-center px-4 py-10">
      <div className="w-full max-w-[420px]">
        {/* Glow frame */}
        <div className="rounded-2xl bg-gradient-to-b from-primary/30 via-border to-secondary/20 p-px shadow-glow">
          <div className="rounded-2xl bg-surface/90 px-7 py-8 backdrop-blur-[14px]">
            <div className="flex flex-col items-center text-center">
              <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-primary text-primary-fg shadow-glow-primary">
                <ShieldCheck size={22} />
              </div>
              <h1 className="text-xl font-semibold tracking-tight text-content">AllHaven Command Center</h1>
              <p className="mt-1.5 font-mono text-[10.5px] uppercase tracking-[0.22em] text-content-subtle">
                Your private AI workspace
              </p>
            </div>

            {/* Mode toggle */}
            <div className="mt-6 flex rounded-md border border-border bg-surface-input p-1">
              {(["login", "register"] as Mode[]).map((value) => (
                <button
                  key={value}
                  type="button"
                  onClick={() => {
                    setMode(value);
                    setError(null);
                  }}
                  className={
                    "flex-1 rounded px-3 py-1.5 text-[13px] font-medium transition-colors " +
                    (mode === value ? "bg-surface-high text-primary" : "text-content-muted hover:text-content")
                  }
                >
                  {value === "login" ? "Access" : "Register"}
                </button>
              ))}
            </div>

            <form onSubmit={submit} className="mt-6 space-y-5">
              {mode === "register" ? (
                <div className="space-y-1.5">
                  <label htmlFor="full_name" className={fieldLabel}>
                    Operator name
                  </label>
                  <input
                    id="full_name"
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    placeholder="Ada Lovelace"
                    className="h-11 w-full rounded-lg border border-border bg-surface-input px-3.5 text-sm text-content placeholder:text-content-subtle focus:border-primary/70 focus:outline-none focus:ring-1 focus:ring-primary/30"
                  />
                </div>
              ) : null}

              <div className="space-y-1.5">
                <label htmlFor="email" className={fieldLabel}>
                  <AtSign size={11} className="mr-1 inline" /> Command ID (Email)
                </label>
                <input
                  id="email"
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="identity@allhaven.ai"
                  className="h-11 w-full rounded-lg border border-border bg-surface-input px-3.5 text-sm text-content placeholder:text-content-subtle focus:border-primary/70 focus:outline-none focus:ring-1 focus:ring-primary/30"
                />
              </div>

              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <label htmlFor="password" className={fieldLabel}>
                    <KeyRound size={11} className="mr-1 inline" /> Access Key
                  </label>
                  <span className="text-[11px] text-content-subtle">Min 8 characters</span>
                </div>
                <div className="relative">
                  <input
                    id="password"
                    type={showPassword ? "text" : "password"}
                    required
                    minLength={mode === "register" ? 8 : undefined}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="••••••••••••"
                    className="h-11 w-full rounded-lg border border-border bg-surface-input pl-3.5 pr-10 text-sm text-content placeholder:text-content-subtle focus:border-primary/70 focus:outline-none focus:ring-1 focus:ring-primary/30"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((s) => !s)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-content-subtle hover:text-content"
                    aria-label={showPassword ? "Hide access key" : "Show access key"}
                  >
                    {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>
              </div>

              {error ? (
                <p className="rounded-md border border-danger/30 bg-danger/10 px-3 py-2 text-[13px] text-danger">
                  {error}
                </p>
              ) : null}

              <Button type="submit" size="lg" className="w-full" loading={loading}>
                {mode === "login" ? "Access Command Center" : "Create Command Access"}
                {!loading ? <ArrowRight size={16} /> : null}
              </Button>
            </form>

            {/* Decorative secure bypass — honest: disabled in MVP */}
            <div className="mt-6">
              <div className="mb-3 flex items-center gap-3">
                <span className="h-px flex-1 bg-border" />
                <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-content-subtle">
                  Secure bypass
                </span>
                <span className="h-px flex-1 bg-border" />
              </div>
              <div className="grid grid-cols-2 gap-2">
                {[
                  { icon: Fingerprint, label: "Biometric" },
                  { icon: Usb, label: "Hardware Key" },
                ].map(({ icon: Icon, label }) => (
                  <button
                    key={label}
                    type="button"
                    disabled
                    title="Not available in this MVP"
                    className="flex h-10 cursor-not-allowed items-center justify-center gap-2 rounded-lg border border-border bg-surface-input/60 text-[13px] text-content-subtle"
                  >
                    <Icon size={15} /> {label}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>

        <div className="mt-6 text-center">
          <p className="inline-flex items-center gap-2 text-[12px] text-content-muted">
            <span className="h-1.5 w-1.5 rounded-full bg-primary" />
            Secure by design · Human approval required
          </p>
          <p className="mt-1 font-mono text-[10px] uppercase tracking-[0.18em] text-content-subtle">
            AllHaven Executive Interface {APP_VERSION}
          </p>
          <Link href="/" className="mt-3 inline-block text-[12px] text-content-subtle hover:text-content">
            ← Back to overview
          </Link>
        </div>
      </div>
    </main>
  );
}
