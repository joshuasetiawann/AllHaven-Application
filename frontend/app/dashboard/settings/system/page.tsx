import { AppShell } from "@/components/layout/AppShell";
import { PageHeader } from "@/components/layout/PageHeader";
import SystemControl from "@/components/settings/SystemControl";

export default function SystemControlPage() {
  return (
    <AppShell>
      <PageHeader
        title="System Control"
        subtitle="Start, stop, restart, and inspect Haven services."
      />
      <SystemControl />
    </AppShell>
  );
}
