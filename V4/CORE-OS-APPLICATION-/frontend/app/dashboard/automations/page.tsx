"use client";

import { useEffect, useState } from "react";
import { Workflow, Zap } from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card } from "@/components/ui/Card";
import { EmptyState, Loading } from "@/components/ui/States";
import { IntegrationStatusBanner } from "@/components/modules/IntegrationStatusBanner";
import { settingsApi } from "@/lib/api";
import type { Integration } from "@/types";

const SAMPLE_FLOWS = [
  { name: "Daily digest", desc: "Summarize tasks & cashflow each morning." },
  { name: "Receipt capture", desc: "Turn forwarded receipts into transactions (with approval)." },
  { name: "Note → task", desc: "Convert flagged notes into tasks (with approval)." },
];

export default function AutomationsPage() {
  const [integration, setIntegration] = useState<Integration | undefined>();
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    settingsApi
      .integrations()
      .then((r) => setIntegration(r.integrations.find((i) => i.key === "n8n")))
      .finally(() => setLoading(false));
  }, []);

  const configured = integration?.configured;

  return (
    <AppShell>
      <PageHeader title="Automations" subtitle="Workflow automation via n8n." />
      {loading ? (
        <Loading />
      ) : (
        <>
          <IntegrationStatusBanner integration={integration} label="n8n Automation" />

          {configured ? (
            <Card>
              <EmptyState
                title="No workflows yet"
                description="n8n is configured. Workflow execution is not wired into CoreOS yet — flows will appear here once enabled. CoreOS never executes workflows without explicit support."
                icon={<Workflow size={20} />}
              />
            </Card>
          ) : (
            <>
              <p className="mb-3 text-[13px] text-content-muted">
                Example automations you can build once n8n is connected (templates — not active):
              </p>
              <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
                {SAMPLE_FLOWS.map((flow) => (
                  <Card key={flow.name} className="opacity-90">
                    <div className="flex items-start justify-between">
                      <span className="flex h-10 w-10 items-center justify-center rounded-lg border border-border bg-surface-input text-primary">
                        <Zap size={18} />
                      </span>
                      <span className="rounded border border-border px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-content-subtle">
                        Template
                      </span>
                    </div>
                    <h3 className="mt-3 text-sm font-semibold text-content">{flow.name}</h3>
                    <p className="mt-1 text-[12.5px] text-content-muted">{flow.desc}</p>
                  </Card>
                ))}
              </div>
            </>
          )}
        </>
      )}
    </AppShell>
  );
}
