"use client";

import { useEffect, useMemo, useState } from "react";
import { CalendarDays } from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card } from "@/components/ui/Card";
import { Loading } from "@/components/ui/States";
import { IntegrationStatusBanner } from "@/components/modules/IntegrationStatusBanner";
import { settingsApi } from "@/lib/api";
import { cn } from "@/lib/format";
import type { Integration } from "@/types";

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

export default function CalendarPage() {
  const [integration, setIntegration] = useState<Integration | undefined>();
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    settingsApi
      .integrations()
      .then((r) => setIntegration(r.integrations.find((i) => i.key === "google_calendar")))
      .finally(() => setLoading(false));
  }, []);

  // Current week dates (Mon–Sun), for an honest empty preview grid.
  const week = useMemo(() => {
    const now = new Date();
    const monday = new Date(now);
    const day = (now.getDay() + 6) % 7;
    monday.setDate(now.getDate() - day);
    return DAYS.map((label, i) => {
      const d = new Date(monday);
      d.setDate(monday.getDate() + i);
      return { label, date: d.getDate(), isToday: d.toDateString() === now.toDateString() };
    });
  }, []);

  return (
    <AppShell>
      <PageHeader title="Calendar" subtitle="Schedule preview — Google Calendar sync setup." />
      {loading ? (
        <Loading />
      ) : (
        <>
          <IntegrationStatusBanner integration={integration} label="Google Calendar" />

          <Card padding="none" className="overflow-hidden">
            <div className="grid grid-cols-7 border-b border-border">
              {week.map((d) => (
                <div key={d.label} className="border-r border-border px-3 py-2.5 text-center last:border-0">
                  <p className="text-[11px] uppercase tracking-wide text-content-subtle">{d.label}</p>
                  <p className={cn("mt-0.5 text-sm font-semibold", d.isToday ? "text-primary" : "text-content")}>
                    {d.date}
                  </p>
                </div>
              ))}
            </div>
            <div className="grid grid-cols-7" style={{ minHeight: 280 }}>
              {week.map((d) => (
                <div key={d.label} className="border-r border-border p-2 last:border-0" />
              ))}
            </div>
          </Card>

          <Card className="mt-5">
            <div className="flex flex-col items-center justify-center px-6 py-10 text-center">
              <span className="mb-3 flex h-12 w-12 items-center justify-center rounded-xl border border-border bg-surface-input text-primary">
                <CalendarDays size={22} />
              </span>
              <p className="text-sm font-medium text-content">No synced events</p>
              <p className="mt-1 max-w-md text-[13px] text-content-muted">
                Google Calendar OAuth is not implemented in this MVP, so no events are synced. CoreOS
                never shows fake calendar events. Add your client ID in Settings to prepare the
                integration.
              </p>
            </div>
          </Card>
        </>
      )}
    </AppShell>
  );
}
