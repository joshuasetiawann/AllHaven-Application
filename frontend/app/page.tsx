"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { LoaderCircle, ShieldCheck } from "lucide-react";
import { APP_VERSION } from "@/components/layout/nav";

export default function HomePage() {
  const router = useRouter();

  useEffect(() => {
    router.replace("/dashboard");
  }, [router]);

  return (
    <main className="flex min-h-screen items-center justify-center bg-bg px-5 py-10 text-content">
      <div className="flex w-full max-w-sm flex-col items-center text-center">
        <div className="grad-primary mb-4 flex h-14 w-14 items-center justify-center rounded-xl text-primary-fg shadow-glow-primary">
          <ShieldCheck size={24} />
        </div>
        <p className="label-mono">AllHaven {APP_VERSION}</p>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight">Opening Command Center</h1>
        <p className="mt-2 text-sm leading-relaxed text-content-muted">
          Checking your session and routing you to the right workspace.
        </p>
        <LoaderCircle className="mt-6 animate-spin text-primary" size={22} />
        <div className="mt-6 flex gap-3 text-sm">
          <Link className="text-primary hover:text-primary-bright" href="/login">
            Login
          </Link>
          <Link className="text-content-muted hover:text-content" href="/dashboard">
            Dashboard
          </Link>
        </div>
      </div>
    </main>
  );
}
