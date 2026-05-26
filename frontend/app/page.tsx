import Link from "next/link";
import { ArrowRight, Bot, ListTodo, ShieldCheck, Wallet } from "lucide-react";
import { APP_VERSION } from "@/components/layout/nav";

const FEATURES = [
  { icon: ListTodo, title: "Tasks & Notes", desc: "Workspace-scoped, soft-deleted, fully audited." },
  { icon: Wallet, title: "Finance tracking", desc: "Cashflow only — never financial advice." },
  { icon: Bot, title: "AI command center", desc: "Proposes actions; you approve every write." },
];

export default function LandingPage() {
  return (
    <main className="relative min-h-screen overflow-hidden">
      <div className="mx-auto flex max-w-5xl flex-col items-center px-6 py-24 text-center sm:py-32">
        <span className="mb-6 inline-flex items-center gap-2 rounded-full border border-border bg-surface/70 px-3.5 py-1.5 text-[12px] text-content-muted backdrop-blur">
          <span className="h-1.5 w-1.5 rounded-full bg-primary" />
          Local-first command center · {APP_VERSION}
        </span>

        <div className="mb-6 flex h-16 w-16 items-center justify-center rounded-2xl bg-primary text-primary-fg shadow-glow-primary">
          <ShieldCheck size={30} />
        </div>

        <h1 className="max-w-3xl text-balance text-4xl font-semibold tracking-tight text-content sm:text-6xl">
          CoreOS <span className="text-primary">Command Center</span>
        </h1>
        <p className="mt-6 max-w-xl text-balance text-[15px] leading-relaxed text-content-muted sm:text-base">
          A premium, modular AI command center for personal and company productivity. Tasks, notes,
          finance, and an assistant that <span className="text-content">proposes</span> — while humans
          approve every write action.
        </p>

        <div className="mt-9 flex flex-wrap items-center justify-center gap-3">
          <Link
            href="/login"
            className="inline-flex h-12 items-center gap-2 rounded-lg bg-primary px-6 text-sm font-semibold text-primary-fg transition-colors hover:bg-primary-bright"
          >
            Enter Command Center <ArrowRight size={16} />
          </Link>
          <Link
            href="/dashboard"
            className="inline-flex h-12 items-center rounded-lg border border-border px-6 text-sm font-medium text-content transition-colors hover:border-primary/60 hover:text-primary"
          >
            View dashboard
          </Link>
        </div>

        <div className="mt-20 grid w-full gap-4 sm:grid-cols-3">
          {FEATURES.map(({ icon: Icon, title, desc }) => (
            <div key={title} className="panel p-6 text-left">
              <span className="flex h-10 w-10 items-center justify-center rounded-lg border border-border bg-surface-input text-primary">
                <Icon size={18} />
              </span>
              <h3 className="mt-4 text-sm font-semibold text-content">{title}</h3>
              <p className="mt-1.5 text-[13px] leading-relaxed text-content-muted">{desc}</p>
            </div>
          ))}
        </div>
      </div>
    </main>
  );
}
