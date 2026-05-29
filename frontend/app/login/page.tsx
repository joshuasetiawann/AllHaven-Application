"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { authApi, ApiException } from "@/lib/api";
import { setStoredUser, setToken } from "@/lib/auth";

type Mode = "login" | "register";

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<Mode>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
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
      const message =
        err instanceof ApiException ? err.message : "Something went wrong. Please try again.";
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="flex min-h-screen items-center justify-center px-4 py-12">
      <div className="w-full max-w-md">
        <Link href="/" className="mb-8 flex items-center justify-center gap-2.5">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary text-primary-fg">
            <ShieldCheck size={20} />
          </div>
          <div className="leading-tight">
            <p className="text-[16px] font-semibold tracking-tight text-content">CoreOS</p>
            <p className="label-mono">Command Center</p>
          </div>
        </Link>

        <div className="panel p-6">
          <div className="mb-5 flex rounded-md border border-border bg-surface-input p-1">
            {(["login", "register"] as Mode[]).map((value) => (
              <button
                key={value}
                onClick={() => {
                  setMode(value);
                  setError(null);
                }}
                className={
                  "flex-1 rounded px-3 py-1.5 text-sm font-medium capitalize transition-colors " +
                  (mode === value
                    ? "bg-surface-high text-primary"
                    : "text-content-muted hover:text-content")
                }
              >
                {value === "login" ? "Sign in" : "Register"}
              </button>
            ))}
          </div>

          <form onSubmit={submit} className="space-y-4">
            {mode === "register" ? (
              <Input
                id="full_name"
                label="Full name"
                placeholder="Ada Lovelace"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
              />
            ) : null}
            <Input
              id="email"
              label="Email"
              type="email"
              required
              placeholder="you@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
            <Input
              id="password"
              label="Password"
              type="password"
              required
              minLength={mode === "register" ? 8 : undefined}
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />

            {error ? (
              <p className="rounded-md border border-danger/30 bg-danger/10 px-3 py-2 text-[13px] text-danger">
                {error}
              </p>
            ) : null}

            <Button type="submit" className="w-full" disabled={loading}>
              {loading ? "Please wait…" : mode === "login" ? "Sign in" : "Create account"}
            </Button>
          </form>

          {mode === "register" ? (
            <p className="mt-4 text-[12px] leading-relaxed text-content-subtle">
              Local MVP auth. Passwords are hashed and a default workspace is created for you.
              This auth boundary is replaceable by Supabase Auth in production.
            </p>
          ) : null}
        </div>
      </div>
    </main>
  );
}
