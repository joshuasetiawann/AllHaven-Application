import Link from "next/link";
import { ArrowRight, Check, Laptop, ShieldCheck, Smartphone, X } from "lucide-react";
import { APP_VERSION } from "@/components/layout/nav";

// The landing page argues the one thing that actually separates AllHaven from
// every other "AI assistant": it proposes, you decide. So the hero is not a
// stack of adjectives — it is the approval moment itself, rendered in the same
// visual language the app uses for the real thing.
const PROPOSAL = {
  tool: "create_transaction",
  summary: "Record 15,000 IDR expense — lunch",
  detail: "From: “spent 15k on lunch today”",
};

// The two surfaces are the page's structural device because choosing between
// them is the actual decision a visitor has to make, and the one people get
// wrong. Not a decorative 01/02/03.
const SURFACES = [
  {
    icon: Laptop,
    name: "Desktop",
    role: "Runs the backend",
    detail: "Your database, your models, your machine. Install from source with one command.",
    href: "https://github.com/joshuasetiawann/AllHaven-Application#quick-start",
    cta: "Read the install guide",
  },
  {
    icon: Smartphone,
    name: "Phone",
    role: "Works on its own",
    detail: "Tasks, notes, finance, memory, knowledge and approvals — with the desktop switched off.",
    href: "https://github.com/joshuasetiawann/AllHaven-Application/releases/tag/mobile-latest",
    cta: "Download the Android APK",
  },
];

export default function LandingPage() {
  return (
    <main className="relative min-h-screen overflow-hidden">
      {/* The app's signature ambient layer. Every authenticated screen has it;
          the landing page did not, which is why it read as a different product. */}
      <div className="pointer-events-none fixed inset-0 z-0" aria-hidden>
        <div className="aurora">
          <i />
        </div>
      </div>

      <div className="relative z-[1] mx-auto w-full max-w-6xl px-6 pb-20 pt-14 sm:pb-24 sm:pt-20">
        {/* Asymmetric: the argument on the left, the proof on the right. */}
        <div className="grid gap-12 lg:grid-cols-[minmax(0,1fr)_minmax(0,26rem)] lg:items-center lg:gap-14">
          <div className="animate-fade-in">
            <p className="label-mono flex items-center gap-2">
              <span className="h-1.5 w-1.5 rounded-full bg-primary" />
              Local-first · {APP_VERSION}
            </p>

            <h1 className="mt-5 text-balance text-[2.6rem] font-semibold leading-[1.05] tracking-tight text-content sm:text-6xl">
              The assistant that
              <br />
              <span className="text-grad">asks first.</span>
            </h1>

            <p className="mt-6 max-w-lg text-balance text-[15px] leading-relaxed text-content-muted sm:text-base">
              AllHaven keeps your tasks, notes, finance and workspace memory on hardware you
              control. Its AI can draft an action — but writing anything waits for you to say yes.
            </p>

            <div className="mt-8 flex flex-wrap items-center gap-3">
              <Link
                href="/login"
                className="focus-ring grad-primary inline-flex h-12 w-full items-center justify-center gap-2 rounded-xl px-6 text-sm font-semibold text-primary-fg shadow-glow-primary transition-transform hover:-translate-y-0.5 sm:w-auto"
              >
                Open your workspace <ArrowRight size={16} />
              </Link>
              <Link
                href="#surfaces"
                className="focus-ring inline-flex h-12 w-full items-center justify-center rounded-xl border border-border px-6 text-sm font-medium text-content transition-colors hover:border-primary/60 hover:text-primary sm:w-auto"
              >
                Which one do I install?
              </Link>
            </div>

            <p className="mt-6 flex items-center gap-2 text-[12.5px] text-content-subtle">
              <ShieldCheck size={14} className="shrink-0 text-primary" />
              Never fabricates AI output — an unreachable model says so.
            </p>
          </div>

          {/* Signature: the approval queue, the product's actual mechanic. */}
          <div className="animate-slide-up lg:animate-float-y">
            <div className="panel-gradient p-5">
              <div className="flex items-center justify-between">
                <p className="label-mono">Pending approval</p>
                <span className="inline-flex items-center gap-1.5 rounded-full border border-warning/30 bg-warning/10 px-2.5 py-1 text-[11px] font-medium text-warning">
                  <span className="h-1.5 w-1.5 animate-pulse-glow rounded-full bg-warning" />
                  Waiting for you
                </span>
              </div>

              <div className="glass-tile mt-4 p-4">
                <p className="font-mono text-[11px] text-primary-bright">{PROPOSAL.tool}</p>
                <p className="mt-2 text-[15px] font-medium leading-snug text-content">
                  {PROPOSAL.summary}
                </p>
                <p className="mt-1.5 text-[12.5px] leading-relaxed text-content-subtle">
                  {PROPOSAL.detail}
                </p>
              </div>

              <div className="mt-4 grid grid-cols-2 gap-2.5" aria-hidden>
                <span className="inline-flex h-10 items-center justify-center gap-1.5 rounded-lg border border-success/30 bg-success/10 text-[13px] font-semibold text-success">
                  <Check size={15} /> Approve
                </span>
                <span className="inline-flex h-10 items-center justify-center gap-1.5 rounded-lg border border-border text-[13px] font-medium text-content-muted">
                  <X size={15} /> Reject
                </span>
              </div>

              <p className="mt-4 text-[11.5px] leading-relaxed text-content-faint">
                Nothing is written until you approve it. Every decision is recorded.
              </p>
            </div>
          </div>
        </div>

        {/* The install decision, answered where people actually look for it. */}
        <section id="surfaces" className="mt-16 scroll-mt-8 sm:mt-20">
          <h2 className="text-[13px] font-semibold uppercase tracking-[0.14em] text-content-subtle">
            Two surfaces, one workspace
          </h2>
          <div className="mt-5 grid gap-4 sm:grid-cols-2">
            {SURFACES.map(({ icon: Icon, name, role, detail, href, cta }) => (
              <a
                key={name}
                href={href}
                className="focus-ring panel panel-hover group flex flex-col p-6"
              >
                <span className="flex h-11 w-11 items-center justify-center rounded-xl border border-border bg-surface-input text-primary">
                  <Icon size={19} />
                </span>
                <h3 className="mt-4 text-base font-semibold text-content">{name}</h3>
                <p className="mt-0.5 text-[12.5px] font-medium text-primary-bright">{role}</p>
                <p className="mt-2.5 flex-1 text-[13.5px] leading-relaxed text-content-muted">
                  {detail}
                </p>
                <span className="mt-5 inline-flex items-center gap-1.5 text-[13px] font-medium text-content transition-colors group-hover:text-primary">
                  {cta}
                  <ArrowRight size={14} className="transition-transform group-hover:translate-x-0.5" />
                </span>
              </a>
            ))}
          </div>
        </section>
      </div>
    </main>
  );
}
