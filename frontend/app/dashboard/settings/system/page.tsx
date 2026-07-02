import { Terminal } from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { PageHeader } from "@/components/layout/PageHeader";
import SystemControl from "@/components/settings/SystemControl";
import { APP_VERSION } from "@/components/layout/nav";

export default function SystemControlPage() {
  return (
    <AppShell>
      <PageHeader
        title="System Control"
        subtitle="Start, stop, restart, and inspect Haven services."
        actions={
          <span className="inline-flex shrink-0 items-center gap-1.5 rounded-full border border-primary/30 bg-primary/10 px-3 py-1.5 font-mono text-[11px] tracking-[0.06em] text-primary-bright">
            <Terminal size={13} /> AllHaven {APP_VERSION}
          </span>
        }
      />
      <SystemControl />
    </AppShell>
  );
}
