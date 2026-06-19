import type { ReactNode } from "react";

// The AppShell (with auth guard) is applied per-page so each page sets its own
// title. This layout is a simple passthrough.
export default function DashboardLayout({ children }: { children: ReactNode }) {
  return <>{children}</>;
}
