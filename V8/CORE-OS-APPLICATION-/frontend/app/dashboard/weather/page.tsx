"use client";

import { useEffect, useState } from "react";
import { CloudSun, MapPin, Search } from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Loading } from "@/components/ui/States";
import { IntegrationStatusBanner } from "@/components/modules/IntegrationStatusBanner";
import { settingsApi } from "@/lib/api";
import type { Integration } from "@/types";

export default function WeatherPage() {
  const [integration, setIntegration] = useState<Integration | undefined>();
  const [loading, setLoading] = useState(true);
  const [location, setLocation] = useState("");

  useEffect(() => {
    settingsApi
      .integrations()
      .then((r) => setIntegration(r.integrations.find((i) => i.key === "weather_api")))
      .finally(() => setLoading(false));
  }, []);

  const configured = integration?.configured;

  return (
    <AppShell>
      <PageHeader title="Weather" subtitle="Local weather context for your workspace." />
      {loading ? (
        <Loading />
      ) : (
        <>
          <IntegrationStatusBanner integration={integration} label="Weather API" />

          <Card className="mb-5">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
              <div className="flex-1">
                <label className="mb-1.5 block text-[12px] font-medium uppercase tracking-wide text-content-muted">
                  Location
                </label>
                <div className="relative">
                  <MapPin size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-content-subtle" />
                  <input
                    value={location}
                    onChange={(e) => setLocation(e.target.value)}
                    placeholder={integration?.public_config?.default_location || "e.g. Jakarta"}
                    className="h-10 w-full rounded-md border border-border bg-surface-input pl-9 pr-3 text-sm text-content placeholder:text-content-subtle focus:border-primary/70 focus:outline-none"
                  />
                </div>
              </div>
              <Button variant={configured ? "primary" : "subtle"} disabled title={configured ? "Live fetch not implemented in MVP" : "Configure the Weather API first"}>
                <Search size={15} /> Get weather
              </Button>
            </div>
          </Card>

          <Card>
            <div className="flex flex-col items-center justify-center px-6 py-12 text-center">
              <span className="mb-3 flex h-12 w-12 items-center justify-center rounded-xl border border-border bg-surface-input text-primary">
                <CloudSun size={22} />
              </span>
              {configured ? (
                <>
                  <p className="text-sm font-medium text-content">Weather API configured</p>
                  <p className="mt-1 max-w-sm text-[13px] text-content-muted">
                    The live weather fetch endpoint is not implemented in this MVP yet, so no forecast is
                    shown. CoreOS never displays fake weather data.
                  </p>
                </>
              ) : (
                <>
                  <p className="text-sm font-medium text-content">Weather is not configured</p>
                  <p className="mt-1 max-w-sm text-[13px] text-content-muted">
                    Add a Weather API key in Settings → Connected Tools to prepare this module.
                  </p>
                </>
              )}
            </div>
          </Card>
        </>
      )}
    </AppShell>
  );
}
