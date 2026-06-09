import Link from "next/link";
import { ArrowRight, Bot, ShieldCheck, Wallet, ListTodo } from "lucide-react";

const FEATURES = [
  { icon: ListTodo, title: "Tasks & Notes", desc: "Workspace-scoped, soft-deleted, fully audited." },
  { icon: Wallet, title: "Finance tracking", desc: "Cashflow only — never financial advice." },
  { icon: Bot, title: "AI command center", desc: "Proposes actions; you stay in control." },
];

export default function LandingPage() {
  return (
    <main className="relative min-h-screen overflow-hidden">
      <div className="mx-auto flex max-w-5xl flex-col items-center px-6 py-24 text-center">
        <span className="mb-6 inline-flex items-center gap-2 rounded-full border border-border bg-surface/70 px-3 py-1 text-[12px] text-content-muted backdrop-blur">
          <span className="h-1.5 w-1.5 rounded-full bg-primary" />
          Local MVP · Founder-grade command center
        </span>

        <div className="mb-5 flex h-16 w-16 items-center justify-center rounded-2xl bg-primary text-primary-fg shadow-glow">
          <ShieldCheck size={30} />
        </div>

        <h1 className="max-w-3xl text-4xl font-semibold tracking-tight text-content sm:text-5xl">
          CoreOS <span className="text-primary">Command Center</span>
        </h1>
        <p className="mt-5 max-w-xl text-[15px] leading-relaxed text-content-muted">
          A modular AI command center for personal and company productivity. Tasks, notes,
          finance, and an AI assistant that <span className="text-content">proposes</span> —
          while humans approve every write action.
        </p>

        <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
          <Link
            href="/login"
            className="inline-flex h-11 items-center gap-2 rounded-md bg-primary px-5 text-sm font-semibold text-primary-fg transition-colors hover:bg-primary-dim"
          >
            Enter Command Center <ArrowRight size={16} />
          </Link>
          <Link
            href="/dashboard"
            className="inline-flex h-11 items-center rounded-md border border-border px-5 text-sm font-medium text-content transition-colors hover:border-primary/60 hover:text-primary"
          >
            View dashboard
          </Link>
        </div>

        <div className="mt-16 grid w-full gap-4 sm:grid-cols-3">
          {FEATURES.map(({ icon: Icon, title, desc }) => (
            <div key={title} className="panel p-5 text-left">
              <span className="flex h-9 w-9 items-center justify-center rounded-lg border border-border bg-surface-input text-primary">
                <Icon size={18} />
              </span>
              <h3 className="mt-3 text-sm font-semibold text-content">{title}</h3>
              <p className="mt-1 text-[13px] text-content-muted">{desc}</p>
            </div>
          ))}
        </div>
      </div>
    </main>
  );
}
